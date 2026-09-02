import numpy as np

from ml.reid.osnet import OSNetEmbedder
from ml.segmentation.sam3 import SAM3PlayerRefiner
from ml.tracking.deep_eiou import box_iou, expansion_iou, match_tracks
from ml.tracking.tracker import PlayerTracker


def _detection(x1, x2, embedding):
    return {
        "bbox": [x1, 20.0, x2, 100.0],
        "bottom_center": [(x1 + x2) / 2.0, 100.0],
        "confidence": 0.9,
        "role": "near",
        "embedding": np.asarray(embedding, dtype=np.float32),
    }


def test_expansion_iou_associates_nearby_non_overlapping_boxes():
    first = [0.0, 0.0, 10.0, 20.0]
    second = [11.0, 0.0, 21.0, 20.0]

    assert box_iou(first, second) == 0.0
    assert expansion_iou(first, second) > 0.0


def test_osnet_appearance_prevents_identity_swap_during_crossing():
    tracks = [
        _detection(0.0, 20.0, [1.0, 0.0]),
        _detection(80.0, 100.0, [0.0, 1.0]),
    ]
    crossed_detections = [
        _detection(80.0, 100.0, [1.0, 0.0]),
        _detection(0.0, 20.0, [0.0, 1.0]),
    ]

    assert match_tracks(tracks, crossed_detections) == [0, 1]


def test_tracker_does_not_expose_embeddings_in_api_records():
    tracker = PlayerTracker()
    result = tracker.update([_detection(10.0, 30.0, [1.0, 0.0])], frame_idx=1)

    assert result
    assert "embedding" not in result[0]
    assert "embedding" in tracker.tracks[1]


def test_optional_models_are_noops_when_disabled(monkeypatch, tmp_path):
    monkeypatch.setenv("ENABLE_SAM3", "0")
    monkeypatch.setenv("ENABLE_OSNET", "0")
    frame = np.zeros((120, 160, 3), dtype=np.uint8)
    detections = [_detection(10.0, 30.0, [1.0, 0.0])]

    sam = SAM3PlayerRefiner(model_path=str(tmp_path / "sam3.pt"))
    osnet = OSNetEmbedder(model_path=str(tmp_path / "osnet.onnx"))

    assert sam.refine(frame, detections) is detections
    assert osnet.attach_embeddings(frame, detections) is detections
