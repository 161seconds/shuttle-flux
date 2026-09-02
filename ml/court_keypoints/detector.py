"""Automatic BWF court-line detection and perspective calibration."""

import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ml.court_keypoints.template import (
    COURT_LINES,
    HORIZONTAL_LINE_POSITIONS,
    NET_Y,
    SHORT_SERVICE_FAR_Y,
    SHORT_SERVICE_NEAR_Y,
    VERTICAL_LINE_POSITIONS,
)

try:
    import cv2

    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False


Point = Tuple[float, float]


def _homogeneous_line(first: Point, second: Point) -> np.ndarray:
    line = np.cross(
        np.asarray([first[0], first[1], 1.0], dtype=np.float64),
        np.asarray([second[0], second[1], 1.0], dtype=np.float64),
    )
    return line / max(float(np.hypot(line[0], line[1])), 1e-9)


def _intersection(first: np.ndarray, second: np.ndarray) -> Optional[Point]:
    point = np.cross(first, second)
    if abs(point[2]) <= 1e-8:
        return None
    return float(point[0] / point[2]), float(point[1] / point[2])


def _line_x_at_y(line: np.ndarray, y: float) -> float:
    if abs(line[0]) <= 1e-8:
        return float("inf")
    return float(-(line[1] * y + line[2]) / line[0])


def _line_y_at_x(line: np.ndarray, x: float) -> float:
    if abs(line[1]) <= 1e-8:
        return float("inf")
    return float(-(line[0] * x + line[2]) / line[1])


