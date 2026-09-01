# Badminton AI Analytics — Product Blueprint & Roadmap

> **Mục tiêu:** xây dựng một sản phẩm AI phân tích video cầu lông từ video trận đấu, tự động phát hiện người + cầu + sân, tracking theo thời gian, chuyển tọa độ camera sang mặt sân 2D, rồi sinh ra thống kê và insight có thể xem trên web.
>
> **Nguồn cảm hứng kiến trúc:** Roboflow Football AI Tutorial — object detection, tracking, player/team identification, court/pitch keypoints, homography, top-down view và advanced sports analytics. Video gốc: https://www.youtube.com/watch?v=aBVGKoNZQUw
>
> **Triết lý build:** làm MVP chạy end-to-end trước, sau đó tăng độ chính xác; không cố train mọi thứ ngay từ đầu.

---

## 0. Executive Summary

### Sản phẩm cuối cùng nên làm được

Người dùng upload một video cầu lông → hệ thống xử lý → trả về:

1. Video có bounding box + tracking ID.
2. Sân cầu lông được nhận diện và overlay.
3. Hai người chơi được tracking ổn định.
4. Quỹ đạo cầu được hiển thị.
5. Màn hình top-down 2D mô phỏng vị trí người/cầu.
6. Thống kê từng người chơi.
7. Heatmap di chuyển.
8. Rally timeline.
9. Ước lượng số lần đánh / rally.
10. Điểm chạm hoặc vùng cầu rơi nếu model đủ tốt.
11. Một số insight chiến thuật.
12. Trang dashboard để xem lại từng rally và từng đoạn video.

### Kiến trúc tổng quát

```text
                    ┌───────────────────────┐
                    │       Web Client      │
                    │ React / Next.js       │
                    └───────────┬───────────┘
                                │
                                │ upload / query
                                ▼
                    ┌───────────────────────┐
                    │       FastAPI         │
                    │ REST API + Auth       │
                    └───────────┬───────────┘
                                │
                   create processing job
                                ▼
             ┌──────────────────────────────────┐
             │        Async Video Worker        │
             │ Python + CV/ML pipeline          │
             └────────────────┬─────────────────┘
                              │
            ┌─────────────────┼─────────────────────┐
            │                 │                     │
            ▼                 ▼                     ▼
      Player detector   Shuttle detector     Court keypoints
          YOLO                YOLO             YOLO Pose / keypoints
            │                 │                     │
            └──────────┬──────┴────────────┬────────┘
                       ▼                   ▼
                   Tracking           Homography
                  ByteTrack          image → court
                       │                   │
                       └─────────┬─────────┘
                                 ▼
                         Analytics Engine
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
          Movement            Rally             Shot / Event
           Metrics           Analysis            Analysis
              │                  │                  │
              └──────────────────┼──────────────────┘
                                 ▼
                         Results / JSON / DB
                                 │
                                 ▼
                           Dashboard UI
```

---

# 1. Product Scope

## 1.1 Target user

Bản đầu tiên nên nhắm tới:

- người chơi cầu lông phong trào;
- HLV / coach;
- CLB cầu lông;
- sinh viên muốn phân tích trận đấu;
- người làm sports-tech demo / portfolio.

Không nên nhắm ngay tới broadcast-grade analytics hoặc hệ thống trọng tài chính thức.

## 1.2 Input

Hỗ trợ trước:

- MP4
- MOV
- 720p / 1080p
- camera cố định hoặc tương đối ổn định
- single court
- singles trước, doubles sau

Khuyến nghị cho MVP:

```text
Resolution: 1080p
FPS: 30 hoặc 60
Camera: cố định
Camera placement: cuối sân hoặc bên hông nhưng nhìn thấy phần lớn sân
Một trận / một court / ít vật cản
```

## 1.3 Output

### Video analytics

- player bbox
- player ID
- shuttle bbox / center point
- court lines / keypoints
- transformed player position
- transformed shuttle position
- trajectory
- event markers

### Statistics

- total video duration
- active play duration
- number of rallies
- rally duration
- player distance
- average speed
- max speed
- movement heatmap
- court coverage
- left/right/front/back occupancy
- estimated shot count
- shot direction / landing zone nếu đủ dữ liệu

### UX

```text
Upload
  ↓
Processing
  ↓
Results
  ├── Overview
  ├── Video
  ├── Court Map
  ├── Player Stats
  ├── Rally Timeline
  └── Heatmap
```

---

# 2. Tech Stack

## 2.1 Computer Vision / ML

| Thành phần | Công nghệ đề xuất | Vai trò |
|---|---|---|
| Language | Python | ML/CV pipeline |
| DL framework | PyTorch | train/inference |
| Object detection | Ultralytics YOLO | player/shuttle detection |
| Keypoint detection | YOLO Pose / YOLO keypoints | court landmarks |
| Tracking | ByteTrack | player tracking |
| Video processing | OpenCV | frames, geometry, codecs |
| Detection utilities | Supervision | annotation, tracking integration, visualization |
| Numerical | NumPy | geometry, vectors, interpolation |
| Data analysis | Pandas | metrics / exports |
| Experimentation | Jupyter / Google Colab | training & experiments |
| Dataset tooling | Roboflow hoặc CVAT | annotation/versioning |
| Optional embeddings | SigLIP / CLIP | player appearance if needed |
| Optional dimensionality reduction | UMAP | visualization / clustering |
| Optional clustering | K-Means | team/appearance clustering |

## 2.2 Backend

Khuyến nghị:

```text
FastAPI
SQLAlchemy
PostgreSQL
Redis
Celery hoặc worker queue tương đương
S3-compatible object storage
FFmpeg
```

Vai trò:

- FastAPI: REST API.
- PostgreSQL: metadata + analytics results.
- Redis: queue/cache/job state.
- Worker: chạy inference, tracking, analytics.
- Object storage: lưu video gốc, video output, thumbnails.
- FFmpeg: chuẩn hóa video, extract metadata, encode output.

## 2.3 Frontend

Khuyến nghị:

```text
Next.js / React
TypeScript
Tailwind CSS
Chart library
HTML5 video
Canvas hoặc SVG overlay
```

Dashboard cần đồng bộ:

```text
video timestamp
↔
analytics timestamp
↔
player position
↔
shuttle position
↔
rally/event marker
```

## 2.4 Deployment

### Giai đoạn đầu

```text
Frontend: Vercel hoặc static hosting
Backend: cloud VM/container
Worker: GPU VM
Database: managed PostgreSQL
Storage: S3-compatible
```

