"""
Shuttlecock Detection Module:
High-speed Computer Vision detector for badminton shuttlecock tracking.
Combines temporal frame differencing, adaptive HSV brightness filtering,
and player body exclusion. Returns multiple candidates to allow the tracker
to pick the one that fits the physical trajectory.
"""

from typing import Dict, Any, Optional, List
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

    def detect(
        self,
        frame: np.ndarray,
        player_boxes: Optional[List[List[float]]] = None,
    ) -> Dict[str, Any]:
        """
        Detects real white shuttlecock candidates in frame.
        Excludes white shirts/shorts/rackets inside expanded player bounding boxes.
        Returns: Dict with 'candidates': list of dicts, 'visible': bool
        """
        h, w, _ = frame.shape
        candidates = []

        # Method 1: YOLO model if custom trained weights provided
        if self.model is not None:
            results = self.model(frame, conf=self.conf_threshold, verbose=False)[0]

            for box in results.boxes:
                conf = float(box.conf[0].cpu().numpy())
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().tolist()
                candidates.append({
                    "bbox": [round(c, 1) for c in [x1, y1, x2, y2]],
                    "center": [round((x1 + x2) / 2.0, 1), round((y1 + y2) / 2.0, 1)],
                    "confidence": round(conf, 3),
                    "score": conf,
                })
            
            # Sort candidates by score
            candidates.sort(key=lambda x: x["score"], reverse=True)
            
            if candidates:
                # Still return "center" etc at top level for backwards compatibility (picks top 1)
                best = candidates[0]
                return {
                    "bbox": best["bbox"],
                    "center": best["center"],
                    "confidence": best["confidence"],
                    "visible": True,
                    "candidates": candidates,
                }
            return {"visible": False, "candidates": []}

        # Method 2: Temporal Motion Differencing + Adaptive White HSV Blob Detection
        if HAS_OPENCV:
            try:
                # Shuttlecock travels in the playing airspace: 0.08 * h < y < 0.85 * h
                roi_y1 = int(h * 0.08)
                roi_y2 = int(h * 0.85)
                roi_x1 = int(w * 0.10)
                roi_x2 = int(w * 0.90)

                roi = frame[roi_y1:roi_y2, roi_x1:roi_x2]
                hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
                gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

                # Bright white filter (forgiving range for motion blur / indoor lighting)
                lower_white = np.array([0, 0, 190], dtype=np.uint8)
                upper_white = np.array([180, 85, 255], dtype=np.uint8)
                white_mask = cv2.inRange(hsv, lower_white, upper_white)

                # Motion differencing mask
                target_mask = white_mask
                if self.prev_roi_gray is not None and self.prev_roi_gray.shape == gray.shape:
                    diff = cv2.absdiff(gray, self.prev_roi_gray)
                    _, diff_mask = cv2.threshold(diff, 18, 255, cv2.THRESH_BINARY)
                    # Motion combined with white color
                    motion_white = cv2.bitwise_and(white_mask, diff_mask)
                    if cv2.countNonZero(motion_white) >= 2:
                        target_mask = motion_white

                # Store current gray ROI for next frame motion diff
                self.prev_roi_gray = gray.copy()

                # Clean small noise
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
                target_mask = cv2.morphologyEx(target_mask, cv2.MORPH_OPEN, kernel)

                contours, _ = cv2.findContours(target_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

                for cnt in contours:
                    area = cv2.contourArea(cnt)
                    # Shuttlecock size in typical broadcast 720p/1080p is between 4 and 250 pixels
                    if 4 <= area <= 250:
                        bx, by, bw, bh = cv2.boundingRect(cnt)
                        aspect_ratio = float(bw) / max(1, bh)
                        # Compact / flight streak shape
                        if 0.20 <= aspect_ratio <= 4.0:
                            cx = roi_x1 + bx + bw / 2.0
                            cy = roi_y1 + by + bh / 2.0

                            # Exclude if candidate is inside any player's bounding box
                            # Expand player box by 30% width and 15% height to cover swinging rackets
                            if player_boxes:
                                in_player = False
                                for pbox in player_boxes:
                                    if len(pbox) == 4:
                                        pw = pbox[2] - pbox[0]
                                        ph = pbox[3] - pbox[1]
                                        px_min = pbox[0] - pw * 0.30
                                        px_max = pbox[2] + pw * 0.30
                                        py_min = pbox[1] - ph * 0.15
                                        py_max = pbox[3] + ph * 0.10
                                        
                                        if (px_min <= cx <= px_max) and (py_min <= cy <= py_max):
                                            in_player = True
                                            break
                                if in_player:
                                    continue

                            # Score candidate by intensity and compactness (higher is better)
                            score = float(area) / (1.0 + abs(aspect_ratio - 1.0) * 0.5)
                            
                            candidates.append({
                                "bbox": [
                                    round(cx - bw / 2, 1),
                                    round(cy - bh / 2, 1),
                                    round(cx + bw / 2, 1),
                                    round(cy + bh / 2, 1),
                                ],
                                "center": [round(cx, 1), round(cy, 1)],
                                "confidence": 0.88,
                                "score": score,
                            })

                if candidates:
                    # Sort candidates by visual score descending
                    candidates.sort(key=lambda x: x["score"], reverse=True)
                    # Keep top 5 candidates for the tracker to match with trajectory
                    candidates = candidates[:5]
                    
                    best = candidates[0]
                    return {
                        "bbox": best["bbox"],
                        "center": best["center"],
                        "confidence": best["confidence"],
                        "visible": True,
                        "candidates": candidates,
                    }
            except Exception as e:
                print(f"[ShuttleDetector] Error: {e}")

        return {"visible": False, "candidates": []}
