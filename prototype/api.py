"""ADAM hosted Qwen API prototype. Run: uvicorn api:app --host 127.0.0.1 --port 8000
This is a developer prototype, not a public multi-tenant service.
"""
from __future__ import annotations
import io
import json
import os
import secrets
import threading
import uuid
import zipfile
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from PIL import Image, ImageOps, UnidentifiedImageError

BASE = Path(__file__).resolve().parent
DATA = Path(os.getenv("ADAM_DATA", str(BASE / "jobs"))).resolve()
DATA.mkdir(parents=True, exist_ok=True)
MAX_UPLOAD = 20 * 1024 * 1024
MAX_PIXELS = 40_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS
# One job per process for the early proof of concept.
active = threading.Lock()
states: dict[str, dict] = {}
app = FastAPI(title="ADAM Artwork Processing API", version="0.2.0")

def authorize(x_adam_token: str | None):
    token = os.getenv("ADAM_ACCESS_TOKEN")
    if not token:
        raise HTTPException(503, "Configure ADAM_ACCESS_TOKEN before starting the API")
    if not x_adam_token or not secrets.compare_digest(x_adam_token, token):
        raise HTTPException(401, "Invalid ADAM access token")

def safe_download(url: str) -> bytes:
    # Do not allow arbitrary provider-controlled URLs to become SSRF requests.
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in {"fal.media", "v3b.fal.media", "storage.googleapis.com"}:
        raise ValueError("Unexpected output host; review provider URL configuration")
    with httpx.Client(timeout=90, follow_redirects=False) as client:
        with client.stream("GET", url) as response:
            response.raise_for_status()
            data = bytearray()
            for chunk in response.iter_bytes(65536):
                data.extend(chunk)
                if len(data) > MAX_UPLOAD:
                    raise ValueError("Provider layer exceeds 20MB")
            return bytes(data)

def save_images(folder: Path, images: list[Image.Image], dpi: int):
    if not images:
        raise ValueError("No image layers returned")
    canvas = images[0].size
    composite = Image.new("RGBA", canvas, (0, 0, 0, 0))
    layers = []
    for index, image in enumerate(images, 1):
        if image.size != canvas:
            raise ValueError("Provider returned inconsistent layer dimensions")
        image = image.convert("RGBA")
        if image.width * image.height > MAX_PIXELS:
            raise ValueError("Layer exceeds pixel limit")
        name = f"layer_{index:02d}.png"
        image.save(folder / name)
        composite = Image.alpha_composite(composite, image)
        layers.append({"name": f"Layer {index}", "file": name})
    composite.save(folder / "preview.png")
    composite.save(folder / "print_rgba.tif", format="TIFF", compression="tiff_deflate", dpi=(dpi, dpi))
    manifest = {"width": canvas[0], "height": canvas[1], "dpi": dpi, "layers": layers,
                "warning": "Proof-only RGBA TIFF; verify physical dimensions, ICC, RIP, panel specifications before production."}
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf8")
    with zipfile.ZipFile(folder / "artwork.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(folder.iterdir()):
            if file.is_file() and file.name != "artwork.zip":
                archive.write(file, file.name)
    return manifest

def perform(job: str, source: Path, count: int, dpi: int):
    folder = source.parent
    states[job] = {"state": "processing"}
    try:
        if os.getenv("ADAM_MODE", "fal") == "manual":
            with Image.open(source) as im:
                images = [im.convert("RGBA").copy()]
            mode = "manual — no AI extraction"
        else:
            if not os.getenv("FAL_KEY"):
                raise ValueError("FAL_KEY missing; set it privately on the server")
            import fal_client
            url = fal_client.upload_file(str(source))
            response = fal_client.subscribe("fal-ai/qwen-image-layered",
                        arguments={"image_url": url, "num_layers": count,
                                   "output_format": "png", "enable_safety_checker": True})
            entries = response.get("images", [])
            images = []
            for entry in entries:
                binary = safe_download(entry["url"])
                with Image.open(io.BytesIO(binary)) as im:
                    im.load()
                    if im.width * im.height > MAX_PIXELS:
                        raise ValueError("Returned layer too large")
                    images.append(im.convert("RGBA").copy())
            mode = "fal-ai/qwen-image-layered"
        manifest = save_images(folder, images, dpi)
        states[job] = {"state": "complete", "mode": mode, **manifest}
    except Exception as exc:
        states[job] = {"state": "error", "message": str(exc)[:500]}
    finally:
        active.release()

@app.get("/")
def home():
    return FileResponse(BASE / "static" / "studio.html")

@app.get("/api/health")
def health():
    return {"ok": True, "mode": os.getenv("ADAM_MODE", "fal"), "api_key_configured": bool(os.getenv("FAL_KEY"))}

@app.post("/api/jobs", status_code=202)
async def submit(file: UploadFile = File(...), layers: int = Form(4), dpi: int = Form(300),
                 x_adam_token: str | None = Header(default=None)):
    authorize(x_adam_token)
    if not 1 <= layers <= 10 or dpi not in {150, 300, 600}:
        raise HTTPException(400, "Invalid layer count or DPI")
    if not active.acquire(blocking=False):
        raise HTTPException(429, "One job is already running")
    folder = None
    try:
        raw = await file.read(MAX_UPLOAD + 1)
        await file.close()
        if not raw or len(raw) > MAX_UPLOAD:
            raise HTTPException(413, "Upload must be 1 byte to 20 MB")
        try:
            with Image.open(io.BytesIO(raw)) as im:
                if im.format not in {"PNG", "JPEG", "WEBP", "TIFF"}:
                    raise ValueError("Unsupported image")
                if im.width * im.height > MAX_PIXELS:
                    raise ValueError("Too many pixels")
                source_image = ImageOps.exif_transpose(im).convert("RGBA")
        except (OSError, ValueError, UnidentifiedImageError) as exc:
            raise HTTPException(400, f"Invalid image: {exc}") from exc
        job = uuid.uuid4().hex
        folder = DATA / job
        folder.mkdir(parents=True)
        source = folder / "original.png"
        source_image.save(source)
        states[job] = {"state": "queued"}
        threading.Thread(target=perform, args=(job, source, layers, dpi), daemon=True).start()
        return {"job_id": job, "state": "queued"}
    except Exception:
        active.release()
        if folder is not None:
            import shutil
            shutil.rmtree(folder, ignore_errors=True)
        raise

@app.get("/api/jobs/{job}")
def status(job: str, x_adam_token: str | None = Header(default=None)):
    authorize(x_adam_token)
    if job not in states:
        raise HTTPException(404, "Unknown job or server restarted")
    return states[job]

@app.get("/api/jobs/{job}/files/{filename}")
def download(job: str, filename: str, x_adam_token: str | None = Header(default=None)):
    authorize(x_adam_token)
    state = states.get(job)
    if not state or state["state"] != "complete" or len(job) != 32:
        raise HTTPException(404)
    permitted = {"preview.png", "print_rgba.tif", "artwork.zip", "original.png", "manifest.json"}
    permitted.update(row["file"] for row in state["layers"])
    if filename not in permitted:
        raise HTTPException(404)
    path = DATA / job / filename
    if not path.is_file():
        raise HTTPException(404)
    return FileResponse(path, filename=filename)