### Giai đoạn production

```text
Frontend
    ↓
API service
    ↓
Job queue
    ↓
GPU workers
    ↓
Object storage + PostgreSQL
```

---

# 3. Tool nào trong Football AI được giữ / bỏ / thay?

## 3.1 Giữ nguyên

### Python

Giữ nguyên.

### YOLO

Giữ nguyên kiến trúc; train lại dataset badminton.

### ByteTrack

Giữ nguyên cho player tracking.

### OpenCV

Giữ nguyên.

### NumPy

Giữ nguyên.

### Supervision

Giữ nguyên hoặc dùng mạnh hơn cho video annotation/tracking.

### Homography

Giữ nguyên và trở thành thành phần cốt lõi.

### Keypoint detection

Giữ nguyên ý tưởng nhưng chuyển từ football pitch landmarks sang badminton court landmarks.

## 3.2 Có thể bỏ ở MVP

### SigLIP + UMAP + K-Means

Football cần chia player thành team A/B. Badminton singles không cần.

Doubles mới cân nhắc.

### Voronoi / pitch control

Có thể làm phase nâng cao, không phải MVP.

## 3.3 Thêm mới cho badminton

### Rally detection

Xác định khoảng thời gian một rally bắt đầu/kết thúc.

### Shot event detection

Xác định thời điểm người chơi đánh cầu.

### Shot classification

Phân loại:

- serve
- clear
- drop
- smash
- drive
- net shot
- lift
- block / defensive shot

### Shuttle trajectory recovery

Không chỉ detect shuttle từng frame mà cần nối thành trajectory liên tục, có xử lý missing detections.

---

# 4. Bài toán AI cần giải

## 4.1 Problem A — Player Detection

### Input

Frame từ video.

### Output

```json
{
  "class": "player",
  "bbox": [x1, y1, x2, y2],
  "confidence": 0.94
}
```

### Dataset

Annotate class:

```text
player
```

Cho doubles:

```text
player
```

Không cần encode team trong object detection model nếu team assignment xử lý hậu kỳ.

---

# 5. Problem B — Shuttlecock Detection

Đây là một trong các bài toán khó nhất.

## Vì sao?

- shuttle rất nhỏ;
- chuyển động cực nhanh;
- motion blur;
- có thể bị khuất;
- nền sân và đèn làm contrast thay đổi;
- nhiều frame không thấy cầu rõ;
- có thể xuất hiện false positive.

Sports ball tracking nói chung gặp đúng các vấn đề như vật thể nhỏ, hình dáng giống các vật khác và điều kiện ánh sáng thay đổi. citeturn166320search6

## Strategy

Không ép hệ thống phải detect shuttle ở 100% frame.

Thiết kế pipeline:

```text
YOLO detection
      ↓
confidence filtering
      ↓
temporal association
      ↓
tracking / Kalman / interpolation
      ↓
trajectory smoothing
```

### MVP target

> ưu tiên trajectory hợp lý hơn là detection hoàn hảo từng frame.

---

# 6. Problem C — Court Detection

## Mục tiêu

Tìm các landmark của sân.

Ví dụ dataset có thể label:

```text
court_corner_top_left
court_corner_top_right
court_corner_bottom_left
court_corner_bottom_right
net_left
net_right
service_line_* 
center_line_*
```

Không nhất thiết phải dùng toàn bộ ngay từ đầu.

## MVP tối thiểu

Có thể bắt đầu với 4–6 điểm đủ ổn định để thiết lập homography.

## Better version

Dùng nhiều landmark hơn để:

- kiểm tra consistency;
- xử lý camera thay đổi nhẹ;
- xác định đường biên;
- phát hiện lỗi calibration.

Roboflow dùng keypoint detection để tìm các landmark của sân rồi dùng chúng làm source/target points cho homography; cùng ý tưởng đó có thể chuyển sang badminton court. citeturn166320search4

---

# 7. Problem D — Perspective Transformation / Homography

## Input

Điểm trên image:

```text
src_points = [
    p1,
    p2,
    p3,
    p4
]
```

Điểm tương ứng trên mặt sân:

```text
target_points = [
    q1,
    q2,
    q3,
    q4
]
```

## Output

Một matrix homography `H`.

```text
image coordinate
       ↓
       H
       ↓
real court coordinate
```

Homography là geometric transformation dùng để map các điểm từ một mặt phẳng sang mặt phẳng khác và sửa distortion do perspective. citeturn166320search4

## Vì sao cần?

Không thể lấy:

```text
pixel distance = real distance
```

một cách đơn giản.

Ví dụ 50 px gần camera và 50 px xa camera không đại diện cùng một khoảng cách ngoài đời.

Sau homography, ta mới có thể tính metrics trên mặt sân.

---

# 8. Court Coordinate System

Chọn một coordinate system cố định.

Ví dụ:

```text
x = 0 → chiều ngang sân
x = court_width → chiều ngang đối diện

y = 0 → baseline phía player A
 y tăng → phía player B
```

Normalize thêm:

```text
x_norm ∈ [0, 1]
y_norm ∈ [0, 1]
```

Điều này giúp analytics độc lập hơn với resolution video.

---

# 9. Player Tracking

## Pipeline

```text
YOLO Player Detection
        ↓
Detection boxes
        ↓
ByteTrack
        ↓
Player ID
        ↓
Temporal trajectory
```

Video football tutorial dùng tracker ID để duy trì identity của objects qua các frame. citeturn166320search0turn166320search2

## Player position

Không nên dùng center của bbox một cách mù quáng.

Cho player trên sân, ưu tiên:

```text
bottom-center of bbox
```

vì điểm đó gần với vị trí chân tiếp xúc mặt sân hơn.

```text
bbox
┌─────────────┐
│      P      │
│             │
│             │
└──────●──────┘
       ↑
 bottom-center
```

---

# 10. Shuttle Tracking

## Basic

Mỗi frame:

```text
shuttle_center = (cx, cy)
```

## Temporal tracker

Mỗi object có:

```text
frame_id
time
x
y
confidence
visible
```

## Missing frames

Không nên bỏ trajectory ngay khi mất cầu.

Dùng state machine:

```text
DETECTED
   ↓
TEMPORARILY_MISSING
   ↓
RECOVERED
```

Nếu mất quá lâu:

```text
LOST
```

Sau đó bắt đầu trajectory segment mới.

---

# 11. Rally Segmentation

Đây là feature cực quan trọng đối với badminton.

## Định nghĩa

Một rally:

