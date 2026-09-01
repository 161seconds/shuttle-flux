# 🏸 Shuttle Flux — Tài Liệu Toàn Diện & Bối Cảnh Dự Án (Project Context & Technical Guide)

> **Hệ thống Trí tuệ Nhân tạo & Thị giác Máy tính Phân tích Trận đấu Cầu Lông Chuyên nghiệp theo Chuẩn Quốc tế BWF**  
> *(Automated Badminton Match Video Analytics, Computer Vision Tracking, 2D Radar Homography & Interactive Dashboard)*

---

## 📑 MỤC LỤC
1. [Bối Cảnh & Mục Tiêu Dự Án (Project Context & Vision)](#1-bối-cảnh--mục-tiêu-dự-án-project-context--vision)
2. [Kiến Trúc Tổng Thể & Luồng Xử Lý (System Architecture & Pipeline)](#2-kiến-trúc-tổng-thể--luồng-xử-lý-system-architecture--pipeline)
3. [Chi Tiết Các Module Thị Giác Máy Tính (Computer Vision & ML Deep Dive)](#3-chi-tiết-các-module-thị-giác-máy-tính-computer-vision--ml-deep-dive)
   - [3.1 Nhận Diện VĐV & Loại Trừ Trọng Tài (Player Detection & Referee Exclusion)](#31-nhận-diện-vđv--loại-trừ-trọng-tài-player-detection--referee-exclusion)
   - [3.2 Theo Dấu VĐV & Giữ Ổn Định ID (Spatial Tracking & Track Continuity)](#32-theo-dấu-vđv--giữ-ổn-định-id-spatial-tracking--track-continuity)
   - [3.3 Hệ Thống Hình Học Sân BWF & Lưới 3D (Court Keypoints & 3D Net Foreshortening)](#33-hệ-thống-hình-học-sân-bwf--lưới-3d-court-keypoints--3d-net-foreshortening)
   - [3.4 Nhận Diện Bảng Điểm & Tên VĐV (Broadcast Scoreboard OCR)](#34-nhận-diện-bảng-điểm--tên-vđv-broadcast-scoreboard-ocr)
4. [Kiến Trúc Frontend & Trải Nghiệm Người Dùng (Frontend Next.js 16)](#4-kiến-trúc-frontend--trải-nghiệm-người-dùng-frontend-nextjs-16)
5. [Đặc Tả REST API & Cấu Trúc Dữ Liệu (API & Data Schema)](#5-đặc-tả-rest-api--cấu-trúc-dữ-liệu-api--data-schema)
6. [Hướng Dẫn Cài Đặt & Khởi Chạy Từng Bước (Step-by-Step Setup Guide)](#6-hướng-dẫn-cài-đặt--khởi-chạy-từng-bước-step-by-step-setup-guide)
7. [Các Vấn Đề Đã Giải Quyết & Best Practices (Troubleshooting & Solutions)](#7-các-vấn-đề-đã-giải-quyết--best-practices-troubleshooting--solutions)

---

## 1. Bối Cảnh & Mục Tiêu Dự Án (Project Context & Vision)

Trong các trận thi đấu cầu lông chuyên nghiệp (BWF World Tour, Olympic, giải vô địch thế giới), việc phân tích video truyền hình thủ công đòi hỏi chuyên viên thống kê tốn nhiều giờ đồng hồ để ghi nhận từng cú đánh, quãng đường di chuyển, vị trí tiếp xúc cầu và phân đoạn từng pha cầu (rally).

**Shuttle Flux** được xây dựng để tự động hóa $100\%$ quy trình này thông qua **Thị giác Máy tính (Computer Vision)** và **AI Phân tích Thể thao Hiện đại**:
- 🎥 **Nhập liệu đa nguồn**: Tải lên video MP4/MOV từ máy tính hoặc dán trực tiếp đường dẫn YouTube (Hỗ trợ Full HD 1080p).
- ⚡ **Chế độ Xem & Tải Trực Tiếp (Live Stream AI Mode)**: Người dùng có thể nhấn Play xem video ngay từ giây thứ 0 trong khi AI tính toán luồng phía trước theo từng batch mà không cần chờ video xử lý xong toàn bộ.
- 🎯 **Thị giác máy tính tự động $100\%$**: Tự nhận diện các vạch sân chuẩn BWF, vẽ lưới 3D, phân biệt trận đấu Đơn 1v1 hoặc Đôi 2v2 mà không bắt buộc người dùng căn chỉnh thủ công.
- 🏸 **Theo dấu & Vật lý thể thao**: Tính toán vị trí tiếp xúc chân của từng VĐV, vận tốc di chuyển tức thời, tổng quãng đường (m), mật độ bao quát sân (Heatmap 6 phân vùng) và phân đoạn các pha cầu (Rallies) tự động.
- 📺 **Trích xuất thông tin phát sóng**: Đọc tự động tên VĐV (Ví dụ: `YU QI`, `KEAN YEW`), quốc gia và tỷ số trận đấu từ thẻ đồ họa bảng điểm gốc.

---

## 2. Kiến Trúc Tổng Thể & Luồng Xử Lý (System Architecture & Pipeline)

```text
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                USER INTERACTION                                 │
│             Next.js 16 Web Dashboard (React 19 + Turbopack + TailwindCSS)       │
└────────────────────────────────────────┬────────────────────────────────────────┘
                                         │  HTTP / REST / Streaming Polling
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                               FASTAPI BACKEND                                   │
│  - Video Ingestion & YouTube 1080p Downloader (Mobile Player Client Bypass)     │
│  - Match & Job Status Management (In-Memory + File Storage Registry)           │
│  - Live Streaming Analytics Batches Provider (/analytics)                       │
└────────────────────────────────────────┬────────────────────────────────────────┘
                                         │  Async Worker Tasks
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        COMPUTER VISION & ANALYTICS PIPELINE                     │
│                                                                                 │
│   [ Video Frame Extraction ] (OpenCV / FFmpeg 30 FPS)                           │
│              │                                                                  │
│              ├─► [ Scoreboard OCR ] (EasyOCR + BWF Sponsor Keyword Filtering)   │
│              │                                                                  │
│              ├─► [ Court Keypoint Detection ] (12 BWF Perspective Nodes & Net)  │
│              │                                                                  │
│              ├─► [ Player Detection & Filter ] (YOLOv8 + Referee Exclusion)     │
│              │                                                                  │
│              ├─► [ Spatial Track Association ] (Continuous Euclidean Tracking)  │
│              │                                                                  │
│              ├─► [ Homography 2D Transformation ] (3D Space -> 2D Radar Canvas) │
│              │                                                                  │
│              ├─► [ Movement & Speed Analytics ] (Savitzky-Golay Smoothing)      │
│              │                                                                  │
│              └─► [ Rally & Hit State Machine ] (Active Play Segmentation)       │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Chi Tiết Các Module Thị Giác Máy Tính (Computer Vision & ML Deep Dive)

### 3.1 Nhận Diện VĐV & Loại Trừ Trọng Tài (`ml/player_detection/detector.py`)
Mô hình sử dụng YOLOv8 được tinh chỉnh để nhận diện người trên sân, kết hợp bộ lọc hình học nhằm loại bỏ hoàn toàn các nhân vật không thi đấu:
1. **Trọng tài chính (Main Umpire)**: Ngồi trên ghế cao sát cột lưới bên ngoài biên dọc ($x < 0.24$ hoặc $x > 0.76$, $0.42 \le y \le 0.66$, $y_{top} < 0.26$).
2. **Trọng tài giao cầu (Service Judge)**: Ngồi ghế thấp đối diện cột lưới ($0.44 \le y \le 0.62$).
3. **Trọng tài biên sân xa (Far Baseline Line Judges)**: 2–3 trọng tài ngồi ở hàng ghế phía sau vạch đáy sân xa ($y_{bottom} < 0.40$).
4. **Trọng tài biên sân gần & Nhân viên lau sân**: Vị trí các góc đáy $y > 0.88, x < 0.15$ hoặc $x > 0.85$.
5. **Hành lang sân thi đấu (Dynamic Perspective Corridor)**: Mở rộng tuyến tính từ sân xa ($26\% - 74\%$) xuống sân gần ($10\% - 90\%$).

### 3.2 Theo Dấu VĐV & Giữ Ổn Định ID (`ml/tracking/tracker.py`)
- **Phân loại thứ tự không gian tương đối**: Thay vì dùng ngưỡng $y$ cố định (dễ gây lỗi khi VĐV sân xa lao lên lưới), hệ thống sắp xếp các phát hiện theo khoảng cách quang học. VĐV sân gần (P1) có chiều cao bounding box lớn hơn ($h > 0.20$) và chân thấp hơn VĐV sân xa (P2).
- **Khắc phục lỗi Đổi ID khi lên lưới**: Khi VĐV sân xa (P2) di chuyển lên sát lưới để đánh cầu ngắn, hệ thống sử dụng **Track Continuity (Khoảng cách Euclidean từ vị trí frame trước)** để giữ nguyên ID `P2`, không bao giờ bị đổi thành `P1` hay sinh ra `P3`/`P4`.
- **Chế độ Đơn 1v1 Mặc định**: Giới hạn nghiêm ngặt chỉ hiển thị 2 vận động viên thật, loại bỏ hoàn toàn hiện tượng bounding box bóng ma đè lên nhau.

### 3.3 Hệ Thống Hình Học Sân BWF & Lưới 3D (`ml/court_keypoints/detector.py`)
Kích thước sân chuẩn BWF ($13.40\text{m} \times 6.10\text{m}$ đôi / $5.18\text{m}$ đơn) được ánh xạ chính xác qua phép chiếu phối cảnh 2D:
- **Vạch đáy trên (Far Baseline)**: $y = 0.00\text{m}$
- **Vạch giao cầu dài sân xa (Far Doubles Long Service Line)**: $0.76\text{m}$ từ vạch đáy xa.
- **Vạch giao cầu ngắn sân xa (Far Short Service Line)**: $1.98\text{m}$ từ lưới.
- **Vị trí Lưới thi đấu (3D Net)**: Tại vị trí chính giữa $6.70\text{m}$ ($50\%$ chiều dài 3D $\rightarrow$ chiếu xuống $20\%$ chiều cao Y phối cảnh 2D), gồm 2 cột lưới, dải viền trắng và lưới đan.
- **Vạch giao cầu ngắn sân gần (Near Short Service Line)**: $1.98\text{m}$ từ lưới về phía sân gần.
- **Vạch giao cầu dài sân gần (Near Doubles Long Service Line)**: $0.76\text{m}$ trước vạch đáy gần.
- **Vạch đáy dưới (Near Baseline)**: $y = 13.40\text{m}$
- **Vạch trung tâm (Center Service Line)**: Chạy dọc chia đôi 2 ô giao cầu.
- **12 Landmark Nodes**: 4 góc sân (`P_TL`, `P_TR`, `P_BL`, `P_BR`), 2 cột lưới (`Net_L`, `Net_R`) và các ngã ba giao cầu (`T_Far`, `T_Near`).

### 3.4 Nhận Diện Bảng Điểm & Tên VĐV (`ml/ocr/scoreboard_reader.py`)
- Quét vùng góc trên cùng bên trái ($x: 2\% - 32\%, y: 2\% - 22\%$).
- **Bộ lọc từ khóa rác & nhà tài trợ**: Tự động loại bỏ các từ: `HSBC`, `BWF`, `WORLD TOUR`, `SUPER 750/1000`, `SHENZHEN`, `CHINA MASTERS`, `VICTOR`, `YONEX`, `TOTALENERGIES`.
- Trích xuất tên VĐV (Ví dụ: `YU QI` - Sân xa, `KEAN YEW` - Sân gần), điểm số từng set (`1 - 1`) và biểu tượng quả cầu giao cầu.

---

## 4. Kiến Trúc Frontend & Trải Nghiệm Người Dùng (Frontend Next.js 16)

Frontend được đặt tại thư mục `apps/web/`, chạy trên **Next.js 16 (Turbopack)** với **pnpm**:

- **VideoPlayerWithRadar (`apps/web/src/components/VideoPlayerWithRadar.tsx`)**:
  - Trình phát song song: **Video Gốc** và **Luồng Thị Giác AI (AI Vision Stream)**.
  - Bảng điểm BWF Broadcast HUD góc trên trái: Thẻ trắng bo góc, quốc kỳ `CHN`/`SGP`, tên VĐV và điểm số theo thời gian thực.
  - Vạch sân BWF & Lưới 3D phát sáng rõ nét trên mọi nền sân màu xanh hoặc xám.
  - **Chế độ Hiệu chỉnh Góc Sân (Calibration Mode)**: Người dùng có thể kéo thả 4 điểm góc. Khi thả chuột, vị trí được lưu trữ cố định vào `userHasEditedNodesRef`, không bị luồng live polling làm reset.
- **Radar Canvas (`apps/web/src/components/RadarCanvas.tsx`)**:
  - Mô phỏng sân 2D nhìn từ trên cao (Top-down view).
  - Tọa độ chấm sáng thời gian thực: P1 (Xanh Cyan), P2 (Vàng Hổ Phách).
  - Quỹ đạo di chuyển (Trajectory trail) và bản đồ nhiệt Heatmap.
- **Rally Timeline Explorer (`apps/web/src/components/RallyTimeline.tsx`)**:
  - Tự động phân đoạn các pha giao tranh (Rallies).
  - Nhấn vào từng rally để tua trực tiếp video đến thời điểm phát cầu.
- **Player Stats Cards (`apps/web/src/components/PlayerStats.tsx`) & OverviewCards (`OverviewCards.tsx`)**:
  - Thống kê chi tiết quãng đường di chuyển (m), vận tốc tối đa (km/h), thời gian thi đấu thực và tỷ lệ kiểm soát 6 ô sân.

---

## 5. Đặc Tả REST API & Cấu Trúc Dữ Liệu (API & Data Schema)

API chạy tại `http://localhost:8000` (FastAPI):

| Method | Endpoint | Mô Tả |
|---|---|---|
| `GET` | `/health` | Kiểm tra tình trạng hoạt động của backend |
| `POST` | `/api/v1/matches/upload` | Tải lên file video trực tiếp (`.mp4`, `.mov`, `.avi`) |
| `POST` | `/api/v1/matches/youtube` | Phân tích video từ YouTube URL (1080p Full HD) |
| `GET` | `/api/v1/matches/{id}/processing` | Kiểm tra tiến độ phân tích (0% - 100%) và stage hiện tại |
| `GET` | `/api/v1/matches/{id}/analytics` | Lấy dữ liệu analytics đầy đủ hoặc stream từng phần (Live Mode) |
| `GET` | `/api/v1/matches/demo/analytics` | Tạo và nạp trận đấu mẫu Demo tức thì (900 frames, 0s delay) |
| `GET` | `/api/v1/matches/{id}/video` | Stream video MP4 phục vụ trình phát |
| `POST` | `/api/v1/matches/{id}/cancel` | Hủy tác vụ xử lý đang chạy |
| `POST` | `/api/v1/matches/{id}/players` | Cập nhật thủ công tên vận động viên |
| `POST` | `/api/v1/storage/cleanup` | Dọn dẹp các video cũ trong `storage/matches` để giải phóng ổ cứng |

---

## 6. Hướng Dẫn Cài Đặt & Khởi Chạy Từng Bước (Step-by-Step Setup Guide)

### 6.1 Yêu Cầu Môi Trường (Prerequisites)
- **Hệ điều hành**: Windows 10/11, macOS, hoặc Linux.
- **Python**: Phiên bản 3.10 đến 3.12 (khuyên dùng Python 3.12).
- **Node.js**: Phiên bản 18 trở lên (khuyên dùng Node.js 20+).
- **pnpm**: Trình quản lý gói chính cho frontend (`pnpm v11+`).
- **FFmpeg**: Đã cài đặt và có trong biến môi trường `PATH`.

---

### 6.2 Cài Đặt & Chạy Backend (FastAPI + Python AI Worker)

```bash
# 1. Di chuyển vào thư mục gốc dự án
cd d:/my-project/shuttle-flux

# 2. Tạo môi trường ảo Python (nếu chưa có)
python -m venv venv

# 3. Kích hoạt môi trường ảo
# Trên Windows PowerShell:
.\venv\Scripts\Activate.ps1
# Trên Linux/macOS:
source venv/bin/activate

# 4. Cài đặt các gói thư viện AI/ML cần thiết
pip install fastapi uvicorn pydantic python-multipart ultralytics opencv-python easyocr yt-dlp numpy scipy imageio imageio-ffmpeg pytest requests httpx

# 5. Khởi động Backend API Server (cổng 8000)
uvicorn apps.api.main:app --reload --port 8000
```

---

### 6.3 Cài Đặt & Chạy Frontend (Next.js 16 Turbopack)

Mở một cửa sổ Terminal mới:

```bash
# 1. Di chuyển vào thư mục web
cd d:/my-project/shuttle-flux/apps/web

# 2. Cài đặt toàn bộ dependencies bằng pnpm
pnpm install

# 3. Khởi động máy chủ Next.js Dev Server (cổng 3000)
pnpm run dev
```

Mở trình duyệt web tại địa chỉ: **[http://localhost:3000](http://localhost:3000)**.

---

### 6.4 Chạy Kiểm Thử Hệ Thống (Automated Testing)

```bash
# Kiểm tra toàn bộ 13 bài test Python Unit & Integration
.\venv\Scripts\pytest.exe tests/ -v

# Kiểm tra kiểu dữ liệu TypeScript Frontend
cd apps/web
pnpm exec tsc --noEmit

# Kiểm tra biên dịch Next.js Production Build
pnpm run build
```

---

## 7. Các Vấn Đề Đã Giải Quyết & Best Practices (Troubleshooting & Solutions)

### 7.1 YouTube Bot Challenge (`Sign in to confirm you're not a bot`)
- **Giải pháp**: Cấu hình `extractor_args.youtube.player_client = ['android', 'ios', 'mweb']` cùng `User-Agent` giả lập thiết bị di động Android. YouTube sẽ phục vụ luồng di động không yêu cầu captcha hoặc đăng nhập Google.

### 7.2 Hiện Tượng Đổi ID & Hộp Bounding Box Chồng Chất (1v1 vs 2v2)
- **Giải pháp**: Phân biệt VĐV dựa trên **thứ tự Y tương đối và tỷ lệ kích thước bounding box**. Không sử dụng ngưỡng Y cố định. Đảm bảo khi VĐV sân xa (P2) chạy lên sát lưới thực hiện cú bỏ nhỏ, ID `P2` vẫn được duy trì liên tục mà không bị nhảy sang `P1`.

### 7.3 Kéo Thả Góc Sân Bị Reset Tọa Độ
- **Giải pháp**: Cơ chế `userHasEditedNodesRef` khóa các cập nhật từ luồng polling khi người dùng đang ở chế độ hiệu chỉnh (Calibration Mode). Tọa độ sân tùy chỉnh được lưu cố định suốt phiên làm việc.

### 7.4 Tối Ưu Tốc Độ Xử Lý & Live Streaming
- Hệ thống gửi các batch phân tích từng $8$ frames về API. Frontend cho phép người dùng xem trước và điều khiển video ngay từ frame đầu tiên mà không cần đợi $100\%$ video kết thúc.

---

*Tài liệu được cập nhật tự động — Phiên bản Shuttle Flux 2.0 (Tháng 9/2026).*
