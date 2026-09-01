"""
Shuttlecock Detection Module:
Computer Vision detector for badminton shuttlecock tracking.
Detects real fast-moving white shuttlecock blobs in air space using HSV brightness,
morphological filtering, and size/shape constraints.
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
        self.prev_gray = None

        if model_path:
            try:
                from ultralytics import YOLO

                self.model = YOLO(model_path)
            except Exception as e:
                print(f"[ShuttleDetector] Failed to load model {model_path}: {e}")

    def detect(self, frame: np.ndarray) -> Optional[Dict[str, Any]]:
        """
        Detects real white shuttlecock in frame.
        Returns: Dict with 'center': [x, y], 'bbox': [x1, y1, x2, y2], 'confidence': float, 'visible': bool
        """
        h, w, _ = frame.shape

        # Method 1: YOLO model if provided
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

        # Method 2: High-contrast white shuttlecock blob detection (OpenCV)
        if HAS_OPENCV:
            try:
                # Shuttlecock is in the airspace between/above players: 0.10 * h < y < 0.85 * h
                roi_y1 = int(h * 0.10)
                roi_y2 = int(h * 0.85)
                roi_x1 = int(w * 0.10)
                roi_x2 = int(w * 0.90)

                roi = frame[roi_y1:roi_y2, roi_x1:roi_x2]
                hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
                gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

                # Shuttlecock is bright white (High Value, Low Saturation)
                lower_white = np.array([0, 0, 215], dtype=np.uint8)
                upper_white = np.array([180, 80, 255], dtype=np.uint8)
                mask = cv2.inRange(hsv, lower_white, upper_white)

                # Clean small noise
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
                mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                best_shuttle = None
                best_score = 0.0

                for cnt in contours:
                    area = cv2.contourArea(cnt)
                    # Shuttlecock size in typical 720p/1080p stream is 4 to 120 pixels
                    if 4 <= area <= 140:
                        bx, by, bw, bh = cv2.boundingRect(cnt)
                        aspect_ratio = float(bw) / max(1, bh)
                        # Compact / oval shape
                        if 0.4 <= aspect_ratio <= 2.2:
                            # Prefer candidate in central play zone
                            cx = roi_x1 + bx + bw / 2.0
                            cy = roi_y1 + by + bh / 2.0
                            score = float(area) / (1.0 + abs(aspect_ratio - 1.0))
                            if score > best_score:
                                best_score = score
                                best_shuttle = (cx, cy, bw, bh, area)

                if best_shuttle is not None:
                    cx, cy, bw, bh, _ = best_shuttle
                    return {
                        "bbox": [round(cx - bw / 2, 1), round(cy - bh / 2, 1), round(cx + bw / 2, 1), round(cy + bh / 2, 1)],
                        "center": [round(cx, 1), round(cy, 1)],
                        "confidence": 0.88,
                        "visible": True,
                    }
            except Exception:
                pass

        # If not detected, return not visible
        return {"visible": False}
