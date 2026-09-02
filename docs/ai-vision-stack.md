# Shuttle Flux AI vision stack

This project uses each technology for a concrete part of the badminton analysis pipeline. Optional GPU models are lazy-loaded so the application still runs on CPU and on GPUs with limited VRAM.

| Technology | Role in Shuttle Flux |
| --- | --- |
| Python | API, worker, inference and analytics implementation |
| PyTorch | Native YOLO/SAM/OSNet execution and CUDA access |
| Ultralytics YOLO | Player detection and model export |
| SAM 3 | Periodic prompt-based player-mask refinement from YOLO boxes |
| TensorRT | Fast YOLO engine execution and ONNX Runtime OSNet provider |
| ONNX | Portable YOLO and OSNet inference format |
| CUDA | NVIDIA GPU execution and FP16 acceleration |
| OpenCV | Video decode, image transforms, masks and court geometry |
| Deep-EIoU | Multi-scale box/motion association for stable doubles tracking |
| OSNet ReID | Appearance embeddings that preserve IDs when players cross |
| OCR | EasyOCR scoreboard and jersey-name extraction |
| Homography | Camera-pixel to normalized 2D badminton-court projection |
| Flask | Dedicated model-serving process with warm models |
| JavaScript | Next.js runtime dashboard and interactive analytics UI |
| FFmpeg | Optional codec/pixel-format normalization of an analysis copy |

## Local setup

Create a clean Python environment and install the application dependencies:

```powershell
uv venv .venv --python 3.12
.\.venv\Scripts\Activate.ps1
uv pip install -r apps/api/requirements.txt
uv pip install Flask
```

`apps/api/requirements.txt` includes the worker dependencies because local FastAPI background jobs execute the video pipeline. For a separately isolated inference environment, install `apps/inference/requirements.txt` instead.

For ONNX/CUDA/TensorRT and OSNet, install the GPU extras from `apps/worker/requirements-gpu.txt`. TensorRT also requires a compatible NVIDIA driver/runtime. Verify the providers before relying on acceleration:

```powershell
python -c "import onnxruntime as ort; print(ort.get_available_providers())"
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"
```

Export a local YOLO checkpoint (the default path is `yolov8n.pt`):

```powershell
python scripts/export_models.py --format onnx --dynamic
python scripts/export_models.py --format engine --half
python scripts/export_osnet.py --arch osnet_x0_25
```

SAM 3 weights are gated and are not downloaded automatically. Place the authorized checkpoint at `models/sam3.pt`, then set `ENABLE_SAM3=1`. Place an exported OSNet checkpoint at `models/osnet_x0_25.onnx`, then set `ENABLE_OSNET=1`.

For a 6 GB GPU, use YOLO on every sampled frame, SAM 3 every 10 or more frames, and OSNet only for player crops. Running all large models on every video frame can exhaust VRAM.

## Run services

Run these in separate terminals from the repository root:

```powershell
# Optional warm-model Flask service
python -m apps.inference.app

# FastAPI backend
uvicorn apps.api.main:app --reload --port 8000

# Next.js frontend
cd apps/web
npm run dev
```

If Flask is not running, unset `INFERENCE_SERVICE_URL`; the worker falls back to local inference. Runtime state is available at `GET /api/v1/runtime` and is shown at the top of the dashboard.

## Docker

CPU-compatible stack:

```powershell
docker compose -f infra/docker/docker-compose.yml up --build
```

NVIDIA GPU overlay:

```powershell
docker compose -f infra/docker/docker-compose.yml -f infra/docker/docker-compose.gpu.yml up --build
```

The GPU overlay requires NVIDIA Container Toolkit and compatible SAM 3/OSNet model files in `models/`.