```text
serve / hit begins
        ↓
multiple exchanges
        ↓
shuttle becomes dead / point ends
```

## Ban đầu có thể dùng heuristic

Features:

- shuttle velocity;
- shuttle visibility;
- player movement;
- distance shuttle-player;
- pause duration;
- audio peak (optional);
- scoreboard OCR (optional).

## State machine

```text
IDLE
 ↓
RALLY_START
 ↓
ACTIVE
 ↓
RALLY_END
 ↓
IDLE
```

## Sau này

Train sequence/event model trên window temporal thay vì chỉ dựa threshold.

---

# 12. Hit Detection

Mục tiêu:

> tìm frame mà player vừa chạm / đánh shuttle.

## Signals

Có thể kết hợp:

```text
Distance(player, shuttle)
+
Shuttle velocity change
+
Shuttle direction change
+
Player racket/arm motion
```

## MVP heuristic

Một candidate hit khi:

```text
shuttle close to player
AND
velocity vector changes significantly
```

Đây chỉ là heuristic; không nên gọi nó là ground truth.

---

# 13. Shot Classification

## Phase 1 — Rule-based baseline

Dựa trên trajectory:

```text
shuttle height / estimated arc
landing region
velocity
net proximity
trajectory direction
```

Có thể classify thô:

```text
serve
clear
smash
net
```

## Phase 2 — Supervised model

Dataset:

```text
clip around hit event
        ↓
label shot type
```

Input features:

- player position;
- shuttle position;
- shuttle velocity;
- shuttle acceleration;
- trajectory curvature;
- hit position;
- landing position;
- temporal window.

Model options:

```text
MLP
Random Forest
XGBoost
1D CNN
LSTM / GRU
Temporal Transformer
```

Không cần nhảy thẳng vào Transformer.

---

# 14. Movement Analytics

Sau khi có player position trên court coordinates:

## Distance

```text
D = Σ distance(p_t, p_t-1)
```

## Average speed

```text
average_speed = total_distance / active_time
```

## Maximum speed

Dùng smoothing trước khi tính để tránh noise.

## Acceleration

```text
v_t = distance / dt
 a_t = (v_t - v_t-1) / dt
```

## Court coverage

Có thể chia sân thành grid:

```text
┌────┬────┬────┬────┐
│    │    │    │    │
├────┼────┼────┼────┤
│    │    │    │    │
├────┼────┼────┼────┤
│    │    │    │    │
└────┴────┴────┴────┘
```

Tính:

- time per zone;
- visit frequency;
- transition between zones.

---

# 15. Heatmap

Input:

```text
player court coordinates over time
```

Output:

```text
2D density map
```

Frontend có thể render:

- static heatmap;
- heatmap theo rally;
- heatmap comparison A vs B.

---

# 16. Top-down Radar View

Đây là feature nên có vì rất trực quan.

## Input

```text
player positions
shuttle position
court geometry
```

## Output

```text
Top-down badminton court
+ Player A
+ Player B
+ Shuttle
+ trajectories
```

Football tutorial sử dụng keypoints + homography để tạo tactical/radar view từ góc camera. citeturn166320search0turn166320search2

---

# 17. Analytics Engine

Thiết kế analytics engine tách khỏi detector.

```text
raw detections
      ↓
normalized tracking data
      ↓
analytics engine
```

Không để logic thống kê nằm trong code model.

## Data model tối thiểu

```json
{
  "frame": 1234,
  "timestamp": 41.13,
  "players": [
    {
      "id": 1,
      "x": 2.31,
      "y": 4.72,
      "confidence": 0.97
    },
    {
      "id": 2,
      "x": 5.91,
      "y": 7.21,
      "confidence": 0.95
    }
  ],
  "shuttle": {
    "x": 4.2,
    "y": 5.3,
    "visible": true,
    "confidence": 0.82
  }
}
```

---

# 18. Database Design

## `users`

```text
id
email
password_hash / auth_provider
created_at
```

## `matches`

```text
id
user_id
name
sport
mode
status
video_url
result_url
duration
created_at
```

## `processing_jobs`

```text
id
match_id
status
progress
stage
error_message
started_at
completed_at
```

## `players`

```text
id
match_id
tracking_id
label
metadata
```

## `player_metrics`

```text
id
match_id
player_id
distance
avg_speed
max_speed
coverage
active_time
```

## `rallies`

```text
id
match_id
index
start_time
end_time
duration
winner_player_id
confidence
```

## `shots`

```text
id
rally_id
player_id
time
shot_type
hit_x
hit_y
landing_x
landing_y
confidence
```

## `trajectory_points`

```text
id
match_id
frame
timestamp
player_id
object_type
x_image
y_image
x_court
y_court
confidence
```

Lưu dữ liệu lớn theo file/Parquet nếu cần; database không nhất thiết phải chứa mọi frame của mọi video khi scale lên.

---

# 19. API Design

## Upload

```http
POST /api/v1/matches
```

Multipart upload.

## Get match

```http
GET /api/v1/matches/{matchId}
```

## Processing status

```http
GET /api/v1/matches/{matchId}/processing
```

Response:

```json
{
  "status": "processing",
  "progress": 67,
  "stage": "shuttle_tracking"
}
```

## Match analytics

```http
GET /api/v1/matches/{matchId}/analytics
```

## Rally list

```http
GET /api/v1/matches/{matchId}/rallies
```

## Rally detail

```http
GET /api/v1/rallies/{rallyId}
```

## Player stats

```http
GET /api/v1/matches/{matchId}/players/{playerId}/stats
```

---

# 20. Frontend UX

## Page 1 — Landing

Hiển thị:

- product value proposition;
- demo video;
- supported format;
- CTA upload.

## Page 2 — Upload

```text
Drag & Drop Video

or

Select File
```

Hiển thị:

- file size;
- duration;
- resolution;
- estimated processing status.

## Page 3 — Processing

Pipeline progress:

```text
✓ Upload
✓ Video preprocessing
✓ Player detection
✓ Player tracking
→ Shuttle tracking
○ Court calibration
○ Analytics
○ Rendering
```

## Page 4 — Match Overview

Cards:

```text
Duration
Rallies
Shots
Distance P1
Distance P2
```

## Page 5 — Video Analytics

Video bên trái.

Overlay:

```text
Player #1
Player #2
Shuttle
Court lines
Trajectory
Event markers
```

## Page 6 — Radar View

Bên cạnh video:

```text
Top-down court
```

Khi user kéo video:

```text
video timestamp
       ↕
rader timestamp
```

## Page 7 — Player Analytics

