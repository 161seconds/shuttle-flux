"""
Court Keypoint Detector:
Identifies court landmarks and corners on broadcast video for accurate Homography transformation.
"""

from typing import Dict, Tuple, Optional
import numpy as np

try:
    import cv2
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False


class CourtKeypointDetector:
    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path
        self.model = None

    def detect_keypoints(self, frame: np.ndarray) -> Dict[str, Tuple[float, float]]:
        """
        Detects primary court corners in image pixels.
        Returns mapping of corner names to (px_x, px_y).
        """
        h, w, _ = frame.shape

        # Standard BWF broadcast camera geometry (Denmark Open, All England, etc.)
        # Far baseline: ~52% of height, Net: ~62% of height, Near baseline: ~90% of height
        default_keypoints = {
            "corner_top_left": (w * 0.35, h * 0.52),
            "corner_top_right": (w * 0.65, h * 0.52),
            "net_left": (w * 0.29, h * 0.62),
            "net_right": (w * 0.71, h * 0.62),
            "corner_bottom_left": (w * 0.18, h * 0.90),
            "corner_bottom_right": (w * 0.82, h * 0.90),
        }

        # Optional: refined court floor segmentation if OpenCV available
        if HAS_OPENCV:
            try:
                hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                # Green badminton court mat HSV range
                green_mask = cv2.inRange(hsv, np.array([35, 30, 30]), np.array([85, 255, 255]))
                contours, _ = cv2.findContours(green_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if contours:
                    largest_cnt = max(contours, key=cv2.contourArea)
                    if cv2.contourArea(largest_cnt) > (w * h * 0.15):
                        # Approximate polygon
                        peri = cv2.arcLength(largest_cnt, True)
                        approx = cv2.approxPolyDP(largest_cnt, 0.04 * peri, True)
                        if len(approx) == 4:
                            pts = approx.reshape(4, 2)
                            # Sort by Y
                            sorted_by_y = pts[np.argsort(pts[:, 1])]
                            top_pts = sorted_by_y[:2]
                            bottom_pts = sorted_by_y[2:]
                            # Sort by X
                            tl = top_pts[np.argmin(top_pts[:, 0])]
                            tr = top_pts[np.argmax(top_pts[:, 0])]
                            bl = bottom_pts[np.argmin(bottom_pts[:, 0])]
                            br = bottom_pts[np.argmax(bottom_pts[:, 0])]

                            # Verify realistic proportions
                            if 0.40 * h <= tl[1] <= 0.60 * h and 0.80 * h <= bl[1] <= 0.98 * h:
                                return {
                                    "corner_top_left": (float(tl[0]), float(tl[1])),
                                    "corner_top_right": (float(tr[0]), float(tr[1])),
                                    "net_left": (float(tl[0] * 0.45 + bl[0] * 0.55), float(tl[1] * 0.45 + bl[1] * 0.55)),
                                    "net_right": (float(tr[0] * 0.45 + br[0] * 0.55), float(tr[1] * 0.45 + br[1] * 0.55)),
                                    "corner_bottom_left": (float(bl[0]), float(bl[1])),
                                    "corner_bottom_right": (float(br[0]), float(br[1])),
                                }
            except Exception:
                pass

        return default_keypoints
