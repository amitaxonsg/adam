"""ADAM artwork prototype: local Qwen layer decomposition + TIFF production export."""
from __future__ import annotations
import io, json, os, shutil, threading, uuid, zipfile
from pathlib import Path
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps, UnidentifiedImageError

BASE = Path(__file__).resolve().parent
JOBS = Path(os.getenv("ADAM_JOBS_DIR", BASE / "jobs")).resolve()
JOBS.mkdir(parents=True, exist_ok=True)
MAX_BYTES = 20 * 1024 * 1024
MAX_PIXELS = 40_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS
app = FastAPI(title="ADAM Artwork Reconstruction Prototype")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
_LOCK = threading.Lock()
_PIPE = None

@app.get("/")
def index():
    return FileResponse(BASE / "static" / "index.html")

@app.get("/api/health")
def health():
    return {"ok": True, "mode": os.getenv("ADAM_MODE", "qwen"), "gpu_model_loaded": _PIPE is not None}

def get_pipeline():
    global _PIPE
    if _PIPE is None:
        import torch
        from diffusers import QwenImageLayeredPipeline
        if not torch.cuda.is_available():
            raise RuntimeError("Qwen requires a CUDA GPU in this prototype. Use ADAM_MODE=manual on CPU.")
        _PIPE = QwenImageLayeredPipeline.from_pretrained("Qwen/Qwen-Image-Layered")
        _PIPE = _PIPE.to("cuda", torch.bfloat16)
    return _PIPE

def save_outputs(work: Path, layers: list[Image.Image], dpi: int):
    canvas = layers[0].size
    stack = Image.new("RGBA", canvas, (0, 0, 0, 0))
    info = []
    for i, img in enumerate(layers, 1):
        layer = img.convert("RGBA")
        if layer.size != canvas:
            raise ValueError("Layer size mismatch")
        layer.save(work / f"layer_{i:02}.png")
        stack = Image.alpha_composite(stack, layer)
        info.append({"name": f"layer_{i:02}", "file": f"layer_{i:02}.png"})
    stack.save(work / "composite.png")
    # Lossless RGBA TIFF; color profile and RIP conversion require factory verification.
    stack.save(work / "production_rgba.tif", format="TIFF", compression="tiff_deflate", dpi=(dpi, dpi))
    metadata = {"layers": info, "size_px": list(canvas), "dpi": dpi,
                "note": "TIFF is an RGBA raster proof, not a certified RIP/CMYK factory output."}
    (work / "manifest.json").write_text(json.dumps(metadata, indent=2), encoding="utf8")
    with zipfile.ZipFile(work / "package.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(work.iterdir()):
            if f.is_file() and f.name != "package.zip":
                z.write(f, f.name)
    return metadata

@app.post("/api/process")
async def process(file: UploadFile = File(...), layers: int = Form(4), dpi: int = Form(300)):
    if not 2 <= layers <= 10 or dpi not in (150, 300, 600):
        raise HTTPException(400, "Layers must be 2-10 and DPI 150, 300, or 600")
    raw = await file.read(MAX_BYTES + 1)
    await file.close()
    if len(raw) > MAX_BYTES:
        raise HTTPException(413, "File exceeds 20 MB limit")
    try:
        with Image.open(io.BytesIO(raw)) as source:
            if source.format not in ("PNG", "JPEG", "WEBP", "TIFF"):
                raise ValueError("Use PNG, JPEG, WEBP or TIFF")
            image = ImageOps.exif_transpose(source)
            image.load()
            if image.width * image.height > MAX_PIXELS:
                raise ValueError("Image too large")
            image = image.convert("RGBA")
    except (UnidentifiedImageError, ValueError, OSError) as exc:
        raise HTTPException(400, f"Invalid image: {exc}") from exc

    # Lock prevents concurrent heavy GPU inferences in this proof of concept.
    if not _LOCK.acquire(blocking=False):
        raise HTTPException(429, "Another processing job is active. Retry after it finishes.")
    job_id = uuid.uuid4().hex
    work = JOBS / job_id
    work.mkdir(parents=True)
    try:
        image.save(work / "original.png")
        mode = os.getenv("ADAM_MODE", "qwen").lower()
        if mode == "manual":
            # CPU demonstration: a single editable image layer, not AI segmentation.
            outputs = [image]
        elif mode == "qwen":
            import torch
            pipe = get_pipeline()
            with torch.inference_mode():
                result = pipe(image=image, generator=torch.Generator(device="cuda").manual_seed(777),
                              true_cfg_scale=4.0, negative_prompt=" ", num_inference_steps=50,
                              num_images_per_prompt=1, layers=layers, resolution=640,
                              cfg_normalize=True, use_en_prompt=True)
            outputs = result.images[0]
        else:
            raise ValueError("ADAM_MODE must be manual or qwen")
        metadata = save_outputs(work, outputs, dpi)
        return {"job_id": job_id, "mode": mode, **metadata,
                "preview": f"/api/jobs/{job_id}/composite.png",
                "package": f"/api/jobs/{job_id}/package.zip",
                "tiff": f"/api/jobs/{job_id}/production_rgba.tif"}
    except Exception as exc:
        shutil.rmtree(work, ignore_errors=True)
        raise HTTPException(500, f"Processing failed: {exc}") from exc
    finally:
        _LOCK.release()

@app.get("/api/jobs/{job_id}/{filename}")
def file_output(job_id: str, filename: str):
    if len(job_id) != 32 or any(c not in "0123456789abcdef" for c in job_id):
        raise HTTPException(404)
    allowed = {"original.png", "composite.png", "production_rgba.tif", "package.zip", "manifest.json"}
    if filename.startswith("layer_") and filename.endswith(".png") and len(filename) == 12:
        allowed.add(filename)
    if filename not in allowed:
        raise HTTPException(404)
    target = JOBS / job_id / filename
    if not target.is_file():
        raise HTTPException(404)
    return FileResponse(target, filename=filename if filename.endswith((".zip", ".tif")) else None)