Charts:

- distance over time;
- speed over time;
- court heatmap;
- zone occupancy;
- rally participation.

## Page 8 — Rally Explorer

```text
Rally #1   08.3s
Rally #2   12.1s
Rally #3   05.7s
...
```

Click rally → video seek tới đúng timestamp.

---

# 21. AI Model Architecture

## Model 1 — Player Detector

```text
Input frame
   ↓
YOLO
   ↓
player bbox
```

## Model 2 — Shuttle Detector

```text
Input frame / crop
   ↓
YOLO
   ↓
shuttle bbox
```

Có thể tách riêng model shuttle để tối ưu resolution/context.

## Model 3 — Court Keypoints

```text
frame
  ↓
YOLO Pose / keypoint model
  ↓
court landmarks
```

## Tracking

```text
player detections → ByteTrack
shuttle detections → custom temporal tracker / tracker phù hợp
```

## Analytics

Không phải neural network ở phase đầu.

```text
tracking data
   ↓
physics / geometry / heuristics
   ↓
statistics
```

Đây là cách giảm độ phức tạp.

---

# 22. Dataset Strategy

## 22.1 Không train trước khi biết dataset cần gì

Quy trình:

```text
Collect videos
   ↓
Inspect camera conditions
   ↓
Define classes / keypoints
   ↓
Annotate
   ↓
Split train/val/test
   ↓
Train baseline
   ↓
Error analysis
   ↓
Add hard examples
   ↓
Retrain
```

## 22.2 Data diversity

Cần có:

- nhiều camera angle;
- indoor/outdoor nếu sản phẩm muốn support cả hai;
- sáng/tối;
- sân khác màu;
- áo khác màu;
- người khác nhau;
- singles;
- doubles sau này;
- motion blur;
- shuttle gần và xa camera;
- occlusion.

## 22.3 Data split

Không split random frame từ cùng một video vào train và validation.

Đúng hơn:

```text
Video A → train
Video B → train
Video C → validation
Video D → test
```

Nếu lấy frame cùng một trận cho cả train/test, metrics dễ bị ảo.

---

# 23. Annotation Specification

## Player

Bounding box tight quanh người.

## Shuttle

BBox càng chính xác càng tốt.

Nếu quá nhỏ, cân nhắc annotation center point / keypoint.

## Court

Mỗi keypoint phải có ID cố định.

Ví dụ:

```text
0 = top-left singles/boundary point
1 = top-right
2 = bottom-left
3 = bottom-right
4 = net-left
5 = net-right
...
```

Không thay đổi thứ tự keypoint giữa các ảnh.

---

# 24. Evaluation Metrics

## Object Detection

Theo dõi:

- precision
- recall
- mAP50
- mAP50-95

mAP là một metric phổ biến để benchmark object detection và cũng được dùng trong workflow của tutorial. citeturn166320search3

## Tracking

Cần thêm:

- ID switches
- track fragmentation
- IDF1 / HOTA nếu pipeline evaluation hỗ trợ.

## Shuttle

Ngoài mAP, quan tâm:

- percentage of frames detected;
- average position error;
- trajectory continuity;
- false positive rate.

## Homography

So sánh:

```text
predicted court point
vs
manually annotated court point
```

## Analytics

Đánh giá bằng ground-truth sample:

```text
predicted distance
vs
manual/reference distance
```

---

# 25. Confidence System

Không hiển thị số liệu như sự thật tuyệt đối.

Mỗi analytics result nên có:

```text
value
confidence
source
```

Ví dụ:

```json
{
  "shot_type": "smash",
  "confidence": 0.76,
  "source": "model_v2"
}
```

UI có thể nói:

> Estimated smash: 76% confidence

thay vì:

> Smash chắc chắn 100%.

---

# 26. Processing Pipeline Chi Tiết

```text
1. Upload
   ↓
2. Validate file
   ↓
3. Extract metadata
   ↓
4. Normalize FPS/resolution
   ↓
5. Decode frames
   ↓
6. Court detection
   ↓
7. Player detection
   ↓
8. Shuttle detection
   ↓
9. Player tracking
   ↓
10. Shuttle trajectory reconstruction
   ↓
11. Court homography
   ↓
12. Convert all coordinates
   ↓
13. Smooth trajectories
   ↓
14. Detect rally segments
   ↓
15. Detect hit events
   ↓
16. Estimate shot type
   ↓
17. Calculate player metrics
   ↓
18. Calculate heatmaps
   ↓
19. Generate radar data
   ↓
20. Generate annotated video
   ↓
21. Save JSON/DB results
   ↓
22. Update processing status
   ↓
23. Frontend reads results
```

---

# 27. Video Processing Architecture

Không xử lý video nặng bên request thread của FastAPI.

Sai:

```text
POST /upload
   ↓
FastAPI
   ↓
run YOLO for 20 minutes
   ↓
response
```

Đúng:

```text
POST /upload
   ↓
create job
   ↓
return job_id

worker
   ↓
process video
   ↓
update progress
```

## Job status

```text
QUEUED
PROCESSING
COMPLETED
FAILED
CANCELLED
```

## Pipeline stages

```text
preprocessing
player_detection
shuttle_detection
tracking
court_mapping
analytics
rendering
uploading
```

---

# 28. Storage Strategy

## Original video

Object storage.

## Processed video

Object storage.

## Frames

Không cần lưu toàn bộ frame vĩnh viễn trong DB.

## Analytics

JSON / Parquet.

## Database

Metadata + summaries + queryable events.

---

# 29. Caching

Khi user mở match nhiều lần:

Không chạy model lại.

```text
video hash
model version
pipeline version
```

Có thể dùng chúng làm processing fingerprint:

```text
hash(video)
+
model_version
+
pipeline_version
```

Nếu đã có result → trả result cũ.

---

# 30. Model Versioning

Mọi result phải biết model nào tạo ra nó.

```text
player_detector = player-v3
shuttle_detector = shuttle-v5
court_model = court-v2
analytics_version = analytics-v4
```

Không overwrite model version trong result cũ.

Điều này cực kỳ quan trọng khi sau này retrain.

---

# 31. Experiments Folder Structure

