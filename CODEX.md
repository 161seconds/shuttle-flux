# CODEX.md — Shuttle Flux Codebase Index & Engineering Playbook

> **Complete Technical Reference, Mathematical Models, Data Contracts & Operational Runbook for Shuttle Flux**

---

## 📑 TABLE OF CONTENTS
1. [System Architecture & Dataflow](#1-system-architecture--dataflow)
2. [Codebase File & Module Directory](#2-codebase-file--module-directory)
3. [Mathematical & Physical Formulations](#3-mathematical--physical-formulations)
   - [3.1 Homography Transformation Matrix (H)](#31-homography-transformation-matrix-h)
   - [3.2 2D Perspective Foreshortening Formulation](#32-2d-perspective-foreshortening-formulation)
   - [3.3 Kinematics: Distance & Velocity Estimation](#33-kinematics-distance--velocity-estimation)
   - [3.4 2D Gaussian Kernel Density Estimation (Heatmap)](#34-2d-gaussian-kernel-density-estimation-heatmap)
4. [Machine Learning & Computer Vision Specifications](#4-machine-learning--computer-vision-specifications)
5. [Data Schemas & REST API Endpoints](#5-data-schemas--rest-api-endpoints)
6. [Operational Runbook & Troubleshooting](#6-operational-runbook--troubleshooting)

---

## 1. System Architecture & Dataflow

```text
                                [ Input Video Source ]
                             (Local Upload or YouTube URL)
                                         │
                                         ▼
                            [ Ingestion & Normalization ]
                         - yt-dlp 1080p Mobile Client Bypass
                         - OpenCV / FFmpeg Frame Extractor (30 FPS)
                                         │
                                         ▼
                    ┌────────────────────┴────────────────────┐
                    ▼                                         ▼
        [ Court Geometry Pipeline ]               [ Vision Inference Pipeline ]
      - 12 BWF Perspective Keypoints            - YOLOv8 Person Detection
      - Dynamic Corridor Bounds                 - Referee / Umpire Filter
      - Homography Matrix H Estimation          - Scoreboard EasyOCR (Names & Scores)
                    │                                         │
                    └────────────────────┬────────────────────┘
                                         │
                                         ▼
                            [ Spatial Track Association ]
                         - Relative Spatial Sorting (Near vs Far)
                         - Track Continuity (Euclidean Proximity)
                         - Net Rush ID Persistence (No swapping)
                         - Strict Singles 1v1 Gating (No ghost tracks)
                                         │
                                         ▼
                            [ 2D Coordinate Transformation ]
                         - Project feet bbox to 2D court [0,1]
                         - Temporal Smoothing (Savitzky-Golay)
                                         │
                                         ▼
                            [ Analytics Computation ]
                         - Speed, Distance, Acceleration Profiles
                         - 6-Zone Occupancy Matrix
                         - 2D Gaussian Heatmap Generation
                         - Rally State Machine (Serve, Active, Interval)
                                         │
                                         ▼
                          [ Live Streaming Batches & Store ]
                         - Periodic 8-frame partial batch emit
                         - Final storage/results/{id}_analytics.json
                                         │
                                         ▼
                         [ Next.js 16 Web Application ]
                         - Dual Video & AI Vision Stream
                         - BWF Broadcast Scoreboard HUD
                         - Interactive Top-Down Radar Canvas
                         - Draggable Calibrated Court Grid
```

---

## 2. Codebase File & Module Directory

| File Path | Primary Class / Functions | Description |
|---|---|---|
| `apps/api/main.py` | `FastAPI`, `ingest_youtube_match`, `get_match_analytics`, `create_demo_match` | Primary HTTP server, YouTube downloader, streaming provider |
| `apps/api/storage.py` | `save_partial_analytics`, `get_partial_analytics`, `cleanup_storage` | Thread-safe in-memory and disk analytics storage |
| `apps/worker/worker.py` | `process_video_pipeline`, `process_video_frame_by_frame` | Video processing orchestration, model invocation, batch emission |
| `ml/player_detection/detector.py` | `PlayerDetector`, `is_official_referee`, `detect` | YOLOv8 person detection with 5-rule referee/umpire exclusion |
| `ml/tracking/tracker.py` | `PlayerTracker`, `update`, `_track_court_side` | Multi-player spatial track association and net-rush ID persistence |
| `ml/court_keypoints/detector.py` | `CourtKeypointDetector`, `detect_court_keypoints` | Computes 12 BWF perspective landmarks and optical net line |
| `ml/ocr/scoreboard_reader.py` | `ScoreboardReader`, `extract_player_names_from_frame` | EasyOCR with sponsor blacklist (`HSBC`, `BWF`, `World Tour`) |
| `analytics/movement.py` | `compute_distance_meters`, `compute_speed_profile`, `get_court_zone` | Kinematics, trajectory smoothing, and 6-zone occupancy |
| `analytics/rally.py` | `RallySegmenter`, `segment_rallies` | Finite State Machine for rally active play detection |
| `analytics/heatmap.py` | `generate_player_heatmap` | 2D Gaussian kernel density estimation matrix ($30 \times 60$) |
| `analytics/court.py` | `normalize_court_coordinates`, `compute_homography_matrix` | Perspective-to-planar projective math |
| `apps/web/src/components/VideoPlayerWithRadar.tsx` | `VideoPlayerWithRadar` | Dual video view, 3D BWF mesh, HUD scoreboard, node dragging |
| `apps/web/src/components/RadarCanvas.tsx` | `RadarCanvas` | Canvas-based 2D top-down court, trajectory trails, density map |
| `apps/web/src/components/OverviewCards.tsx` | `OverviewCards` | KPI metrics display with defensive null-safety |
| `apps/web/src/components/PlayerStats.tsx` | `PlayerStats` | Detailed player speed, distance, and 6-zone court grid |
| `apps/web/src/components/RallyTimeline.tsx` | `RallyTimeline` | Rally timeline cards with instant video seek triggers |
| `apps/web/src/lib/api.ts` | `uploadVideo`, `getMatchAnalytics`, `updatePlayerNames` | TypeScript API client with full data contracts |

---

## 3. Mathematical & Physical Formulations

### 3.1 Homography Transformation Matrix ($H$)
To project an arbitrary image point $(u, v)$ from the broadcast perspective to real-world 2D court coordinates $(X, Y) \in [-3.05, 3.05] \times [0, 13.40]\text{ m}$:

$$\begin{bmatrix} X' \\ Y' \\ W \end{bmatrix} = H \begin{bmatrix} u \\ v \\ 1 \end{bmatrix} = \begin{bmatrix} h_{11} & h_{12} & h_{13} \\ h_{21} & h_{22} & h_{23} \\ h_{31} & h_{32} & h_{33} \end{bmatrix} \begin{bmatrix} u \\ v \\ 1 \end{bmatrix}$$

Where normalized 2D coordinates are recovered as:
$$X = \frac{X'}{W}, \quad Y = \frac{Y'}{W}$$

### 3.2 2D Perspective Foreshortening Formulation
Due to the pitch angle $\theta$ of the broadcast camera (typically $18^\circ - 28^\circ$), distances along the longitudinal $Y$-axis undergo geometric foreshortening:

$$y_{\text{screen}} = y_{\text{far}} + \left( \frac{Y_{\text{3D}} / L}{1 + \kappa \cdot (1 - Y_{\text{3D}} / L)} \right) \cdot (y_{\text{near}} - y_{\text{far}})$$

Where:
- $L = 13.40\text{m}$ (Full BWF Court Length)
- $\kappa \approx 2.4 - 3.2$ (Perspective compression factor)
- Optical Center (Badminton Net at $Y = 6.70\text{m}$):
  $$y_{\text{net}} = y_{\text{far}} + 0.20 \cdot (y_{\text{near}} - y_{\text{far}})$$
- Far Short Service Line ($Y = 4.72\text{m}$): $y_{\text{fsl}} = y_{\text{far}} + 0.118 \cdot \Delta y$
- Near Short Service Line ($Y = 8.68\text{m}$): $y_{\text{nsl}} = y_{\text{far}} + 0.317 \cdot \Delta y$

### 3.3 Kinematics: Distance & Velocity Estimation
Trajectory points $p_k = (x_k, y_k)$ at timestamp $t_k$ are smoothed using a temporal window.
- **Euclidean Distance**:
  $$D_{\text{total}} = \sum_{k=1}^{N-1} \sqrt{(X_{k+1} - X_k)^2 + (Y_{k+1} - Y_k)^2}$$
- **Instantaneous Velocity**:
  $$v_k = \frac{\sqrt{(X_{k+1} - X_{k-1})^2 + (Y_{k+1} - Y_{k-1})^2}}{t_{k+1} - t_{k-1}} \quad (\text{m/s})$$

### 3.4 2D Gaussian Kernel Density Estimation (Heatmap)
For a set of $N$ player foot positions $\{ (X_i, Y_i) \}_{i=1}^N$ over the $30 \times 60$ court grid:

$$\mathcal{D}(x, y) = \frac{1}{N \cdot 2\pi \sigma^2} \sum_{i=1}^N \exp\left( -\frac{(x - X_i)^2 + (y - Y_i)^2}{2\sigma^2} \right)$$

---

## 4. Machine Learning & Computer Vision Specifications

### 1. Referee Exclusion Filter Rules
```python
# Far Baseline Line Judges (2-3 seated behind the far court baseline)
if norm_y_bottom < 0.40 or (norm_y_bottom < 0.45 and norm_h < 0.09):
    return True  # Reject line judge

# Main Umpire Chair (Elevated seat near net post)
if (0.42 <= norm_y_bottom <= 0.66) and (norm_x <= 0.24 or norm_x >= 0.76):
    return True  # Reject main umpire

# Service Judge (Low chair opposite net)
if (0.44 <= norm_y_bottom <= 0.62) and (norm_x <= 0.25 or norm_x >= 0.75):
    return True  # Reject service judge

# Dynamic Corridor Constraint
t_y = np.clip((norm_y_bottom - 0.40) / 0.52, 0.0, 1.0)
min_x = 0.26 - 0.16 * t_y
max_x = 0.74 + 0.16 * t_y
if not (min_x <= norm_x <= max_x):
    return True  # Reject off-court staff
```

### 2. Relative Spatial Sorting (Anti-ID-Swap)
When sorting detections on court:
1. `raw_detections.sort(key=lambda d: d["bottom_center"][1])`
2. First entry $\rightarrow$ **Far Player (role="far", P2)**.
3. Last entry $\rightarrow$ **Near Player (role="near", P1)**.
4. When P2 moves to the net, spatial track continuity preserves the trajectory without ID swapping.

---

## 5. Data Schemas & REST API Endpoints

### Analytics JSON Schema (`storage/results/{id}_analytics.json`)
```json
{
  "metadata": {
    "match_id": "demo-f529",
    "filename": "bwf_china_masters_final.mp4",
    "fps": 30.0,
    "total_frames": 900,
    "duration_seconds": 30.0,
    "is_doubles": false
  },
  "overview": {
    "total_rallies": 3,
    "total_shots": 16,
    "active_play_duration_sec": 21.4,
    "total_distance_player_1_m": 84.6,
    "total_distance_player_2_m": 92.1,
    "score_player_1": 1,
    "score_player_2": 1,
    "serving_player_id": 1
  },
  "players": {
    "player_1": { "player_id": 1, "label": "KEAN YEW", "country": "SGP", "distance_meters": 84.6, "avg_speed_mps": 3.12, "max_speed_mps": 6.84 },
    "player_2": { "player_id": 2, "label": "YU QI", "country": "CHN", "distance_meters": 92.1, "avg_speed_mps": 3.45, "max_speed_mps": 7.15 }
  },
  "court_nodes": {
    "top_left": [0.285, 0.442],
    "top_right": [0.715, 0.442],
    "bottom_left": [0.165, 0.895],
    "bottom_right": [0.835, 0.895]
  },
  "rallies": [
    { "rally_id": 1, "start_time": 1.0, "end_time": 8.0, "duration_seconds": 7.0, "estimated_shot_count": 5 }
  ],
  "frame_records": [
    {
      "frame_idx": 0,
      "timestamp": 0.0,
      "players": [
        { "player_id": 1, "label": "KEAN YEW", "x_norm": 0.50, "y_norm": 0.75, "bbox_norm": [0.44, 0.65, 0.56, 0.90] },
        { "player_id": 2, "label": "YU QI", "x_norm": 0.50, "y_norm": 0.25, "bbox_norm": [0.46, 0.42, 0.54, 0.55] }
      ]
    }
  ]
}
```

---

## 6. Operational Runbook & Troubleshooting

### Issue 1: YouTube Bot Login Error (`Sign in to confirm you're not a bot`)
- **Fix**: In `apps/api/main.py`, pass `'extractor_args': {'youtube': {'player_client': ['android', 'ios', 'mweb']}}` with an Android mobile User-Agent.

### Issue 2: Polling Resets Draggable Court Calibration
- **Fix**: In `VideoPlayerWithRadar.tsx`, use `userHasEditedNodesRef.current = true` on `handlePointerDown`. Polling effects check `!userHasEditedNodesRef.current` before overwriting.

### Issue 3: Next.js Runtime TypeError (`Cannot read properties of undefined (reading 'map')`)
- **Fix**: Apply defensive array checks in `RallyTimeline.tsx`: `const safeRallies = Array.isArray(rallies) ? rallies : []`.

### Issue 4: Python NameError (`Dict` or `Any` not defined)
- **Fix**: Ensure `from typing import List, Optional, Dict, Any` is imported at the top of `apps/api/main.py`.
