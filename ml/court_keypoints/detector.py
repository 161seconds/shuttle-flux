"""
Court Keypoint Detector:
Automatically detects badminton court lines, 4 boundary corners, and net posts
using computer vision (white line detection via Canny + HoughLines + intersection fitting).

Pipeline:
1. Extract white court lines using HSV brightness/saturation thresholds
2. Canny edge detection on white line mask
3. Probabilistic Hough Line Transform to find line segments
4. Classify lines into horizontal (baselines, service lines) and vertical (sidelines)
5. Find intersections between horizontal & vertical extremes → 4 court corners
6. Perspective validation (bottom width > top width * 1.3)
7. Multi-frame averaging over first N frames for stability
8. Fallback to color segmentation + convex hull if line detection fails
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
        Uses white line detection (Canny + HoughLines) as primary method,
        falls back to color segmentation + convex hull.
        """
        h, w = frame.shape[:2]

        # Default fallback corners (standard BWF broadcast perspective)
        tl = (w * 0.285, h * 0.442)
        tr = (w * 0.715, h * 0.442)
        bl = (w * 0.165, h * 0.895)
        br = (w * 0.835, h * 0.895)

        if HAS_OPENCV:
            # Method 1: White line detection (primary, most accurate)
            line_corners = self._detect_via_white_lines(frame, w, h)
            if line_corners is not None:
                tl, tr, bl, br = line_corners
            else:
                # Method 2: Color segmentation + convex hull (fallback)
                seg_corners = self._detect_via_color_segmentation(frame, w, h)
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

    def _detect_via_white_lines(
        self, frame: np.ndarray, w: int, h: int
    ) -> Optional[Tuple[Tuple[float, float], ...]]:
        """
        Primary detection: Extract white court lines using HSV thresholding,
        then find line segments via HoughLinesP, classify into horizontal/vertical,
        and compute court corners from intersections.
        """
        try:
            # Work on the court region only (bottom 62% of frame to exclude stands/scoreboard)
            court_top = int(h * 0.35)
            roi = frame[court_top:, :]
            roi_h, roi_w = roi.shape[:2]

            # Convert to HSV for white line extraction
            hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

            # White lines: high value (brightness), low saturation
            # BWF courts have bright white painted lines on green/blue mats
            white_mask = cv2.inRange(
                hsv,
                np.array([0, 0, 180]),    # low: any hue, low sat, high value
                np.array([180, 70, 255])   # high: any hue, moderate sat, max value
            )

            # Also check in grayscale for robustness
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            _, bright_mask = cv2.threshold(gray, 190, 255, cv2.THRESH_BINARY)

            # Combine both masks
            line_mask = cv2.bitwise_or(white_mask, bright_mask)

            # Remove very bright areas that might be LED panels or audience flashes
            # These tend to be large blobs, not thin lines
            kernel_open = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 1))
            kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            line_mask = cv2.morphologyEx(line_mask, cv2.MORPH_OPEN, kernel_open)
            line_mask = cv2.morphologyEx(line_mask, cv2.MORPH_CLOSE, kernel_close)

            # Mask out the left 8% and right 8% to avoid LED banner interference
            line_mask[:, :int(roi_w * 0.08)] = 0
            line_mask[:, int(roi_w * 0.92):] = 0

            # Canny edge detection on the white line mask
            edges = cv2.Canny(line_mask, 50, 150, apertureSize=3)

            # Probabilistic Hough Line Transform
            lines = cv2.HoughLinesP(
                edges,
                rho=1,
                theta=np.pi / 180,
                threshold=60,
                minLineLength=int(roi_w * 0.08),
                maxLineGap=int(roi_w * 0.03),
            )

            if lines is None or len(lines) < 4:
                return None

            # Classify lines into near-horizontal and near-vertical
            horizontals = []
            verticals = []

            for line in lines:
                x1, y1, x2, y2 = line[0]
                length = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
                if length < roi_w * 0.06:
                    continue

                dx = abs(x2 - x1)
                dy = abs(y2 - y1)

                if dx > 0:
                    angle = np.degrees(np.arctan2(dy, dx))
                else:
                    angle = 90.0

                if angle < 25:  # near-horizontal
                    avg_y = (y1 + y2) / 2.0
                    horizontals.append((x1, y1, x2, y2, avg_y, length))
                elif angle > 55:  # near-vertical
                    avg_x = (x1 + x2) / 2.0
                    verticals.append((x1, y1, x2, y2, avg_x, length))

            if len(horizontals) < 2 or len(verticals) < 2:
                return None

            # Find the topmost and bottommost horizontal lines (far baseline, near baseline)
            horizontals.sort(key=lambda l: l[4])  # sort by avg_y
            
            # Cluster horizontal lines by Y position to find distinct baselines
            h_clusters = self._cluster_lines_by_position(horizontals, axis=4, threshold=roi_h * 0.05)
            
            if len(h_clusters) < 2:
                return None

            # Top cluster = far baseline, bottom cluster = near baseline
            far_baseline_lines = h_clusters[0]
            near_baseline_lines = h_clusters[-1]

            # Find leftmost and rightmost vertical lines (left sideline, right sideline)
            verticals.sort(key=lambda l: l[4])  # sort by avg_x

            v_clusters = self._cluster_lines_by_position(verticals, axis=4, threshold=roi_w * 0.05)

            if len(v_clusters) < 2:
                return None

            left_sideline_lines = v_clusters[0]
            right_sideline_lines = v_clusters[-1]

            # Merge line segments within each cluster to get representative lines
            far_bl = self._merge_line_segments(far_baseline_lines)
            near_bl = self._merge_line_segments(near_baseline_lines)
            left_sl = self._merge_line_segments(left_sideline_lines)
            right_sl = self._merge_line_segments(right_sideline_lines)

            # Find 4 corner intersections
            c_tl = self._line_intersection(far_bl, left_sl)
            c_tr = self._line_intersection(far_bl, right_sl)
            c_bl = self._line_intersection(near_bl, left_sl)
            c_br = self._line_intersection(near_bl, right_sl)

            if any(c is None for c in [c_tl, c_tr, c_bl, c_br]):
                return None

            # Convert from ROI coordinates back to full frame coordinates
            c_tl = (c_tl[0], c_tl[1] + court_top)
            c_tr = (c_tr[0], c_tr[1] + court_top)
            c_bl = (c_bl[0], c_bl[1] + court_top)
            c_br = (c_br[0], c_br[1] + court_top)

            # Validate perspective geometry
            top_w = np.sqrt((c_tr[0] - c_tl[0]) ** 2 + (c_tr[1] - c_tl[1]) ** 2)
            bot_w = np.sqrt((c_br[0] - c_bl[0]) ** 2 + (c_br[1] - c_bl[1]) ** 2)

            if not (
                0.30 * h <= c_tl[1] <= 0.55 * h
                and 0.75 * h <= c_bl[1] <= 0.98 * h
                and bot_w > top_w * 1.15
                and top_w > w * 0.25
                and 0.05 * w <= c_tl[0] <= 0.45 * w
                and 0.55 * w <= c_tr[0] <= 0.95 * w
            ):
                return None

            return (c_tl, c_tr, c_bl, c_br)

        except Exception as e:
            print(f"[CourtKeypointDetector] White line detection error: {e}")
            return None

    def _detect_via_color_segmentation(
        self, frame: np.ndarray, w: int, h: int
    ) -> Optional[Tuple[Tuple[float, float], ...]]:
        """
        Fallback detection: Green/Blue court floor color segmentation + convex hull corner extraction.
        """
        try:
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

            # Green court mask (standard BWF green mat)
            green_mask = cv2.inRange(hsv, np.array([32, 25, 30]), np.array([85, 255, 255]))
            # Blue court mask (e.g. French Open / Sudirman Cup)
            blue_mask = cv2.inRange(hsv, np.array([92, 25, 25]), np.array([135, 255, 255]))
            court_mask = cv2.bitwise_or(green_mask, blue_mask)

            # Mask out top 35% of screen (stands, scoreboards, audience)
            court_mask[: int(h * 0.35), :] = 0
            # Mask out left/right 5% (LED banners)
            court_mask[:, :int(w * 0.05)] = 0
            court_mask[:, int(w * 0.95):] = 0

            # Morphology to connect court floor regions
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
            court_mask = cv2.morphologyEx(court_mask, cv2.MORPH_CLOSE, kernel)

            contours, _ = cv2.findContours(court_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                return None

            valid_contours = [c for c in contours if cv2.contourArea(c) > (w * h * 0.08)]
            if not valid_contours:
                return None

            largest_cnt = max(valid_contours, key=cv2.contourArea)
            hull = cv2.convexHull(largest_cnt)

            if len(hull) < 4:
                return None

            pts = self._extract_4_corners_from_hull(hull, w, h)
            if pts is None or len(pts) != 4:
                return None

            sorted_by_y = pts[np.argsort(pts[:, 1])]
            top_pts = sorted_by_y[:2]
            bottom_pts = sorted_by_y[2:]

            c_tl = top_pts[np.argmin(top_pts[:, 0])]
            c_tr = top_pts[np.argmax(top_pts[:, 0])]
            c_bl = bottom_pts[np.argmin(bottom_pts[:, 0])]
            c_br = bottom_pts[np.argmax(bottom_pts[:, 0])]

            top_w = np.linalg.norm(c_tr - c_tl)
            bot_w = np.linalg.norm(c_br - c_bl)

            # Validate sanity of detected court polygon
            if not (
                0.35 * h <= c_tl[1] <= 0.55 * h
                and 0.75 * h <= c_bl[1] <= 0.98 * h
                and bot_w > top_w * 1.15
                and (c_tr[0] - c_tl[0]) > w * 0.25
            ):
                return None

            tl = (float(c_tl[0]), float(c_tl[1]))
            tr = (float(c_tr[0]), float(c_tr[1]))
            bl = (float(c_bl[0]), float(c_bl[1]))
            br = (float(c_br[0]), float(c_br[1]))

            return (tl, tr, bl, br)

        except Exception as e:
            print(f"[CourtKeypointDetector] Color segmentation fallback error: {e}")
            return None

    def _cluster_lines_by_position(
        self, lines: List[tuple], axis: int, threshold: float
    ) -> List[List[tuple]]:
        """Groups lines into clusters by their position along the given axis index."""
        if not lines:
            return []

        sorted_lines = sorted(lines, key=lambda l: l[axis])
        clusters = [[sorted_lines[0]]]

        for line in sorted_lines[1:]:
            if abs(line[axis] - clusters[-1][-1][axis]) < threshold:
                clusters[-1].append(line)
            else:
                clusters.append([line])

        return clusters

    def _merge_line_segments(self, segments: List[tuple]) -> Tuple[float, float, float, float]:
        """Merges multiple collinear line segments into a single representative line."""
        if len(segments) == 1:
            return (segments[0][0], segments[0][1], segments[0][2], segments[0][3])

        # Find the extreme endpoints
        all_points = []
        for seg in segments:
            all_points.append((seg[0], seg[1]))
            all_points.append((seg[2], seg[3]))

        pts = np.array(all_points, dtype=np.float32)

        # Fit a line through all points
        vx, vy, cx, cy = cv2.fitLine(pts, cv2.DIST_L2, 0, 0.01, 0.01).flatten()

        # Project all points onto the line direction to find extremes
        projections = [(p[0] - cx) * vx + (p[1] - cy) * vy for p in all_points]
        min_proj = min(projections)
        max_proj = max(projections)

        x1 = cx + min_proj * vx
        y1 = cy + min_proj * vy
        x2 = cx + max_proj * vx
        y2 = cy + max_proj * vy

        return (float(x1), float(y1), float(x2), float(y2))

    def _line_intersection(
        self, line1: Tuple[float, ...], line2: Tuple[float, ...]
    ) -> Optional[Tuple[float, float]]:
        """Computes the intersection point of two line segments (extended to full lines)."""
        x1, y1, x2, y2 = line1[:4]
        x3, y3, x4, y4 = line2[:4]

        denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(denom) < 1e-6:
            return None  # Parallel lines

        t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom

        ix = x1 + t * (x2 - x1)
        iy = y1 + t * (y2 - y1)

        return (float(ix), float(iy))

    def _average_corners(self) -> Dict[str, Tuple[float, float]]:
        """Computes the median of accumulated corner history for stability."""
        keys = ["tl", "tr", "bl", "br"]
        result = {}
        for key in keys:
            xs = [c[key][0] for c in self._corner_history]
            ys = [c[key][1] for c in self._corner_history]
            result[key] = (float(np.median(xs)), float(np.median(ys)))
        return result

    def _extract_4_corners_from_hull(self, hull: np.ndarray, w: int, h: int) -> Optional[np.ndarray]:
        """Extracts the 4 most prominent corners of the perspective court quad from convex hull."""
        pts = hull.reshape(-1, 2).astype(np.float32)
        if len(pts) < 4:
            return None

        # 1. Top-Left: minimize (x + y)
        tl_idx = np.argmin(pts[:, 0] + pts[:, 1])
        # 2. Bottom-Right: maximize (x + y)
        br_idx = np.argmax(pts[:, 0] + pts[:, 1])
        # 3. Top-Right: maximize (x - y)
        tr_idx = np.argmax(pts[:, 0] - pts[:, 1])
        # 4. Bottom-Left: minimize (x - y)
        bl_idx = np.argmin(pts[:, 0] - pts[:, 1])

        return np.array([pts[tl_idx], pts[tr_idx], pts[br_idx], pts[bl_idx]])