```text
badminton-ai/
│
├── apps/
│   ├── api/
│   ├── worker/
│   └── web/
│
├── ml/
│   ├── player_detection/
│   ├── shuttle_detection/
│   ├── court_keypoints/
│   ├── tracking/
│   └── shot_classification/
│
├── analytics/
│   ├── movement.py
│   ├── rally.py
│   ├── shots.py
│   ├── heatmap.py
│   └── court.py
│
├── pipelines/
│   ├── preprocess.py
│   ├── detect.py
│   ├── track.py
│   ├── calibrate.py
│   ├── analyze.py
│   └── render.py
│
├── datasets/
│   ├── README.md
│   └── configs/
│
├── notebooks/
│   ├── player_training.ipynb
│   ├── shuttle_training.ipynb
│   ├── court_keypoints.ipynb
│   └── analytics_validation.ipynb
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── infra/
│   ├── docker/
│   └── deployment/
│
├── docs/
│
└── README.md
```

---

# 32. Development Principles

## Principle 1 — Separate detection from analytics

Model chỉ tạo observations.

Analytics engine tạo conclusions.

## Principle 2 — Save raw predictions

Luôn có cách debug:

```text
raw detection
→ tracked data
→ transformed data
→ analytics
```

## Principle 3 — Every feature must be measurable

Ví dụ:

Không nói:

> tracking khá tốt.

Mà nói:

> ID switches / 10 minutes = X.

## Principle 4 — Build with confidence scores

Không che giấu uncertainty.

## Principle 5 — Dataset quality > fancy model

Thêm hard examples thường hữu ích hơn việc đổi model liên tục.

---

# 33. MVP Definition

MVP chưa cần:

- shot classification đầy đủ;
- doubles team classification;
- audio analysis;
- OCR scoreboard;
- tactical AI chatbot;
- player pose 3D;
- prediction engine.

MVP bắt buộc có:

```text
[ ] upload video
[ ] process asynchronously
[ ] detect players
[ ] track players
[ ] detect shuttle
[ ] track shuttle trajectory cơ bản
[ ] detect court
[ ] homography
[ ] top-down view
[ ] distance
[ ] speed
[ ] heatmap
[ ] rally segmentation cơ bản
[ ] dashboard
[ ] annotated video
```

---

# 34. Roadmap Tổng Thể

## Phase 0 — Product Definition

### Mục tiêu

Chốt exactly product làm gì.

### Tasks

```text
[ ] Define target user
[ ] Define supported camera
[ ] Define supported video format
[ ] Define singles/doubles scope
[ ] Define MVP analytics
[ ] Create architecture
[ ] Define dataset schema
[ ] Define API contract
```

### Output

```text
PRD
Architecture diagram
Data schema
API draft
Annotation guideline
```

---

# Phase 1 — Video Infrastructure

### Mục tiêu

Có pipeline video chạy ổn định chưa cần AI.

### Tasks

```text
[ ] Upload video
[ ] Validate file
[ ] Extract FPS/resolution/duration
[ ] FFmpeg normalization
[ ] Extract frames
[ ] Save output
[ ] Generate thumbnails
[ ] Async job
[ ] Progress reporting
[ ] Error handling
```

### Acceptance Criteria

- Upload được video.
- Job không block API.
- Worker xử lý video.
- User xem progress.
- Result video được lưu.

---

# Phase 2 — Player Detection

### Mục tiêu

Detect player chính xác.

### Tasks

```text
[ ] Collect player videos
[ ] Annotate player bbox
[ ] Train baseline YOLO
[ ] Evaluate
[ ] Inspect false positives
[ ] Add hard examples
[ ] Retrain
[ ] Export model
[ ] Build inference module
```

### Acceptance Criteria

Trên test videos:

- player detection ổn định trong camera conditions mục tiêu;
- false positive chấp nhận được;
- inference speed đủ để batch process.

Không cần ép real-time ở phase này.

---

# Phase 3 — Player Tracking

### Mục tiêu

Mỗi player có ID ổn định.

### Tasks

```text
[ ] Integrate ByteTrack
[ ] Tune detection threshold
[ ] Tune tracker threshold
[ ] Handle temporary occlusion
[ ] Validate ID consistency
[ ] Create trajectory output
```

### Acceptance Criteria

```text
Player A → mostly ID 1
Player B → mostly ID 2
```

Không reset ID lung tung khi hai người đi gần nhau.

---

# Phase 4 — Shuttle Detection

### Mục tiêu

Detect shuttle.

### Tasks

```text
[ ] Collect difficult shuttle footage
[ ] Annotate shuttle
[ ] Decide bbox vs point annotation
[ ] Train high-resolution detector
[ ] Evaluate small-object performance
[ ] Add hard negatives
[ ] Optimize inference
```

### Acceptance Criteria

Trajectory nhìn bằng mắt phải hợp lý trên các sample test.

---

# Phase 5 — Shuttle Tracking

### Mục tiêu

Biến detection rời rạc thành trajectory.

### Tasks

```text
[ ] Temporal association
[ ] Velocity estimation
[ ] Missing detection handling
[ ] Interpolation
[ ] Smoothing
[ ] Lost/recovered state
[ ] Trajectory visualization
```

### Acceptance Criteria

- giảm các đoạn trajectory nhảy lung tung;
- missing frames không phá toàn bộ rally;
- đường đi phù hợp với chuyển động thực tế trên sample.

---

# Phase 6 — Court Keypoint Detection

### Mục tiêu

Tự động hiểu geometry của sân.

### Tasks

```text
[ ] Define keypoint schema
[ ] Annotate court landmarks
[ ] Train keypoint model
[ ] Evaluate keypoint error
[ ] Add perspective diversity
```

### Acceptance Criteria

Court landmarks đủ chính xác để homography không làm player nhảy vị trí bất thường.

---

# Phase 7 — Homography

### Mục tiêu

Mapping image → court plane.

### Tasks

```text
[ ] Define court dimensions
[ ] Establish target coordinates
[ ] Compute H
[ ] Transform player points
[ ] Transform shuttle points
[ ] Validate overlay
[ ] Detect calibration failure
```

### Acceptance Criteria

Khi vẽ court lines lên video:

```text
video court lines
≈
virtual court lines
```

---

# Phase 8 — Top-down View

### Mục tiêu

Tạo radar view.

### Tasks

```text
[ ] Build badminton court renderer
[ ] Map players
[ ] Map shuttle
[ ] Map trajectories
[ ] Sync timeline
[ ] Add play/pause/seek
```

### Acceptance Criteria

Video và radar view đồng bộ frame/time.

---

# Phase 9 — Movement Analytics

### Tasks

```text
[ ] Distance
[ ] Speed
[ ] Max speed
[ ] Acceleration
[ ] Court coverage
[ ] Zone occupancy
[ ] Heatmap
```

### Acceptance Criteria

Analytics không có spike vô lý do detection noise.

