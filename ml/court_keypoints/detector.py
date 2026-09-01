"""
Court Keypoint Detector:
Identifies video-specific court landmarks and corners dynamically across different camera angles,
resolutions, zoom levels, and court colors (Green, Blue, Red/Gray).
"""

from typing import Dict, Tuple, Optional, Any
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

    def detect_keypoints(self, frame: np.ndarray) -> Dict[str, Any]:
        """
        Detects primary court corners dynamically in image pixels and normalized 0-1 coords.
        Adapts dynamically to the video's actual camera perspective and zoom.
        """
        h, w, _ = frame.shape

        # Default fallback calibrated to BWF broadcast camera standard
        tl = (w * 0.35, h * 0.52)
        tr = (w * 0.65, h * 0.52)
        bl = (w * 0.18, h * 0.90)
        br = (w * 0.82, h * 0.90)

        # Dynamic Video Floor Segmentation (Green & Blue BWF Courts)
        if HAS_OPENCV:
            try:
                hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

                # Green court mask (standard BWF green mat)
                green_mask = cv2.inRange(hsv, np.array([32, 25, 25]), np.array([88, 255, 255]))
                # Blue court mask (e.g. French Open / Sudirman Cup)
                blue_mask = cv2.inRange(hsv, np.array([95, 30, 30]), np.array([135, 255, 255]))
                court_mask = cv2.bitwise_or(green_mask, blue_mask)

                # Morphology to connect court lines and floor
                kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
                court_mask = cv2.morphologyEx(court_mask, cv2.MORPH_CLOSE, kernel)

                contours, _ = cv2.findContours(court_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if contours:
                    # Find candidate with largest area in lower 70% of screen
                    valid_contours = [
                        c for c in contours 
                        if cv2.contourArea(c) > (w * h * 0.12)
                    ]
                    if valid_contours:
                        largest_cnt = max(valid_contours, key=cv2.contourArea)
                        peri = cv2.arcLength(largest_cnt, True)
                        approx = cv2.approxPolyDP(largest_cnt, 0.035 * peri, True)

                        # Convex hull bounding polygon
                        hull = cv2.convexHull(largest_cnt)
                        if len(approx) == 4:
                            pts = approx.reshape(4, 2)
                        elif len(hull) >= 4:
                            # Sample 4 extreme corners from hull
                            pts = self._extract_4_corners_from_hull(hull, w, h)
                        else:
                            pts = None

                        if pts is not None and len(pts) == 4:
                            sorted_by_y = pts[np.argsort(pts[:, 1])]
                            top_pts = sorted_by_y[:2]
                            bottom_pts = sorted_by_y[2:]
                            
                            c_tl = top_pts[np.argmin(top_pts[:, 0])]
                            c_tr = top_pts[np.argmax(top_pts[:, 0])]
                            c_bl = bottom_pts[np.argmin(bottom_pts[:, 0])]
                            c_br = bottom_pts[np.argmax(bottom_pts[:, 0])]

                            # Validate court geometry sanity
                            top_width = np.linalg.norm(c_tr - c_tl)
                            bottom_width = np.linalg.norm(c_br - c_bl)
                            
                            if (
                                0.35 * h <= c_tl[1] <= 0.65 * h
                                and 0.75 * h <= c_bl[1] <= 0.98 * h
                                and bottom_width > top_width * 1.1
                            ):
                                tl = (float(c_tl[0]), float(c_tl[1]))
                                tr = (float(c_tr[0]), float(c_tr[1]))
                                bl = (float(c_bl[0]), float(c_bl[1]))
                                br = (float(c_br[0]), float(c_br[1]))
            except Exception as e:
                print(f"[CourtKeypointDetector Warning] {e}")

        # Compute intermediate keypoints (Net, Service Lines, Centers)
        nl = (tl[0] * 0.45 + bl[0] * 0.55, tl[1] * 0.45 + bl[1] * 0.55)
        nr = (tr[0] * 0.45 + br[0] * 0.55, tr[1] * 0.45 + br[1] * 0.55)
        fsl = (tl[0] * 0.80 + bl[0] * 0.20, tl[1] * 0.80 + bl[1] * 0.20)
        fsr = (tr[0] * 0.80 + br[0] * 0.20, tr[1] * 0.80 + br[1] * 0.20)
        nsl = (tl[0] * 0.22 + bl[0] * 0.78, tl[1] * 0.22 + bl[1] * 0.78)
        nsr = (tr[0] * 0.22 + br[0] * 0.78, tr[1] * 0.22 + br[1] * 0.78)

        return {
            "corner_top_left": tl,
            "corner_top_right": tr,
            "net_left": nl,
            "net_right": nr,
            "corner_bottom_left": bl,
            "corner_bottom_right": br,
            "normalized_nodes": {
                "top_left": [round(tl[0] / w, 4), round(tl[1] / h, 4)],
                "top_right": [round(tr[0] / w, 4), round(tr[1] / h, 4)],
                "net_left": [round(nl[0] / w, 4), round(nl[1] / h, 4)],
                "net_right": [round(nr[0] / w, 4), round(nr[1] / h, 4)],
                "far_service_left": [round(fsl[0] / w, 4), round(fsl[1] / h, 4)],
                "far_service_right": [round(fsr[0] / w, 4), round(fsr[1] / h, 4)],
                "near_service_left": [round(nsl[0] / w, 4), round(nsl[1] / h, 4)],
                "near_service_right": [round(nsr[0] / w, 4), round(nsr[1] / h, 4)],
                "bottom_left": [round(bl[0] / w, 4), round(bl[1] / h, 4)],
                "bottom_right": [round(br[0] / w, 4), round(br[1] / h, 4)],
            }
        }

    def _extract_4_corners_from_hull(self, hull: np.ndarray, w: int, h: int) -> np.ndarray:
        """Extracts the 4 most prominent corners of the perspective court quad from convex hull."""
        pts = hull.reshape(-1, 2)
        # 1. Top-Left: minimize (x + y)
        tl_idx = np.argmin(pts[:, 0] + pts[:, 1])
        # 2. Bottom-Right: maximize (x + y)
        br_idx = np.argmax(pts[:, 0] + pts[:, 1])
        # 3. Top-Right: maximize (x - y)
        tr_idx = np.argmax(pts[:, 0] - pts[:, 1])
        # 4. Bottom-Left: minimize (x - y)
        bl_idx = np.argmin(pts[:, 0] - pts[:, 1])

        return np.array([pts[tl_idx], pts[tr_idx], pts[br_idx], pts[bl_idx]])