class CourtKeypointDetector:
    """Fits the complete BWF line template instead of guessing four floor corners."""

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path
        self._best_result: Optional[Dict[str, Any]] = None

    def detect_keypoints(self, frame: np.ndarray) -> Dict[str, Any]:
        height, width = frame.shape[:2]
        if not HAS_OPENCV:
            return self._fallback_result(width, height)

        try:
            result = self._detect_lines(frame)
        except Exception as exc:
            print(f"[CourtKeypointDetector] Court-line detection failed: {exc}")
            result = None

        if result is not None and (
            self._best_result is None
            or result["calibration"]["confidence"]
            > self._best_result["calibration"]["confidence"]
        ):
            self._best_result = result
        return self._best_result or self._fallback_result(width, height)

    @staticmethod
    def _court_masks(frame: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        height, width = frame.shape[:2]
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Estimate the playing-surface hue from the central lower image. This
        # separates the court from similarly bright advertising and surrounds.
        roi = hsv[
            int(height * 0.52) : int(height * 0.92),
            int(width * 0.18) : int(width * 0.82),
        ]
        usable = roi[(roi[:, :, 1] >= 18) & (roi[:, :, 2] >= 45)]
        if len(usable):
            histogram = np.bincount(usable[:, 0], minlength=180).astype(np.float32)
            histogram = np.convolve(histogram, np.ones(13), mode="same")
            floor_hue = int(np.argmax(histogram))
        else:
            floor_hue = 72

        hue = hsv[:, :, 0].astype(np.int16)
        hue_delta = np.abs(hue - floor_hue)
        hue_delta = np.minimum(hue_delta, 180 - hue_delta)
        colored_floor = np.where(
            (hue_delta <= 22) & (hsv[:, :, 1] >= 16) & (hsv[:, :, 2] >= 38),
            255,
            0,
        ).astype(np.uint8)
        colored_floor[: int(height * 0.18), :] = 0
        colored_floor = cv2.morphologyEx(
            colored_floor,
            cv2.MORPH_CLOSE,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25)),
        )
        contours, _ = cv2.findContours(
            colored_floor, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        court_region = np.zeros_like(colored_floor)
        valid = [
            contour
            for contour in contours
            if cv2.contourArea(contour) > width * height * 0.04
        ]
        if valid:
            target = (width * 0.50, height * 0.70)
            containing_target = [
                contour
                for contour in valid
                if cv2.pointPolygonTest(contour, target, False) >= 0
            ]
            selected_floor = max(
                containing_target or valid,
                key=cv2.contourArea,
            )
            cv2.drawContours(
                court_region, [selected_floor], -1, 255, -1
            )
            court_region = cv2.dilate(
                court_region,
                cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (17, 17)),
            )
        else:
            court_region[int(height * 0.30) :, :] = 255

        white = cv2.inRange(
            hsv,
            np.array([0, 0, 205], dtype=np.uint8),
            np.array([180, 58, 255], dtype=np.uint8),
        )
        yellow = cv2.inRange(
            hsv,
            np.array([14, 65, 120], dtype=np.uint8),
            np.array([38, 255, 255], dtype=np.uint8),
        )
        background = cv2.GaussianBlur(gray, (0, 0), sigmaX=6.0, sigmaY=6.0)
        local_contrast = cv2.subtract(gray, background)
        contrast_lines = cv2.inRange(local_contrast, 14, 255)
        contrast_lines = cv2.bitwise_and(
            contrast_lines,
            cv2.inRange(hsv, np.array([0, 0, 145]), np.array([180, 145, 255])),
        )
        bright_lines = cv2.bitwise_and(
            cv2.bitwise_or(cv2.bitwise_or(white, yellow), contrast_lines),
            court_region,
        )
        bright_lines = cv2.morphologyEx(
            bright_lines,
            cv2.MORPH_CLOSE,
            cv2.getStructuringElement(cv2.MORPH_RECT, (5, 3)),
        )

        edges = cv2.bitwise_and(cv2.Canny(gray, 60, 160), court_region)
        return bright_lines, cv2.bitwise_or(edges, bright_lines)

    @staticmethod
    def _extract_line_candidates(
        mask: np.ndarray,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        height, width = mask.shape
        raw = cv2.HoughLinesP(
            mask,
            1,
            np.pi / 1440.0,
            threshold=max(18, int(min(width, height) * 0.05)),
            minLineLength=max(25, int(min(width, height) * 0.075)),
            maxLineGap=max(10, int(min(width, height) * 0.04)),
        )
        if raw is None:
            return [], []

        longitudinal = []
        transverse = []
        reference_y = height * 0.82
        reference_x = width * 0.50
        for segment in np.asarray(raw).reshape(-1, 4):
            x1, y1, x2, y2 = (float(value) for value in segment)
            dx, dy = x2 - x1, y2 - y1
            length = float(np.hypot(dx, dy))
            if length <= 1.0:
                continue
            line = _homogeneous_line((x1, y1), (x2, y2))
            angle = math.degrees(math.atan2(dy, dx)) % 180.0
            candidate = {
                "line": line,
                "length": length,
                "angle": angle,
                "segment": (x1, y1, x2, y2),
            }
            horizontal_angle = min(angle, 180.0 - angle)
            if horizontal_angle <= 18.0:
                y_ref = _line_y_at_x(line, reference_x)
                if height * 0.25 <= y_ref <= height * 1.15:
                    candidate["reference"] = y_ref
                    transverse.append(candidate)
            elif 24.0 <= angle <= 166.0 and abs(dy) >= abs(dx) * 0.28:
                x_ref = _line_x_at_y(line, reference_y)
                if -width * 0.35 <= x_ref <= width * 1.35:
                    candidate["reference"] = x_ref
                    longitudinal.append(candidate)

        return (
            CourtKeypointDetector._deduplicate(
                longitudinal, max(9.0, width * 0.014)
            ),
            CourtKeypointDetector._deduplicate(
                transverse, max(7.0, height * 0.018)
            ),
        )

    @staticmethod
    def _deduplicate(
        candidates: List[Dict[str, Any]], position_tolerance: float
    ) -> List[Dict[str, Any]]:
        selected: List[Dict[str, Any]] = []
        for candidate in sorted(
            candidates, key=lambda item: item["length"], reverse=True
        ):
            duplicate = False
            for existing in selected:
                angle_delta = abs(candidate["angle"] - existing["angle"])
                angle_delta = min(angle_delta, 180.0 - angle_delta)
                if (
                    abs(candidate["reference"] - existing["reference"])
                    < position_tolerance
                    and angle_delta < 7.0
                ):
                    duplicate = True
                    break
            if not duplicate:
                selected.append(candidate)
        return selected[:18]

    @staticmethod
    def _project_points(homography: np.ndarray, points: np.ndarray) -> np.ndarray:
        return cv2.perspectiveTransform(
            points.astype(np.float32).reshape(-1, 1, 2), homography
        ).reshape(-1, 2)

    def _score_quad(
        self, line_mask: np.ndarray, quad: np.ndarray
    ) -> Tuple[float, int, Dict[str, float]]:
        source = np.asarray(
            [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
            dtype=np.float32,
        )
        homography = cv2.getPerspectiveTransform(source, quad.astype(np.float32))
        distance = cv2.distanceTransform(255 - line_mask, cv2.DIST_L2, 3)
        height, width = line_mask.shape
        scores: Dict[str, float] = {}
        weighted_sum = 0.0
        total_weight = 0.0
        for name, (start, end) in COURT_LINES.items():
            count = 70 if start[0] == end[0] else 55
            samples = np.linspace(start, end, count, dtype=np.float32)
            projected = self._project_points(homography, samples)
            valid = (
                (projected[:, 0] >= 0)
                & (projected[:, 0] < width)
                & (projected[:, 1] >= 0)
                & (projected[:, 1] < height)
            )
            visibility = float(valid.mean())
            if visibility < 0.22:
                scores[name] = 0.0
                continue
            visible = projected[valid]
            xs = np.clip(np.rint(visible[:, 0]).astype(int), 0, width - 1)
            ys = np.clip(np.rint(visible[:, 1]).astype(int), 0, height - 1)
            support = float(
                np.exp(-np.square(distance[ys, xs]) / (2.0 * 4.0**2)).mean()
            )
            support *= visibility**0.35
            scores[name] = support
            weight = (
                0.65
                if name.startswith("outer_") or name.endswith("baseline")
                else 1.0
            )
            if name.startswith("center_"):
                weight = 0.55
            weighted_sum += support * weight
            total_weight += weight
        score = weighted_sum / total_weight if total_weight else 0.0
        return float(score), sum(value >= 0.34 for value in scores.values()), scores

    @staticmethod
    def _valid_quad(quad: np.ndarray, width: int, height: int) -> bool:
        if not np.all(np.isfinite(quad)):
            return False
        tl, tr, br, bl = quad
        top_width = float(np.linalg.norm(tr - tl))
        bottom_width = float(np.linalg.norm(br - bl))
        top_y = float((tl[1] + tr[1]) / 2.0)
        bottom_y = float((bl[1] + br[1]) / 2.0)
        depth = float(((bl[1] + br[1]) - (tl[1] + tr[1])) / 2.0)
        area = abs(float(cv2.contourArea(quad.astype(np.float32))))
        if tl[0] >= tr[0] or bl[0] >= br[0]:
            return False
        if top_width < width * 0.24 or bottom_width < width * 0.45:
            return False
        if not (height * 0.18 <= top_y <= height * 0.74):
            return False
        if bottom_y < height * 0.84:
            return False
        if depth < height * 0.20 or area < width * height * 0.10:
            return False
        if bottom_width < top_width * 0.72:
            return False
        return bool(
            np.all(quad[:, 0] > -width * 0.50)
            and np.all(quad[:, 0] < width * 1.50)
            and np.all(quad[:, 1] > height * 0.18)
            and np.all(quad[:, 1] < height * 1.45)
        )

    def _choose_outer_quad(
        self,
        line_mask: np.ndarray,
        longitudinal: List[Dict[str, Any]],
        transverse: List[Dict[str, Any]],
    ) -> Optional[Tuple[np.ndarray, float, int, Dict[str, float]]]:
        height, width = line_mask.shape
        left = sorted(
            [item for item in longitudinal if item["reference"] < width * 0.52],
            key=lambda item: item["reference"],
        )[:7]
        right = sorted(
            [item for item in longitudinal if item["reference"] > width * 0.48],
            key=lambda item: item["reference"],
            reverse=True,
        )[:7]
        horizontal = sorted(transverse, key=lambda item: item["reference"])
        top = [
            item
            for item in horizontal
            if height * 0.30 <= item["reference"] <= height * 0.76
        ][:7]
        bottom = [
            item for item in horizontal if item["reference"] >= height * 0.62
        ][-7:]
        bottom.reverse()
        if not left or not right or not top or not bottom:
            return None

        best = None
        best_rank = -1.0
        for left_line in left:
            for right_line in right:
                for top_line in top:
                    for bottom_line in bottom:
                        if top_line is bottom_line:
                            continue
                        points = (
                            _intersection(left_line["line"], top_line["line"]),
                            _intersection(right_line["line"], top_line["line"]),
                            _intersection(right_line["line"], bottom_line["line"]),
                            _intersection(left_line["line"], bottom_line["line"]),
                        )
                        if any(point is None for point in points):
                            continue
                        quad = np.asarray(points, dtype=np.float32)
                        if not self._valid_quad(quad, width, height):
                            continue
                        score, detected, line_scores = self._score_quad(
                            line_mask, quad
                        )
                        rank = score + min(0.08, detected * 0.006)
                        if rank > best_rank:
                            best_rank = rank
                            best = quad, score, detected, line_scores
        return best

    @staticmethod
    def _axis_peak(
        warped_mask: np.ndarray,
        expected: int,
        axis: int,
        spans: Tuple[Tuple[int, int], ...],
        radius: int,
    ) -> Tuple[int, float]:
        height, width = warped_mask.shape
        limit = width if axis == 0 else height
        start = max(0, expected - radius)
        end = min(limit - 1, expected + radius)
        best_position = expected
        best_score = 0.0
        for position in range(start, end + 1):
            samples = []
            if axis == 0:
                x1, x2 = max(0, position - 2), min(width, position + 3)
                for span_start, span_end in spans:
                    samples.append(warped_mask[span_start:span_end, x1:x2])
            else:
                y1, y2 = max(0, position - 2), min(height, position + 3)
                for span_start, span_end in spans:
                    samples.append(warped_mask[y1:y2, span_start:span_end])
            nonempty = [sample for sample in samples if sample.size]
            if not nonempty:
                continue
            score = float(
                np.concatenate([sample.reshape(-1) for sample in nonempty]).mean()
                / 255.0
            )
            if score > best_score:
                best_position, best_score = position, score
        return best_position, best_score

    def _refine_from_template(
        self, line_mask: np.ndarray, quad: np.ndarray
    ) -> Tuple[
        np.ndarray,
        List[List[float]],
        List[List[float]],
        Dict[str, float],
        float,
    ]:
        court_width, court_height, margin = 366, 804, 32
        destination = np.asarray(
            [
                (margin, margin),
                (margin + court_width, margin),
                (margin + court_width, margin + court_height),
                (margin, margin + court_height),
            ],
            dtype=np.float32,
        )
        image_to_warp = cv2.getPerspectiveTransform(
            quad.astype(np.float32), destination
        )
        warped = cv2.warpPerspective(
            line_mask,
            image_to_warp,
            (court_width + margin * 2, court_height + margin * 2),
        )
        warped = cv2.morphologyEx(
            warped,
            cv2.MORPH_CLOSE,
            cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)),
        )

        detected_x = {}
        for name, (x_norm, spans_norm) in VERTICAL_LINE_POSITIONS.items():
            expected = int(round(margin + x_norm * court_width))
            spans = tuple(
                (
                    int(round(margin + start * court_height)),
                    int(round(margin + end * court_height)),
                )
                for start, end in spans_norm
            )
            position, score = self._axis_peak(
                warped, expected, 0, spans, radius=18
            )
            if score >= 0.10:
                detected_x[name] = (position, score, x_norm, spans_norm)

        detected_y = {}
        horizontal_span = ((margin, margin + court_width),)
        for name, y_norm in HORIZONTAL_LINE_POSITIONS.items():
            expected = int(round(margin + y_norm * court_height))
            position, score = self._axis_peak(
                warped, expected, 1, horizontal_span, radius=24
            )
            if score >= 0.10:
                detected_y[name] = (position, score, y_norm)

        warp_to_image = np.linalg.inv(image_to_warp)
        source_points: List[List[float]] = []
        court_points: List[List[float]] = []
        peak_scores = {
            name: round(values[1], 3) for name, values in detected_x.items()
        }
        peak_scores.update(
            {name: round(values[1], 3) for name, values in detected_y.items()}
        )

        for x_position, _, x_norm, spans_norm in detected_x.values():
            for y_position, _, y_norm in detected_y.values():
                if not any(
                    start - 1e-6 <= y_norm <= end + 1e-6
                    for start, end in spans_norm
                ):
                    continue
                image_point = self._project_points(
                    warp_to_image,
                    np.asarray([(x_position, y_position)], dtype=np.float32),
                )[0]
                source_points.append(
                    [float(image_point[0]), float(image_point[1])]
                )
                court_points.append([float(x_norm), float(y_norm)])

        if len(source_points) >= 6:
            homography, inliers = cv2.findHomography(
                np.asarray(source_points, dtype=np.float32),
                np.asarray(court_points, dtype=np.float32),
                cv2.RANSAC,
                0.018,
            )
        else:
            homography = cv2.getPerspectiveTransform(
                quad.astype(np.float32),
                np.asarray(
                    [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
                    dtype=np.float32,
                ),
            )
            inliers = None
        if homography is None:
            raise ValueError("Could not refine court homography")

        projected = (
            self._project_points(
                homography, np.asarray(source_points, dtype=np.float32)
            )
            if source_points
            else np.empty((0, 2))
        )
        target = np.asarray(court_points, dtype=np.float32)
        error = (
            float(np.linalg.norm(projected - target, axis=1).mean())
            if len(projected)
            else 0.0
        )
        if inliers is not None:
            keep = inliers.reshape(-1).astype(bool)
            source_points = np.asarray(source_points)[keep].astype(float).tolist()
            court_points = np.asarray(court_points)[keep].astype(float).tolist()
        return homography, source_points, court_points, peak_scores, error

    def _build_result(
        self,
        homography: np.ndarray,
        source_points: List[List[float]],
        court_points: List[List[float]],
        width: int,
        height: int,
        initial_score: float,
        initial_detected: int,
        peak_scores: Dict[str, float],
        reprojection_error: float,
    ) -> Dict[str, Any]:
        inverse = np.linalg.inv(homography)

        def image_point(point: Point) -> Point:
            projected = self._project_points(
                inverse, np.asarray([point], dtype=np.float32)
            )[0]
            return float(projected[0]), float(projected[1])

        node_template = {
            "top_left": (0.0, 0.0),
            "top_right": (1.0, 0.0),
            "far_doubles_left": (
                0.0,
                HORIZONTAL_LINE_POSITIONS["far_doubles_service"],
            ),
            "far_doubles_right": (
                1.0,
                HORIZONTAL_LINE_POSITIONS["far_doubles_service"],
            ),
            "far_service_left": (0.0, SHORT_SERVICE_FAR_Y),
            "far_service_center": (0.5, SHORT_SERVICE_FAR_Y),
            "far_service_right": (1.0, SHORT_SERVICE_FAR_Y),
            "net_left": (0.0, NET_Y),
            "net_center": (0.5, NET_Y),
            "net_right": (1.0, NET_Y),
            "near_service_left": (0.0, SHORT_SERVICE_NEAR_Y),
            "near_service_center": (0.5, SHORT_SERVICE_NEAR_Y),
            "near_service_right": (1.0, SHORT_SERVICE_NEAR_Y),
            "near_doubles_left": (
                0.0,
                HORIZONTAL_LINE_POSITIONS["near_doubles_service"],
            ),
            "near_doubles_right": (
                1.0,
                HORIZONTAL_LINE_POSITIONS["near_doubles_service"],
            ),
            "bottom_left": (0.0, 1.0),
            "bottom_right": (1.0, 1.0),
        }
        normalized_nodes = {}
        for name, point in node_template.items():
            x, y = image_point(point)
            normalized_nodes[name] = [round(x / width, 4), round(y / height, 4)]

        line_segments = {}
        line_scores = {}
        for name, (start, end) in COURT_LINES.items():
            first, second = image_point(start), image_point(end)
            base_name = "center" if name.startswith("center_") else name
            line_segments[name] = [
                [round(first[0] / width, 4), round(first[1] / height, 4)],
                [round(second[0] / width, 4), round(second[1] / height, 4)],
            ]
            line_scores[name] = peak_scores.get(base_name, 0.0)

        peak_mean = (
            float(np.mean(list(peak_scores.values()))) if peak_scores else 0.0
        )
        detected_line_count = sum(score >= 0.10 for score in peak_scores.values())
        confidence = float(
            np.clip(
                0.50 * initial_score
                + 0.35 * peak_mean
                + 0.15 * min(1.0, detected_line_count / 9.0)
                - min(0.15, reprojection_error * 3.0),
                0.0,
                1.0,
            )
        )
        tl, tr, br, bl = (
            image_point(point) for point in ((0, 0), (1, 0), (1, 1), (0, 1))
        )
        return {
            "corner_top_left": tl,
            "corner_top_right": tr,
            "net_left": image_point((0.0, NET_Y)),
            "net_right": image_point((1.0, NET_Y)),
            "corner_bottom_left": bl,
            "corner_bottom_right": br,
            "normalized_nodes": normalized_nodes,
            "line_segments": line_segments,
            "calibration": {
                "source": "bwf-line-template",
                "confidence": round(confidence, 3),
                "detected_line_count": detected_line_count,
                "initial_detected_line_count": initial_detected,
                "reprojection_error_norm": round(reprojection_error, 5),
                "used_fallback": False,
                "line_scores": line_scores,
                "image_points": source_points,
                "court_points_norm": court_points,
            },
        }

    def _detect_lines(self, frame: np.ndarray) -> Optional[Dict[str, Any]]:
        height, width = frame.shape[:2]
        line_mask, hough_mask = self._court_masks(frame)
        longitudinal, transverse = self._extract_line_candidates(hough_mask)
        selected = self._choose_outer_quad(
            line_mask, longitudinal, transverse
        )
        if selected is None:
            return None
        quad, initial_score, initial_detected, _ = selected
        homography, source_points, court_points, peak_scores, error = (
            self._refine_from_template(line_mask, quad)
        )
        return self._build_result(
            homography,
            source_points,
            court_points,
            width,
            height,
            initial_score,
            initial_detected,
            peak_scores,
            error,
        )

    @staticmethod
    def _fallback_result(width: int, height: int) -> Dict[str, Any]:
        return {
            "corner_top_left": (width * 0.285, height * 0.442),
            "corner_top_right": (width * 0.715, height * 0.442),
            "net_left": (width * 0.236, height * 0.533),
            "net_right": (width * 0.764, height * 0.533),
            "corner_bottom_left": (width * 0.165, height * 0.895),
            "corner_bottom_right": (width * 0.835, height * 0.895),
            "normalized_nodes": {
                "top_left": [0.285, 0.442],
                "top_right": [0.715, 0.442],
                "net_left": [0.236, 0.533],
                "net_right": [0.764, 0.533],
                "bottom_left": [0.165, 0.895],
                "bottom_right": [0.835, 0.895],
            },
            "line_segments": {},
            "calibration": {
                "source": "legacy-fallback",
                "confidence": 0.0,
                "detected_line_count": 0,
                "reprojection_error_norm": None,
                "used_fallback": True,
                "line_scores": {},
                "image_points": [],
                "court_points_norm": [],
            },
        }