---

# Phase 10 — Rally Segmentation

### Tasks

```text
[ ] Define rally start
[ ] Define rally end
[ ] Implement heuristics
[ ] Validate manually
[ ] Store rally segments
[ ] Build rally browser
```

### Acceptance Criteria

Người dùng click rally → video seek đúng đoạn.

---

# Phase 11 — Hit Detection

### Tasks

```text
[ ] Detect proximity player-shuttle
[ ] Detect shuttle velocity changes
[ ] Detect direction changes
[ ] Combine features
[ ] Manual evaluation
```

---

# Phase 12 — Shot Classification

### Start with

```text
serve
clear
smash
drop
net
```

### Steps

```text
[ ] Collect labeled shot clips
[ ] Define temporal window
[ ] Build feature extractor
[ ] Train baseline classifier
[ ] Evaluate confusion matrix
[ ] Add difficult examples
[ ] Retrain
```

---

# Phase 13 — Product Dashboard

### Tasks

```text
[ ] Auth
[ ] Upload page
[ ] Processing page
[ ] Match detail page
[ ] Video analytics player
[ ] Radar view
[ ] Player stats
[ ] Heatmap
[ ] Rally timeline
[ ] Error states
```

---

# Phase 14 — Production Hardening

### Tasks

```text
[ ] Authentication
[ ] Authorization
[ ] Rate limit
[ ] Upload size limit
[ ] File type validation
[ ] Queue retry
[ ] Idempotent processing
[ ] Logging
[ ] Metrics
[ ] Error tracking
[ ] Model versioning
[ ] Storage cleanup
[ ] Backup
```

---

# 35. Recommended Sprint Plan

## Sprint 1

```text
Product architecture
Video upload
FastAPI
Worker
Storage
Basic frontend
```

Output:

> user upload video → job → processed video.

## Sprint 2

```text
Player dataset
Player YOLO
Inference
```

Output:

> video có player boxes.

## Sprint 3

```text
ByteTrack
Trajectory
Player analytics base
```

Output:

> player IDs + movement trajectory.

## Sprint 4

```text
Shuttle dataset
Shuttle YOLO
```

Output:

> shuttle detection.

## Sprint 5

```text
Shuttle tracker
Trajectory smoothing
```

Output:

> shuttle path.

## Sprint 6

```text
Court keypoints
Homography
```

Output:

> player positions mapped to court.

## Sprint 7

```text
Radar view
Heatmap
Distance
Speed
```

Output:

> actual analytics dashboard.

## Sprint 8

```text
Rally detection
Rally viewer
```

## Sprint 9

```text
Hit detection
Shot classification baseline
```

## Sprint 10

```text
Polish
Testing
Deployment
Demo
Documentation
```

---

# 36. AI-Assisted Development Workflow

Mục tiêu là dùng AI như một engineering copilot, không để AI tự quyết architecture không kiểm soát.

## Step 1 — Đưa cho AI tài liệu này

AI cần biết:

```text
product scope
architecture
folder structure
API contract
data schemas
acceptance criteria
```

## Step 2 — Chia task nhỏ

Không prompt:

> Build toàn bộ badminton AI.

Dùng:

> Implement player detection inference module based on this interface.

Sau đó:

> Write tests for player detection result normalization.

Sau đó:

> Integrate module into worker pipeline.

## Step 3 — Mỗi feature phải có

```text
implementation
unit tests
integration tests
README update
error handling
logging
```

## Step 4 — AI phải review output của chính nó

Prompt pattern:

```text
Review this implementation against:
1. requirements
2. architecture
3. edge cases
4. performance
5. testability
6. security
Do not rewrite everything. Identify concrete defects first.
```

## Step 5 — AI cho ML

Dùng AI để:

- generate training scripts;
- inspect errors;
- suggest augmentation;
- create evaluation scripts;
- plot metrics;
- explain false positives;
- generate dataset tooling;
- refactor inference pipeline.

Không giao cho AI quyền tuyên bố model chính xác nếu chưa có evaluation.

---

# 37. Prompt Templates cho AI Coding

## Architecture

```text
You are a senior computer vision engineer.

Read the project specification before coding.

Goal:
Implement <FEATURE>.

Constraints:
- Python
- FastAPI/worker architecture
- typed interfaces
- testable modules
- no business logic inside API route
- model inference must be replaceable

Deliver:
1. implementation
2. tests
3. error handling
4. logging
5. usage example
6. architecture notes
```

## Debug ML

```text
Analyze this detection/tracking failure.

Input:
- video conditions
- model confidence
- wrong predictions
- expected behavior

Return:
1. probable root causes
2. evidence needed
3. smallest experiment to validate each cause
4. proposed fix
5. metric to compare before/after
```

## Code Review

```text
Review this module as production computer vision code.

Focus on:
- coordinate bugs
- frame/timestamp synchronization
- numerical instability
- memory usage
- GPU/CPU transfers
- missing detections
- tracker ID handling
- testability
- concurrency
```

---

# 38. Testing Strategy

## Unit Tests

Test:

```text
homography transform
speed calculation
distance calculation
trajectory smoothing
rally segmentation
coordinate normalization
```

## Integration Tests

```text
video → detector → tracker
video → court → homography
tracking → analytics
API → job queue → worker
```

## End-to-End Test

```text
upload
→ process
→ result
→ dashboard
```

## Golden Video Dataset

Luôn giữ một bộ video nhỏ làm regression set.

```text
sample_001.mp4
sample_002.mp4
sample_003.mp4
...
```

Mỗi lần đổi model/pipeline phải chạy regression.

---

# 39. Performance Strategy

## MVP

Batch processing là đủ.

Không cần real-time.

## Tối ưu sau

- frame skipping;
- lower resolution for player detector;
- higher resolution crop for shuttle detector;
- GPU batching;
- half precision;
- asynchronous pipelines;
- parallel decoding/inference;
- cache intermediate results.

## Smart pipeline

Có thể:

```text
Court model
→ chạy mỗi N frame

Player model
→ chạy mỗi frame / adaptive

Shuttle model
→ chỉ chạy ROI/crop phù hợp
```

Không nhất thiết model nào cũng chạy full-resolution full-frame mọi frame.

---

# 40. Critical Engineering Problems

## Problem 1 — Camera moves

Homography cố định có thể hỏng.

Giải pháp:

```text
redetect court keypoints periodically
+
estimate updated homography
```

Hoặc khóa camera trong MVP.

## Problem 2 — Player occlusion

Hai player đi gần nhau.

