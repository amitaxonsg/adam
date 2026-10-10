# ADAM hosted Qwen API prototype — deployment

## What this does
The browser uploads existing artwork; FastAPI sends the image to fal.ai Qwen-Image-Layered using a server-side key; retrieves isolated PNG layers; composites an RGBA TIFF and ZIP. No local GPU is needed. It preserves the original and layers but is **not** a vector recreation engine or completed roster/garment-production system.

## Windows PowerShell
```powershell
git clone https://github.com/amitaxonsg/adam.git C:\Projects\adam
cd C:\Projects\adam\prototype
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-api.txt
$env:FAL_KEY = "YOUR_PRIVATE_FAL_KEY"
$env:ADAM_ACCESS_TOKEN = "SET_A_LONG_RANDOM_PASSWORD"
$env:ADAM_MODE = "fal"
.\.venv\Scripts\python.exe -m uvicorn api:app --host 127.0.0.1 --port 8000
```
Open http://127.0.0.1:8000 and enter your ADAM_ACCESS_TOKEN. The browser never sees FAL_KEY.
For pipeline smoke tests, set ADAM_MODE=manual. It produces only one original layer, NOT AI separation.

## VPS later
Choose and confirm the target German VPS; do not mix it with other servers. Clone the same Git repository on that VPS and configure a server-local Python virtual environment. Put FAL_KEY and ADAM_ACCESS_TOKEN in private environment variables/service configuration (never Git), protect the API with authenticated HTTPS and a process manager, and use a dedicated data directory via ADAM_DATA. The application must stay private until tenant isolation, persistent job state, quotas, retention/cleanup, upload scanning, auditing, and storage access controls are completed.

## Limitations
- The **fal hosted service charges for inference** and receives uploaded artwork. Obtain customer consent and review the provider's data terms before real customer jobs.
- Qwen's image separation is approximate, not recovery of the original Illustrator/Photoshop layers.
- TIFF output is lossless RGBA only, and not yet factory certified. RIP print size, ICC color space, bleed, transparency, panel templates and CMYK conversion are intentionally not guessed.
- Job state is in memory; restart loses status, although files remain on disk. One job can execute at once. Use Redis/Celery with persistent records for production.
- No cloPRO, SVG tracing, editable object UI, roster or checkout integration yet.
- Provider output URLs are restricted to expected HTTPS hosts; if fal changes hosts, update allowed hosts after verifying the new domain.
- Provider docs: https://fal.ai/models/fal-ai/qwen-image-layered/api
