# ADAM — Artwork reconstruction prototype

Independent proof of concept; does not modify the existing ADAM questionnaire or PHP backend.

## Architecture
Browser upload -> FastAPI -> optional Qwen-Image-Layered local GPU -> RGBA layers -> TIFF/ZIP.
The standalone API is local, **not a paid API**. A remotely hosted GPU service can be added later.
Qwen reconstructs approximate raster layers; it does not recover source Illustrator vector objects or fonts. TIFF is flattened raster output; all RGBA PNG layers are retained in the ZIP.

## Quick start — Windows PowerShell (CPU smoke test)
```powershell
git clone https://github.com/amitaxonsg/adam.git
cd adam/prototype
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:ADAM_MODE="manual"
uvicorn app:app --host 127.0.0.1 --port 8000
```
Visit http://127.0.0.1:8000 . **Manual mode does not extract layers**: it validates upload, original retention, PNG/TIFF/ZIP output and UI.

## Qwen GPU mode
Use a CUDA-capable Linux worker with adequate VRAM. The Windows GTX 1050 Ti and a CPU-only Germany VPS are not appropriate for this full model without separately proven optimizations.

Install a CUDA-compatible PyTorch build using the instructions at https://pytorch.org/get-started/locally/ then:
```bash
pip install -r requirements.txt
pip install 'transformers>=4.51.3' accelerate safetensors
pip install git+https://github.com/huggingface/diffusers
export ADAM_MODE=qwen
uvicorn app:app --host 127.0.0.1 --port 8000
```
First run downloads large model weights from Hugging Face; ensure sufficient free storage. Exact hardware needs must be benchmarked. Qwen reference: https://github.com/QwenLM/Qwen-Image-Layered

## German VPS migration
Clone the repo on the explicitly selected VPS, install Python environment, use `ADAM_MODE=manual` initially, and run under a process manager behind authenticated HTTPS reverse proxy. **Do not publicly expose this prototype**: it has no authentication, rate limits beyond the single processing lock, file retention policy, or production image security controls. For actual GPU decomposition, connect a separate secured GPU worker. Do not assume CUDA on the Contabo CPU VPS.

## Production gaps
- TIFF factory RIP requirements: print dimensions and resizing, ICC profile/CMYK, transparency, bleed, panel separation, format/compression.
- Secure customers and files; expiry, quotas, background job queue, input scanning.
- Editable vector tracing, OCR, object corrections, SVG, roster, garment sizing and cloPRO integration are next modules.
- Review licensing and commercial compatibility of Qwen model, cloPRO and other components prior to delivery.
