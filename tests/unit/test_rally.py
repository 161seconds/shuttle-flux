"""
Unit tests for Rally segmentation state machine.
"""

from analytics.rally import RallySegmenter


def test_rally_segmenter_basic():
    segmenter = RallySegmenter(fps=30.0, min_rally_duration_sec=1.0, max_shuttle_lost_sec=0.5)

    frames_data = []
    # 0 to 1.0s: idle
    for i in range(30):
        frames_data.append({
            "frame_idx": i,
            "timestamp": i / 30.0,
            "shuttle": {"visible": False, "speed_norm": 0.0},
        })

    # 1.0s to 4.0s: active rally (90 frames)
    for i in range(30, 120):
        frames_data.append({
            "frame_idx": i,
            "timestamp": i / 30.0,
            "shuttle": {"visible": True, "speed_norm": 0.25},
        })

    # 4.0s to 6.0s: idle (60 frames lost)
    for i in range(120, 180):
        frames_data.append({
            "frame_idx": i,
            "timestamp": i / 30.0,
            "shuttle": {"visible": False, "speed_norm": 0.0},
        })

    rallies = segmenter.segment(frames_data)
    assert len(rallies) == 1
    assert rallies[0]["duration_seconds"] >= 2.5
    assert rallies[0]["estimated_shot_count"] >= 2


def test_rally_segmenter_uses_timestamps_for_sampled_frames():
    segmenter = RallySegmenter(fps=60.0, min_rally_duration_sec=2.0)
    frames_data = [
        {
            "frame_idx": i * 15,
            "timestamp": i * 0.25,
            "shuttle": {"visible": True},
        }
        for i in range(17)
    ]

    rallies = segmenter.segment(frames_data)

    assert len(rallies) == 1
    assert rallies[0]["duration_seconds"] == 4.0
