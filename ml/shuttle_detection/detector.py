"""
Shuttlecock Detection Module:
High-speed Computer Vision detector for badminton shuttlecock tracking.
Combines temporal frame differencing, adaptive HSV brightness filtering,
and compact morphological blob analysis.
"""

from typing import Dict, Any, Optional
import numpy as np

try:
    import cv2
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False


class ShuttleDetector:
    def __init__(self, model_path: Optional[str] = None, conf_threshold: float = 0.25):
        self.conf_threshold = conf_threshold
        self.model = None
        self.prev_roi_gray = None

        if model_path:
            try:
                from ultralytics import YOLO

                self.model = YOLO(model_path)
            except Exception as e:
                print(f"[ShuttleDetector] Failed to load model {model_path}: {e}")

    def detect(self, frame: np.ndarray) -> Dict[str, Any]:
        """
        Detects real white shuttlecock in frame.
        Returns: Dict with 'center': [cx, cy], 'bbox': [x1, y1, x2, y2], 'confidence': float, 'visible': bool
        """
        h, w, _ = frame.shape

        # Method 1: YOLO model if custom trained weights provided
        if self.model is not None:
            results = self.model(frame, conf=self.conf_threshold, verbose=False)[0]
            best_box = None
            best_conf = 0.0

            for box in results.boxes:
                conf = float(box.conf[0].cpu().numpy())
                if conf > best_conf:
                    best_conf = conf
                    best_box = box.xyxy[0].cpu().numpy().tolist()

            if best_box is not None:
                x1, y1, x2, y2 = best_box
                return {
                    "bbox": [round(c, 1) for c in [x1, y1, x2, y2]],
                    "center": [round((x1 + x2) / 2.0, 1), round((y1 + y2) / 2.0, 1)],
                    "confidence": round(best_conf, 3),
                    "visible": True,
                }

        # Method 2: Temporal Motion Differencing + Adaptive White HSV Blob Detection
        if HAS_OPENCV:
            try:
                # Shuttlecock travels in the playing airspace: 0.06 * h < y < 0.88 * h
                roi_y1 = int(h * 0.06)
                roi_y2 = int(h * 0.88)
                roi_x1 = int(w * 0.08)
                roi_x2 = int(w * 0.92)

                roi = frame[roi_y1:roi_y2, roi_x1:roi_x2]
                hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
                gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

                # Bright white filter (forgiving range for motion blur / indoor lighting)
                lower_white = np.array([0, 0, 185], dtype=np.uint8)
                upper_white = np.array([180, 100, 255], dtype=np.uint8)
                white_mask = cv2.inRange(hsv, lower_white, upper_white)

                # Motion differencing mask
                target_mask = white_mask
                if self.prev_roi_gray is not None and self.prev_roi_gray.shape == gray.shape:
                    diff = cv2.absdiff(gray, self.prev_roi_gray)
                    _, diff_mask = cv2.threshold(diff, 16, 255, cv2.THRESH_BINARY)
                    # Motion combined with white color
                    motion_white = cv2.bitwise_and(white_mask, diff_mask)
                    if cv2.countNonZero(motion_white) >= 4:
                        target_mask = motion_white

                # Store current gray ROI for next frame motion diff
                self.prev_roi_gray = gray.copy()

                # Clean small noise
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
                target_mask = cv2.morphologyEx(target_mask, cv2.MORPH_OPEN, kernel)

                contours, _ = cv2.findContours(target_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                best_shuttle = None
                best_score = 0.0

                for cnt in contours:
                    area = cv2.contourArea(cnt)
                    # Shuttlecock size in typical broadcast 720p/1080p is between 4 and 260 pixels
                    if 4 <= area <= 280:
                        bx, by, bw, bh = cv2.boundingRect(cnt)
                        aspect_ratio = float(bw) / max(1, bh)
                        # Compact / flight streak shape
                        if 0.30 <= aspect_ratio <= 3.0:
                            cx = roi_x1 + bx + bw / 2.0
                            cy = roi_y1 + by + bh / 2.0

                            # Score candidate by intensity and compactness
                            score = float(area) / (1.0 + abs(aspect_ratio - 1.0) * 0.5)
                            if score > best_score:
                                best_score = score
                                best_shuttle = (cx, cy, bw, bh, area)

                if best_shuttle is not None:
                    cx, cy, bw, bh, _ = best_shuttle
                    return {
                        "bbox": [
                            round(cx - bw / 2, 1),
                            round(cy - bh / 2, 1),
                            round(cx + bw / 2, 1),
                            round(cy + bh / 2, 1),
                        ],
                        "center": [round(cx, 1), round(cy, 1)],
                        "confidence": 0.88,
                        "visible": True,
                    }
            except Exception as e:
                pass

        # If not detected in this frame
        return {"visible": False}
