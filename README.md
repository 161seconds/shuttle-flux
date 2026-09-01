# Shuttle Flux — Badminton AI Analytics

AI-powered badminton match video analytics platform: automated player & shuttlecock tracking, 2D court homography, movement analytics, rally segmentation, and interactive web dashboard.

---

## 🏗 Architecture & Project Structure

```text
shuttle-flux/
├── apps/
│   ├── api/                  # FastAPI backend (REST API, job management, storage)
│   ├── worker/               # Async video processing worker (CV/ML pipeline)
│   └── web/                  # Next.js frontend web dashboard
├── ml/                       # Machine learning models & inference wrappers
│   ├── player_detection/     # YOLO player detection
│   ├── shuttle_detection/    # High-resolution shuttlecock detection
│   ├── court_keypoints/      # Court keypoints & landmark detection
│   ├── tracking/             # ByteTrack & temporal shuttle tracking
│   └── shot_classification/  # Shot type classification
├── analytics/                # Analytics engine (pure metrics & physics)
│   ├── movement.py           # Distance, speed, acceleration
│   ├── rally.py              # Rally segmentation & state machine
│   ├── shots.py              # Hit detection & shot analytics
│   ├── heatmap.py            # 2D density & court coverage
│   └── court.py              # Court dimensions & coordinate normalization
├── pipelines/                # Video processing pipelines
│   ├── preprocess.py         # Video normalization & frame extraction
│   ├── detect.py             # Multi-model detection step
│   ├── track.py              # Tracking association & smoothing
│   ├── calibrate.py          # Homography transformation
│   ├── analyze.py            # Analytics computation
│   └── render.py             # Annotated video & radar rendering
├── datasets/                 # Dataset configurations & annotations
├── notebooks/                # Experimentation & model training notebooks
├── tests/                    # Unit, integration, and e2e tests
└── infra/                    # Docker & deployment configurations
```

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10+ (PyTorch, Ultralytics YOLO, OpenCV, Supervision, FastAPI)
- Node.js 18+ (Next.js, Tailwind CSS)
- FFmpeg installed and in PATH

### 2. Setup
Refer to [badminton-ai-roadmap.md](./badminton-ai-roadmap.md) for full system blueprint and sprint plan.