Giải pháp:

- ByteTrack tuning;
- appearance features;
- re-identification nếu cần.

## Problem 3 — Shuttle disappears

Không coi một frame miss là rally end.

Cần temporal state.

## Problem 4 — False shuttle detection

Background / lights / objects có thể giống shuttle.

Giải pháp:

- hard negative data;
- temporal filtering;
- velocity constraints;
- court-area constraint.

## Problem 5 — Noisy speed

Do tọa độ detection jitter.

Giải pháp:

```text
raw positions
→ smoothing
→ derivative
→ speed
```

Không tính speed trực tiếp từ raw bbox.

---

# 41. Data Quality Checklist

Trước khi train:

```text
[ ] labels correct
[ ] bbox tight
[ ] shuttle labels visible
[ ] no duplicate labels
[ ] class names consistent
[ ] keypoint IDs consistent
[ ] train/val/test split by video
[ ] no leaked frames
[ ] difficult examples included
```

---

# 42. Model Training Checklist

```text
[ ] baseline model
[ ] baseline metrics
[ ] inspect validation images
[ ] inspect worst false positives
[ ] inspect false negatives
[ ] add hard examples
[ ] retrain
[ ] compare metrics
[ ] benchmark inference speed
[ ] export versioned model
```

Không chỉ nhìn mAP.

---

# 43. Product Analytics Roadmap Sau MVP

## Level 1

```text
Player tracking
Shuttle tracking
Distance
Speed
Heatmap
Rally duration
```

## Level 2

```text
Shot detection
Shot type
Landing zone
Shot direction
```

## Level 3

```text
Tactical patterns
Player weaknesses
Repeated shot patterns
Recovery position
```

## Level 4

```text
AI coach
Natural-language match summary
Personal recommendations
Training suggestions
```

Ví dụ:

> Player A frequently returns to the center after clears but leaves the rear-left corner exposed.

**Cảnh báo:** insight kiểu này chỉ nên đưa ra khi dữ liệu đủ tốt và rule/model được validate.

---

# 44. Potential Advanced Features

## 44.1 Player Pose

YOLO Pose / another pose model.

Có thể phân tích:

- footwork;
- body orientation;
- arm movement;
- jump smash.

## 44.2 Racket Detection

Class:

```text
racket
```

Dùng để tăng độ tin cậy hit detection.

## 44.3 Scoreboard OCR

Detect score/time trên video.

## 44.4 Audio

Detect:

- racket impact;
- applause;
- whistle;
- court announcements.

Audio có thể hỗ trợ event timing nhưng không phải source duy nhất.

## 44.5 Automated Highlights

Tạo clip:

```text
big smash
long rally
match point
```

## 44.6 AI Coach

Dùng analytics output làm structured context cho LLM.

Không đưa raw video trực tiếp vào LLM rồi hy vọng nó tự tính chính xác toàn bộ tracking.

Architecture tốt hơn:

```text
Video
 ↓
CV pipeline
 ↓
Structured statistics
 ↓
LLM
 ↓
Natural language insight
```

---

# 45. AI Coach Output Schema

Ví dụ:

```json
{
  "summary": "Player A played aggressively from the rear court.",
  "observations": [
    {
      "type": "positioning",
      "evidence": {
        "zone": "rear-left",
        "frequency": 0.31
      },
      "confidence": 0.81
    }
  ],
  "recommendations": [
    {
      "text": "Recover toward the center faster after rear-court shots.",
      "confidence": 0.72
    }
  ]
}
```

LLM không nên tự bịa số liệu.

---

# 46. Security

Vì user upload video:

```text
[ ] validate MIME/type
[ ] file size limit
[ ] random storage names
[ ] virus/malware scanning where appropriate
[ ] no executable uploads
[ ] access control
[ ] signed media URLs
[ ] automatic cleanup
[ ] rate limiting
[ ] authentication
```

---

# 47. Privacy

Sports video có người thật.

Nên thiết kế:

- private-by-default;
- user-owned videos;
- clear retention policy;
- delete match button;
- delete source video after processing nếu product policy cho phép;
- không public result URL mặc định.

---

# 48. Observability

Cần log:

```text
job_id
match_id
model_version
video_duration
processing_time
GPU time
CPU time
frames processed
frames failed
average confidence
```

Metrics:

```text
processing_time / video_minute
failure_rate
queue_time
GPU utilization
average detection confidence
```

---

# 49. Acceptance Criteria Cho Product V1

V1 được coi là usable khi:

```text
[ ] User upload được video.
[ ] System không crash với video hợp lệ.
[ ] Player detection hoạt động trên target camera setup.
[ ] Player IDs ổn định phần lớn trận.
[ ] Shuttle trajectory nhìn hợp lý trong test set.
[ ] Court mapping align được với sân.
[ ] Radar view sync với video.
[ ] Distance/speed có kết quả hợp lý.
[ ] Heatmap hoạt động.
[ ] Rally list seek đúng video timestamp.
[ ] Dashboard có loading/error states.
[ ] Results được lưu và xem lại.
[ ] Model/pipeline version được lưu.
```

---

# 50. Demo Script

Khi demo sản phẩm:

## Step 1

Upload 1 video.

## Step 2

Cho xem processing pipeline.

## Step 3

Mở annotated video.

Cho thấy:

```text
Player #1
Player #2
Shuttle
```

## Step 4

Mở radar view.

Player di chuyển trên court 2D theo video.

## Step 5

Mở player stats.

```text
Distance
Speed
Coverage
Heatmap
```

## Step 6

Mở rally timeline.

Click rally.

Video seek đúng đoạn.

## Step 7

Demo advanced feature nếu có:

```text
shot classification
AI summary
```

---

# 51. Risk Register

| Risk | Impact | Likelihood | Mitigation |
|---|---:|---:|---|
| Shuttle detection kém | High | High | dataset chất lượng + temporal tracking |
| Camera quá thấp | High | Medium | define supported camera setup |
| Camera rung | High | Medium | stabilization / recalibration |
| Player ID swap | High | Medium | tracker tuning + appearance embedding |
| Homography sai | High | Medium | nhiều keypoints + validation |
| Speed sai do noise | Medium | High | smoothing |
| Processing quá chậm | High | Medium | GPU + batching + adaptive inference |
| Chi phí GPU cao | Medium | Medium | batch processing + queue |
| Data leakage | High | Medium | split theo video |
| LLM bịa insight | High | Medium | structured evidence + confidence |

---

# 52. What NOT to Do

## Đừng làm toàn bộ cùng lúc

