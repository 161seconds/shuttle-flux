import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from ml.court_keypoints.detector import CourtKeypointDetector
from ml.court_keypoints.template import COURT_LINES


def _synthetic_court():
    height, width = 540, 960
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:] = (90, 35, 25)
    corners = np.asarray(
        [(330, 150), (700, 175), (850, 515), (100, 500)],
        dtype=np.float32,
    )
    cv2.fillConvexPoly(frame, corners.astype(np.int32), (95, 170, 110))
    homography = cv2.getPerspectiveTransform(
        np.asarray([(0, 0), (1, 0), (1, 1), (0, 1)], dtype=np.float32),
        corners,
    )
    for start, end in COURT_LINES.values():
        projected = cv2.perspectiveTransform(
            np.asarray([start, end], dtype=np.float32).reshape(-1, 1, 2),
            homography,
        ).reshape(-1, 2)
        cv2.line(
            frame,
            tuple(np.rint(projected[0]).astype(int)),
            tuple(np.rint(projected[1]).astype(int)),
            (245, 245, 245),
            5,
        )

    # Simulate a player obscuring several intersections.
    cv2.rectangle(frame, (430, 250), (535, 435), (65, 80, 170), -1)
    return frame, corners


def test_detector_recovers_bwf_template_under_perspective_and_occlusion():
    frame, expected = _synthetic_court()
    result = CourtKeypointDetector().detect_keypoints(frame)
    calibration = result["calibration"]
    actual = np.asarray(
        [
            result["corner_top_left"],
            result["corner_top_right"],
            result["corner_bottom_right"],
            result["corner_bottom_left"],
        ],
        dtype=np.float32,
    )

    assert calibration["used_fallback"] is False
    assert calibration["confidence"] >= 0.8
    assert calibration["detected_line_count"] >= 9
    assert calibration["reprojection_error_norm"] < 0.02
    assert np.max(np.linalg.norm(actual - expected, axis=1)) < 12.0
    assert set(result["line_segments"]) == set(COURT_LINES)


def test_detector_marks_blank_frame_as_fallback():
    result = CourtKeypointDetector().detect_keypoints(
        np.zeros((360, 640, 3), dtype=np.uint8)
    )

    assert result["calibration"]["used_fallback"] is True
    assert result["calibration"]["confidence"] == 0.0
    assert result["line_segments"] == {}


def test_net_overlay_requires_visible_top_tape():
    frame = np.zeros((360, 640, 3), dtype=np.uint8)
    floor_left = (160.0, 240.0)
    floor_right = (480.0, 240.0)

    assert CourtKeypointDetector._detect_net(frame, floor_left, floor_right) is None

    cv2.line(frame, (155, 170), (485, 170), (255, 255, 255), 5)
    net = CourtKeypointDetector._detect_net(frame, floor_left, floor_right)

    assert net is not None
    assert abs(net["top_left"][1] - 170.0) < 5.0
    assert net["bottom_left"][1] < floor_left[1]
