import numpy as np

from ml.equipment.racket import RacketDetector
from ml.pose.athlete_pose import AthletePoseEstimator, KEYPOINT_NAMES
from ml.tracking.racket_tracker import RacketTracker
from ml.tracking.tracker import PlayerTracker


class _ArrayAdapter:
    def __init__(self, values):
        self.values = np.asarray(values, dtype=np.float32)

    def detach(self):
        return self

    def cpu(self):
        return self

    def numpy(self):
        return self.values


class _PoseModel:
    def __init__(self, bbox, keypoints):
        boxes = type(
            "Boxes",
            (),
            {"xyxy": _ArrayAdapter([bbox]), "conf": _ArrayAdapter([0.9])},
        )()
        poses = type("Keypoints", (), {"data": _ArrayAdapter([keypoints])})()
        self.result = type("Result", (), {"boxes": boxes, "keypoints": poses})()

    def predict(self, **_kwargs):
        return [self.result]


def test_pose_estimator_attaches_named_joints_and_angles(monkeypatch):
    monkeypatch.setenv("ENABLE_POSE", "1")
    keypoints = np.zeros((len(KEYPOINT_NAMES), 3), dtype=np.float32)
    for index in range(len(KEYPOINT_NAMES)):
        keypoints[index] = [50.0 + index, 30.0 + index, 0.9]
    keypoints[KEYPOINT_NAMES.index("left_shoulder")] = [40.0, 40.0, 0.95]
    keypoints[KEYPOINT_NAMES.index("left_elbow")] = [50.0, 40.0, 0.95]
    keypoints[KEYPOINT_NAMES.index("left_wrist")] = [60.0, 40.0, 0.95]

    estimator = AthletePoseEstimator(model_path="unused.pt")
    estimator.model = _PoseModel([20.0, 10.0, 80.0, 100.0], keypoints)
    detections = [
        {
            "bbox": [20.0, 10.0, 80.0, 100.0],
            "bottom_center": [50.0, 100.0],
            "confidence": 0.9,
        }
    ]

    result = estimator.enrich(np.zeros((120, 100, 3), dtype=np.uint8), detections)

    assert result[0]["pose"]["keypoints"]["left_wrist"] == [60.0, 40.0, 0.95]
    assert result[0]["pose"]["angles"]["left_elbow"] == 180.0


def test_pose_estimator_recovers_unmatched_far_player(monkeypatch):
    monkeypatch.setenv("ENABLE_POSE", "1")
    keypoints = np.full((len(KEYPOINT_NAMES), 3), [50.0, 30.0, 0.9], dtype=np.float32)
    estimator = AthletePoseEstimator(model_path="unused.pt")
    estimator.model = _PoseModel([35.0, 15.0, 65.0, 80.0], keypoints)

    result = estimator.enrich(
        np.zeros((120, 100, 3), dtype=np.uint8), [], include_unmatched=True
    )

    assert result[0]["bbox"] == [35.0, 15.0, 65.0, 80.0]
    assert result[0]["pose"]["keypoints"]["nose"] == [50.0, 30.0, 0.9]


def test_racket_tracker_uses_wrist_for_owner_and_holds_dropout():
    players = [
        {
            "player_id": 1,
            "bbox": [0.0, 0.0, 50.0, 100.0],
            "pose": {"keypoints": {"right_wrist": [42.0, 40.0, 0.9]}},
        },
        {
            "player_id": 2,
            "bbox": [100.0, 0.0, 150.0, 100.0],
            "pose": {"keypoints": {"left_wrist": [108.0, 40.0, 0.9]}},
        },
    ]
    rackets = [
        {
            "bbox": [38.0, 30.0, 50.0, 65.0],
            "center": [44.0, 45.0],
            "confidence": 0.8,
            "source": "coco-racket",
        }
    ]
    tracker = RacketTracker()

    detected = tracker.update(rackets, players, frame_idx=10)
    held = tracker.update([], players, frame_idx=11)

    assert detected[0]["owner_id"] == 1
    assert detected[0]["keypoints"]["wrist"] == [42.0, 40.0, 0.9]
    assert set(detected[0]["keypoints"]) == {"wrist", "handle", "head_center", "tip"}
    assert held[0]["owner_id"] == 1
    assert held[0]["confidence"] < detected[0]["confidence"]


def test_racket_detector_is_noop_when_disabled(monkeypatch):
    monkeypatch.setenv("ENABLE_RACKET_DETECTION", "0")
    detector = RacketDetector(shared_model=object())

    assert detector.detect(np.zeros((32, 32, 3), dtype=np.uint8)) == []


def test_racket_tracker_handles_player_without_pose():
    tracker = RacketTracker()
    players = [{"player_id": 1, "bbox": [0.0, 0.0, 50.0, 100.0], "pose": None}]
    rackets = [{"bbox": [20.0, 20.0, 35.0, 60.0], "center": [27.5, 40.0], "confidence": 0.8}]

    assert tracker.update(rackets, players, frame_idx=1)[0]["owner_id"] == 1


def test_player_tracker_retains_pose_between_pose_intervals():
    tracker = PlayerTracker(smoothing_alpha=1.0)
    pose = {"keypoints": {"right_wrist": [30.0, 40.0, 0.9]}, "angles": {}}
    base = {
        "bbox": [10.0, 10.0, 50.0, 100.0],
        "bottom_center": [30.0, 100.0],
        "confidence": 0.9,
        "role": "near",
    }

    tracker.update([{**base, "pose": pose}], frame_idx=1)
    result = tracker.update([base], frame_idx=2)

    assert result[0]["pose"] == pose


def test_player_tracker_keeps_far_athlete_when_official_has_higher_confidence():
    tracker = PlayerTracker(smoothing_alpha=1.0)
    athlete = {
        "bbox": [280.0, 80.0, 340.0, 200.0],
        "bottom_center": [310.0, 200.0],
        "confidence": 0.7,
        "role": "far",
    }
    tracker.update([athlete], frame_idx=1)

    official = {
        "bbox": [80.0, 90.0, 140.0, 200.0],
        "bottom_center": [110.0, 200.0],
        "confidence": 0.99,
        "role": "far",
    }
    moved_athlete = {
        **athlete,
        "bbox": [290.0, 80.0, 350.0, 200.0],
        "bottom_center": [320.0, 200.0],
        "confidence": 0.65,
    }

    result = tracker.update([official, moved_athlete], frame_idx=2)

    assert result[0]["bottom_center"] == [320.0, 200.0]


def test_player_tracker_reacquires_athlete_after_broadcast_cut():
    tracker = PlayerTracker(smoothing_alpha=1.0)
    athlete = {
        "bbox": [280.0, 80.0, 340.0, 200.0],
        "bottom_center": [310.0, 200.0],
        "confidence": 0.8,
        "role": "far",
    }
    tracker.update([athlete], frame_idx=1)
    for frame_idx in range(2, 20):
        tracker.update([], frame_idx=frame_idx)

    replacement = {
        **athlete,
        "bbox": [430.0, 80.0, 490.0, 200.0],
        "bottom_center": [460.0, 200.0],
    }
    result = tracker.update([replacement], frame_idx=20)

    assert result[0]["bottom_center"] == [460.0, 200.0]
