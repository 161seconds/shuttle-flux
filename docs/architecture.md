# System Architecture

## Component Interaction

```text
+-------------------+        +--------------------+
|  Web Client       | -----> |  FastAPI Backend   |
|  (Next.js / React)|        |  (Job Management)  |
+-------------------+        +--------------------+
                                       |
                                       v
                               +----------------+
                               |  Redis Queue   |
                               +----------------+
                                       |
                                       v
+-------------------------------------------------------------+
|                      Async Video Worker                     |
|                                                             |
| 1. Video Ingestion & Metadata (FFmpeg/OpenCV)               |
| 2. Court Detection & Homography (YOLO Pose -> 2D Court)     |
| 3. Player Detection & Tracking (YOLO + ByteTrack)           |
| 4. Shuttlecock Trajectory Recovery (Temporal State Machine) |
| 5. Analytics Engine (Movement, Rallies, Hits, Heatmaps)     |
| 6. Rendering Engine (Video Overlays & Top-down Radar View)  |
+-------------------------------------------------------------+
```
