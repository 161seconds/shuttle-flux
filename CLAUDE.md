# CLAUDE.md — Shuttle Flux AI Development Guidelines

This document provides system guidelines, development commands, architectural rules, and code conventions for AI agents and developers working on the **Shuttle Flux** repository.

---

## 🎯 Project Overview & Mission

**Shuttle Flux** is an end-to-end Computer Vision & AI analytics platform for professional badminton broadcast videos (Singles 1v1 and Doubles 2v2) adhering strictly to Badminton World Federation (BWF) court standards.

- **Backend**: Python 3.10+ (FastAPI, PyTorch, Ultralytics YOLOv8, OpenCV, EasyOCR, yt-dlp, SciPy, NumPy)
- **Frontend**: Next.js 16 (App Router + Turbopack), React 19, TypeScript 5.9, TailwindCSS, Lucide Icons, managed with **pnpm**
- **Pipeline**: Automated referee rejection, persistent player spatial tracking, 2D radar homography, 3D net perspective projection, scoreboard OCR, and rally segmentation.

---

## 🛠️ Essential Developer Commands

### 1. Backend (FastAPI & ML Pipeline)
```bash
# Environment setup (Windows PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install Python ML dependencies
pip install fastapi uvicorn pydantic python-multipart ultralytics opencv-python easyocr yt-dlp numpy scipy imageio imageio-ffmpeg pytest requests httpx

# Run FastAPI Development Server on port 8000
uvicorn apps.api.main:app --reload --port 8000

# Run all unit & integration tests
pytest tests/ -v

# Run specific test suites
pytest tests/unit/test_movement.py -v
pytest tests/integration/test_api.py -v
```

### 2. Frontend (Next.js 16 Web Dashboard)
```bash
# Move to frontend directory
cd apps/web

# Install packages with pnpm
pnpm install

# Start Next.js Turbopack dev server on port 3000
pnpm run dev

# Check TypeScript static types (0 error guarantee)
pnpm exec tsc --noEmit

# Production bundle build
pnpm run build
```

---

## 🏛️ Code Architecture & Directory Structure

```text
shuttle-flux/
├── apps/
│   ├── api/
│   │   ├── main.py               # FastAPI endpoints, YouTube 1080p downloader, streaming batches
│   │   └── storage.py            # In-memory registry & JSON file store (storage/results/)
│   ├── worker/
│   │   └── worker.py             # Async video processing worker (extracts, infers, streams)
│   └── web/                      # Next.js 16 Frontend (pnpm)
│       ├── src/app/              # Next.js App Router (page.tsx, layout.tsx, globals.css)
│       ├── src/components/       # UI Components:
│       │   ├── VideoPlayerWithRadar.tsx # Dual player, 3D BWF mesh, Scoreboard HUD, node dragging
│       │   ├── RadarCanvas.tsx          # 2D top-down court, player trails, density heatmap
│       │   ├── OverviewCards.tsx        # High-level stats cards with null-safety
│       │   ├── PlayerStats.tsx          # 1v1 & 2v2 player speed, distance, 6-zone matrix
│       │   └── RallyTimeline.tsx        # Rally breakdown & interactive video seek
│       └── src/lib/api.ts        # Typed API client, Axios/fetch wrappers, Data contracts
├── ml/
│   ├── player_detection/
│   │   └── detector.py           # YOLOv8 person detection + strict referee/umpire exclusion
│   ├── tracking/
│   │   └── tracker.py            # Spatial track association & net-rush ID continuity
│   ├── court_keypoints/
│   │   └── detector.py           # 12 BWF perspective landmarks & net optical midpoint
│   └── ocr/
│       └── scoreboard_reader.py  # EasyOCR reader for BWF broadcast HUD card (names & scores)
├── analytics/                    # Physics & metric calculation engine
│   ├── court.py                  # Court normalization & zone geometry
│   ├── movement.py               # Savitzky-Golay speed smoothing, Euclidean distance
│   ├── rally.py                  # Rally state machine (active play vs intermission)
│   └── heatmap.py                # 2D Gaussian density distribution
├── storage/                      # Video uploads and processed JSON result files
└── tests/                        # Comprehensive test suite (13 unit & integration tests)
```

