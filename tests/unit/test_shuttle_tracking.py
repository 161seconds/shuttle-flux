from types import SimpleNamespace

import numpy as np

from ml.shuttle_detection.detector import HAS_OPENCV, ShuttleDetector
from ml.tracking.shuttle_tracker import ShuttleTrajectoryTracker


def test_tracker_bridges_configured_short_detection_gap():
    tracker = ShuttleTrajectoryTracker(max_missing_frames=6)
    detection = {
        "visible": True,
        "candidates": [{"center": [100.0, 100.0], "confidence": 0.9}],
    }
    tracker.update(detection, frame_idx=0, timestamp=0.0)

    held = [tracker.update(None, frame_idx=i, timestamp=i / 15) for i in range(1, 7)]

    assert all(point["visible"] for point in held)
    assert not any(point["observed"] for point in held)
    assert not tracker.update(None, frame_idx=7, timestamp=7 / 15)["visible"]


def test_tracker_renders_observed_position_without_ema_lag():
    tracker = ShuttleTrajectoryTracker()
    tracker.update(
        {"visible": True, "candidates": [{"center": [100.0, 100.0]}]},
        frame_idx=0,
        timestamp=0.0,
    )

    result = tracker.update(
        {"visible": True, "candidates": [{"center": [200.0, 100.0]}]},
        frame_idx=1,
        timestamp=1 / 15,
        frame_shape=(720, 1280),
    )

    assert result["observed"] is True
    assert result["center"] == [200.0, 100.0]


def test_detector_requires_motion_before_heuristic_detection(monkeypatch, tmp_path):
    if not HAS_OPENCV:
        return
    monkeypatch.setenv("SHUTTLE_MODEL_PATH", str(tmp_path / "missing.pt"))
    detector = ShuttleDetector()
    first = np.zeros((200, 300, 3), dtype=np.uint8)
    second = first.copy()
    second[80:83, 140:143] = 255

    initial = detector.detect(first)
    result = detector.detect(second)

    assert not initial["visible"]
    assert result["visible"]


def test_upper_airspace_candidate_requires_local_motion():
    previous = np.zeros((80, 120), dtype=np.uint8)
    current = previous.copy()

    assert not ShuttleDetector._has_local_motion(
        current, previous, (40.0, 10.0, 45.0, 15.0)
    )

    current[12:14, 42:44] = 255
    assert ShuttleDetector._has_local_motion(
        current, previous, (40.0, 10.0, 45.0, 15.0)
    )


def test_detector_keeps_shuttle_sliding_near_court_floor(monkeypatch, tmp_path):
    if not HAS_OPENCV:
        return
    monkeypatch.setenv("SHUTTLE_MODEL_PATH", str(tmp_path / "missing.pt"))
    detector = ShuttleDetector()
    first = np.zeros((200, 300, 3), dtype=np.uint8)
    second = first.copy()
    second[187:190, 135:149] = 255

    detector.detect(first)
    result = detector.detect(second)

    assert result["visible"]
    assert result["center"][1] > 170


def test_custom_model_uses_motion_fallback_only_for_court_floor(monkeypatch, tmp_path):
    if not HAS_OPENCV:
        return
    monkeypatch.setenv("SHUTTLE_MODEL_PATH", str(tmp_path / "missing.pt"))
    detector = ShuttleDetector()
    detector.model = lambda *args, **kwargs: [SimpleNamespace(boxes=[])]
    detector.heuristic_enabled = False
    first = np.zeros((200, 300, 3), dtype=np.uint8)
    second = first.copy()
    second[187:190, 135:149] = 255

    detector.detect(first)
    result = detector.detect(second)

    assert result["visible"]
    assert result["center"][1] > 170
