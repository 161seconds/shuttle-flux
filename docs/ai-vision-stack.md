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
| YOLO Athlete Pose | 17 body joints plus elbow, shoulder and knee angles |
| Racket AI | Generic COCO racket fallback or custom handle/head/tip keypoints |
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

## Athlete pose and racket tracking

`ENABLE_POSE=1` activates the public `yolo11n-pose.pt` model. The pose estimator associates its 17 COCO body joints only with players that already passed Shuttle Flux's court/referee filtering. It also calculates left/right elbow, shoulder and knee angles. `POSE_FRAME_INTERVAL=2` is the recommended RTX 4050 setting; the tracker retains the previous skeleton between pose frames.

## Automatic BWF court calibration

The court detector segments the playing surface, extracts both perspective line families, fits the complete BWF marking template, and refines image-to-court homography from multiple detected intersections with RANSAC. The template uses the official 6.10 x 13.40 m doubles boundary, 0.46 m singles alleys, 1.98 m short-service offset, and 0.76 m doubles long-service offset from the current BWF Laws of Badminton.

Calibration is accepted only when `COURT_MIN_CONFIDENCE`, `COURT_MIN_DETECTED_LINES`, and `COURT_MAX_REPROJECTION_ERROR` all pass. `ALLOW_COURT_FALLBACK=0` is the safe default: if the actual markings cannot be read, the worker stops instead of producing a guessed 2D map. Set it to `1` only for legacy/demo behavior.

Official geometry source: [BWF Laws of Badminton, Section 4.1 (26 April 2025)](https://extranet.bwf.sport/docs/document-system/81/1466/1470/Section%204.1%20-%20Laws%20of%20Badminton%20-%2026%20April%202025%20V5.0%20(2)%20.pdf).

Racket tracking has two levels:

1. Without a custom model, the existing YOLO detector uses COCO class 38 (`tennis racket`) as a zero-setup badminton fallback. Wrist proximity rejects most rackets belonging to officials or people outside the court.
2. With `models/racket-pose.pt`, the custom model returns three racket keypoints: handle, racket-head center and racket-head tip. This provides racket direction and a better basis for future swing-speed/contact analysis.

Prepare an Ultralytics pose dataset using [datasets/racket-pose.yaml](../datasets/racket-pose.yaml), then train and copy the best checkpoint:

```powershell
python scripts/train_racket_pose.py --epochs 100 --imgsz 960
Copy-Item runs/racket-pose/yolo11n-racket-keypoints/weights/best.pt models/racket-pose.pt
```

The video overlay draws the athlete skeleton, joint nodes, racket box, smoothed pixel speed and custom racket axis when these detections are available. Generic racket recognition is useful immediately, but a badminton-specific dataset is required for reliable broadcast-level racket tracking.

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