---

## 📐 Core Engineering & ML Rules

### 1. Referee Exclusion Protocol (`ml/player_detection/detector.py`)
All tournament non-player personnel MUST be rejected:
- **Main Umpire**: Elevated high chair at net sideline ($x < 0.24$ or $x > 0.76$, $0.42 \le y \le 0.66$, $y_{top} < 0.26$).
- **Service Judge**: Seated low directly opposite the umpire at net level ($0.44 \le y \le 0.62$).
- **Far Line Judges**: Seated behind far baseline ($y_{bottom} < 0.40$ or $norm\_h < 0.09$).
- **Near Corner Judges**: Seated at $y > 0.88, x < 0.15$ or $x > 0.85$.
- **Dynamic Playable Corridor**: Enforces bounds from $26\%-74\%$ at far baseline to $10\%-90\%$ at near baseline.

### 2. Player Role & Net Rush Continuity (`ml/tracking/tracker.py`)
- Never use a hardcoded $y$ cutoff to classify near vs far players.
- Near Player (P1) is optical camera-near $\rightarrow$ larger bounding box height ($h > 0.20$), lower bottom position.
- Far Player (P2) is camera-far $\rightarrow$ smaller bounding box height ($h < 0.18$).
- **Net Rush Preservation**: When P2 rushes to the net to play a drop/net shot, continuous tracking matches the detection to P2 by minimal Euclidean distance from the preceding frame. Track ID MUST remain `P2` and never swap with `P1`.
- **Strict Singles 1v1**: Default to exactly 2 active tracks. Never emit ghost P3/P4 tracks in singles matches.

### 3. BWF Court Perspective Geometry
Standard 3D Dimensions: $13.40\text{m}$ Length $\times 6.10\text{m}$ Doubles Width / $5.18\text{m}$ Singles Width.
- **Top Baseline**: $y = 0.00\text{m}$ ($y_{top}$)
- **Far Doubles Long Service Line**: $0.76\text{m}$ from top baseline ($2.4\%$ in 2D)
- **Far Short Service Line**: $1.98\text{m}$ from net ($11.8\%$ in 2D)
- **Net Line & Posts**: Optical Center at $y = y_{top} + 0.20 \cdot \Delta y$
- **Near Short Service Line**: $1.98\text{m}$ from net ($31.7\%$ in 2D)
- **Near Doubles Long Service Line**: $0.76\text{m}$ inside near baseline ($88.0\%$ in 2D)
- **Bottom Baseline**: $y = 13.40\text{m}$ ($y_{bottom}$)
- **Singles Tramlines**: $7.5\%$ inset from left and right doubles lines.

### 4. Scoreboard OCR & Filtering (`ml/ocr/scoreboard_reader.py`)
- Target Box: Top-left of frame ($x: 2\%-32\%, y: 2\%-22\%$).
- Blacklist tournament sponsors/logos: `HSBC`, `BWF`, `WORLD TOUR`, `SUPER 750/1000`, `SHENZHEN`, `CHINA MASTERS`, `VICTOR`, `YONEX`, `TOTALENERGIES`.
- Extract True Player Names (e.g., `YU QI` for Far Court, `KEAN YEW` for Near Court) and Set Scores (`1 - 1`).

### 5. Frontend Polling & State Safety
- In `VideoPlayerWithRadar.tsx`, always wrap manual calibration state with `userHasEditedNodesRef` to prevent periodic polling updates from resetting user-dragged court corners.
- In all components mapping arrays (`rallies`, `hits`, `frame_records`), use defensive fallbacks: `const safeRallies = Array.isArray(rallies) ? rallies : []`.

---

## 🧪 Testing & Quality Standards

- **Always verify before commit**:
  1. `pytest tests/ -v` $\rightarrow$ 100% pass (13/13).
  2. `cd apps/web && pnpm exec tsc --noEmit` $\rightarrow$ 0 TypeScript errors.
  3. `pnpm run build` $\rightarrow$ Clean static generation.
- **Package Manager**: Use `pnpm` exclusively in `apps/web`. Never run `npm install` inside `apps/web` to avoid lockfile conflicts.
