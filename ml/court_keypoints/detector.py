"""
Court Keypoint Detector:
Automatically detects badminton court lines, 4 boundary corners, and net posts
using computer vision (color segmentation + extreme points of the largest contour).

Pipeline:
1. Color segmentation (green/blue court mat)
2. Morphological operations to clean up mask
3. Find the largest contour (the court floor)
4. Extract Extreme Points (top-left, top-right, bottom-left, bottom-right)
5. Multi-frame averaging over first N frames for stability
6. Soft validation logic to ensure it doesn't fail on perfectly valid courts
"""

from typing import Dict, Tuple, Optional, Any, List
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
        # Multi-frame corner buffer for averaging stability
        self._corner_history: List[Dict[str, Tuple[float, float]]] = []
        self._stable_corners: Optional[Dict[str, Tuple[float, float]]] = None
        self._max_history = 5

    def detect_keypoints(self, frame: np.ndarray) -> Dict[str, Any]:
        """
        Detects the 4 court corners and net landmarks dynamically from video frame.
        Uses robust Extreme Points color segmentation.
        """
        h, w = frame.shape[:2]

        # Default fallback corners (standard BWF broadcast perspective)
        tl = (w * 0.285, h * 0.442)
        tr = (w * 0.715, h * 0.442)
        bl = (w * 0.165, h * 0.895)
        br = (w * 0.835, h * 0.895)

        if HAS_OPENCV:
            seg_corners = self._detect_via_extreme_points(frame, w, h)
            if seg_corners is not None:
                tl, tr, bl, br = seg_corners

            # Multi-frame averaging for stability
            current = {"tl": tl, "tr": tr, "bl": bl, "br": br}
            self._corner_history.append(current)
            if len(self._corner_history) > self._max_history:
                self._corner_history.pop(0)

            if len(self._corner_history) >= 2:
                avg = self._average_corners()
                tl, tr, bl, br = avg["tl"], avg["tr"], avg["bl"], avg["br"]
                self._stable_corners = avg

        # Compute key court landmarks using perspective foreshortening
        # Net at center of 3D court (6.70m / 13.40m = 50%), projects to ~20% in foreshortened 2D Y
        dxL = bl[0] - tl[0]
        dyL = bl[1] - tl[1]
        dxR = br[0] - tr[0]
        dyR = br[1] - tr[1]

        nl_x = tl[0] + 0.20 * dxL - w * 0.025
        nl_y = tl[1] + 0.20 * dyL
        nr_x = tr[0] + 0.20 * dxR + w * 0.025
        nr_y = tr[1] + 0.20 * dyR

        # Far Short Service Line (t = 0.35 -> factor 0.118)
        fsl_x = tl[0] + 0.118 * dxL
        fsl_y = tl[1] + 0.118 * dyL
        fsr_x = tr[0] + 0.118 * dxR
        fsr_y = tr[1] + 0.118 * dyR

        # Near Short Service Line (t = 0.65 -> factor 0.317)
        nsl_x = tl[0] + 0.317 * dxL
        nsl_y = tl[1] + 0.317 * dyL
        nsr_x = tr[0] + 0.317 * dxR
        nsr_y = tr[1] + 0.317 * dyR

        return {
            "corner_top_left": tl,
            "corner_top_right": tr,
            "net_left": (nl_x, nl_y),
            "net_right": (nr_x, nr_y),
            "corner_bottom_left": bl,
            "corner_bottom_right": br,
            "normalized_nodes": {
                "top_left": [round(tl[0] / w, 4), round(tl[1] / h, 4)],
                "top_right": [round(tr[0] / w, 4), round(tr[1] / h, 4)],
                "net_left": [round(nl_x / w, 4), round(nl_y / h, 4)],
                "net_right": [round(nr_x / w, 4), round(nr_y / h, 4)],
                "far_service_left": [round(fsl_x / w, 4), round(fsl_y / h, 4)],
                "far_service_right": [round(fsr_x / w, 4), round(fsr_y / h, 4)],
                "near_service_left": [round(nsl_x / w, 4), round(nsl_y / h, 4)],
                "near_service_right": [round(nsr_x / w, 4), round(nsr_y / h, 4)],
                "bottom_left": [round(bl[0] / w, 4), round(bl[1] / h, 4)],
                "bottom_right": [round(br[0] / w, 4), round(br[1] / h, 4)],
            }
        }

    def _detect_via_extreme_points(
        self, frame: np.ndarray, w: int, h: int
    ) -> Optional[Tuple[Tuple[float, float], ...]]:
        """
        Detection: Green/Blue court floor color segmentation + Extreme Points.
        """
        try:
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

            # Green court mask (standard BWF green mat)
            green_mask = cv2.inRange(hsv, np.array([32, 25, 30]), np.array([85, 255, 255]))
            # Blue court mask (e.g. French Open / Sudirman Cup)
            blue_mask = cv2.inRange(hsv, np.array([92, 25, 25]), np.array([135, 255, 255]))
            court_mask = cv2.bitwise_or(green_mask, blue_mask)

            # Aggressive masking to avoid audience, LED boards, and umpires
            court_mask[: int(h * 0.35), :] = 0  # Top 35% (Stands/Scoreboard)
            court_mask[:, :int(w * 0.10)] = 0   # Left 10% (LED/Umpires)
            court_mask[:, int(w * 0.90):] = 0   # Right 10% (LED/Umpires)

            # Morphology to connect court floor regions
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
            court_mask = cv2.morphologyEx(court_mask, cv2.MORPH_CLOSE, kernel)
            kernel_open = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
            court_mask = cv2.morphologyEx(court_mask, cv2.MORPH_OPEN, kernel_open)

            contours, _ = cv2.findContours(court_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                return None

            # Filter out tiny noise blobs
            valid_contours = [c for c in contours if cv2.contourArea(c) > (w * h * 0.05)]
            if not valid_contours:
                return None

            # The largest contour should be the main court mat
            largest_cnt = max(valid_contours, key=cv2.contourArea)
            pts = largest_cnt.reshape(-1, 2)

            if len(pts) < 4:
                return None

            # Find Extreme Points (Top-Left, Top-Right, Bottom-Left, Bottom-Right)
            # 1. Top-Left: minimize (x + y)
            tl_idx = np.argmin(pts[:, 0] + pts[:, 1])
            # 2. Bottom-Right: maximize (x + y)
            br_idx = np.argmax(pts[:, 0] + pts[:, 1])
            # 3. Top-Right: maximize (x - y)
            tr_idx = np.argmax(pts[:, 0] - pts[:, 1])
            # 4. Bottom-Left: minimize (x - y)
            bl_idx = np.argmin(pts[:, 0] - pts[:, 1])

            c_tl = pts[tl_idx]
            c_tr = pts[tr_idx]
            c_br = pts[br_idx]
            c_bl = pts[bl_idx]

            # Soft Validation: ensure basic trapezoid shape
            top_w = np.linalg.norm(c_tr - c_tl)
            bot_w = np.linalg.norm(c_br - c_bl)
            
            # Very loose validation to ensure it almost always returns a result if a big green/blue blob exists
            if (c_tl[1] < h * 0.65) and (c_bl[1] > h * 0.70) and (bot_w > top_w * 1.05):
                tl = (float(c_tl[0]), float(c_tl[1]))
                tr = (float(c_tr[0]), float(c_tr[1]))
                bl = (float(c_bl[0]), float(c_bl[1]))
                br = (float(c_br[0]), float(c_br[1]))
                return (tl, tr, bl, br)
            
            return None

        except Exception as e:
            print(f"[CourtKeypointDetector] Extreme points extraction error: {e}")
            return None

    def _average_corners(self) -> Dict[str, Tuple[float, float]]:
        """Computes the median of accumulated corner history for stability."""
        keys = ["tl", "tr", "bl", "br"]
        result = {}
        for key in keys:
            xs = [c[key][0] for c in self._corner_history]
            ys = [c[key][1] for c in self._corner_history]
            result[key] = (float(np.median(xs)), float(np.median(ys)))
        return result