Không bắt đầu bằng:

```text
YOLO
+ Pose
+ Shuttle
+ Racket
+ Shot model
+ LLM
+ mobile app
+ real-time
```

## Đừng train trên dataset ít nhưng kỳ vọng universal

Một model tốt trong 1 sân chưa chắc tốt trên 20 sân.

## Đừng tính metric từ raw detection

Phải qua tracking + smoothing + coordinate transform.

## Đừng dùng frame random split nếu video có cùng sequence

Dễ leakage.

## Đừng build UI trước khi pipeline data ổn

Dashboard đẹp nhưng analytics sai = sản phẩm không có giá trị.

---

# 53. Definition of Done Cho Mỗi Feature

Feature chỉ được coi là xong khi có:

```text
[ ] code
[ ] tests
[ ] sample data
[ ] metrics / validation
[ ] logs
[ ] error handling
[ ] documentation
[ ] frontend integration nếu feature user-facing
```

---

# 54. Final Recommended Build Order

Đây là thứ tự **nên bám sát**, vì mỗi bước unlock bước sau:

```text
1. Video upload + processing worker
        ↓
2. Player detection
        ↓
3. Player tracking
        ↓
4. Shuttle detection
        ↓
5. Shuttle trajectory
        ↓
6. Court keypoints
        ↓
7. Homography
        ↓
8. Court coordinates
        ↓
9. Radar view
        ↓
10. Movement analytics
        ↓
11. Heatmap
        ↓
12. Rally segmentation
        ↓
13. Hit detection
        ↓
14. Shot classification
        ↓
15. Product dashboard
        ↓
16. AI coach
```

---

# 55. Priority Matrix

## P0 — phải có

```text
Player detection
Player tracking
Shuttle detection
Court mapping
Homography
Radar view
Distance
Speed
Heatmap
Upload/processing/dashboard
```

## P1 — rất nên có

```text
Shuttle trajectory
Rally segmentation
Rally viewer
Hit detection
```

## P2 — nâng cấp

```text
Shot classification
Racket detection
Pose estimation
Scoreboard OCR
```

## P3 — advanced

```text
AI coach
Tactical pattern mining
Highlight generation
Predictive analysis
```

---

# 56. First 10 Tasks Cần Làm Ngay

Không bắt đầu train model hôm nay ngay lập tức. Làm 10 task này trước:

```text
[ ] 01. Create Git repository
[ ] 02. Create README + architecture
[ ] 03. Create monorepo structure
[ ] 04. Setup Python CV environment
[ ] 05. Setup FastAPI
[ ] 06. Setup React/Next.js
[ ] 07. Implement video upload
[ ] 08. Implement async processing job
[ ] 09. Collect 5–10 representative badminton videos
[ ] 10. Annotate a small player + shuttle + court sample
```

Sau đó mới baseline model.

---

# 57. First Experimental Milestone

Mục tiêu đầu tiên không phải "AI hoàn chỉnh".

Mục tiêu:

```text
1 video badminton
        ↓
YOLO player detection
        ↓
ByteTrack
        ↓
2 stable player IDs
        ↓
visualized trajectories
```

Khi cái này chạy ổn → mới tiến tới shuttle.

---

# 58. Second Experimental Milestone

```text
1 video
 ↓
player tracking
+
shuttle detection
 ↓
shuttle trajectory
```

Mục tiêu là nhìn vào video và thấy:

```text
Player A ────────────────●
                         ↑
                       shuttle
Player B ────●───────────
```

trajectory phải follow chuyển động hợp lý.

---

# 59. Third Experimental Milestone

```text
camera view
    ↓
court keypoints
    ↓
homography
    ↓
top-down view
```

Player ở camera view phải tương ứng với đúng vị trí trên court.

---

# 60. Fourth Experimental Milestone

```text
Video
 ↓
Tracking
 ↓
Court coordinates
 ↓
Analytics
 ↓
Dashboard
```

Đây chính là **MVP có thể demo**.

---

# 61. Long-Term Vision

```text
              BADMINTON AI PLATFORM
                       │
        ┌──────────────┼──────────────┐
        │              │              │
      Vision        Analytics        AI Coach
        │              │              │
   detection       movement       recommendations
   tracking        shot stats     natural language
   calibration     rally stats    training plans
        │              │              │
        └──────────────┼──────────────┘
                       │
                  User Profile
                       │
                historical matches
                       │
                player progression
```

Mục tiêu cuối không phải chỉ là "YOLO detect player".

Mục tiêu là biến:

```text
VIDEO
  ↓
STRUCTURED SPORTS DATA
  ↓
INSIGHT
  ↓
ACTIONABLE COACHING
```

---

# 62. References

1. Roboflow — Football AI Tutorial: From Basics to Advanced Stats with Python.
   - https://www.youtube.com/watch?v=aBVGKoNZQUw
2. Roboflow — Camera Calibration in Sports with Keypoints.
   - https://blog.roboflow.com/camera-calibration-sports-computer-vision/
3. Roboflow — Ball Tracking in Sports with Computer Vision.
   - https://blog.roboflow.com/tracking-ball-sports-computer-vision/
4. Roboflow Sports repository.
   - https://github.com/roboflow/sports
5. Roboflow football detection/keypoint notebooks and Football AI notebook are listed in the tutorial resources. citeturn166320search0

---

# 63. Final Checklist

## Infrastructure

- [ ] API
- [ ] worker
- [ ] queue
- [ ] database
- [ ] object storage
- [ ] frontend

## CV

- [ ] player detector
- [ ] player tracker
- [ ] shuttle detector
- [ ] shuttle tracker
- [ ] court keypoints
- [ ] homography

## Analytics

- [ ] coordinates
- [ ] distance
- [ ] speed
- [ ] heatmap
- [ ] rally segmentation
- [ ] hit detection
- [ ] shot classification

## Product

- [ ] upload
- [ ] processing progress
- [ ] results dashboard
- [ ] video overlay
- [ ] radar view
- [ ] player stats
- [ ] rally explorer

## Production

- [ ] auth
- [ ] storage security
- [ ] logging
- [ ] monitoring
- [ ] model versioning
- [ ] regression tests
- [ ] failure handling

---

# 64. One-Sentence Product Definition

> **Badminton AI là hệ thống computer vision biến video trận cầu lông thành dữ liệu có cấu trúc về người chơi, cầu, vị trí, chuyển động, rally và shot, sau đó trình bày chúng dưới dạng dashboard để người chơi/HLV có thể phân tích trận đấu.**
