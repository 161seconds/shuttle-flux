"""
End-to-end integration test:
Simulates pipeline execution and verifies full analytics output data contract.
"""

import numpy as np
from pipelines.analyze import run_full_analytics


def test_full_pipeline_analytics_contract():
    frame_records = []
    fps = 30.0

    for i in range(150):  # 5 seconds
        t = i / fps
        p1_x = 0.5 + 0.1 * np.sin(t)
        p1_y = 0.2 + 0.05 * np.cos(t)
        p2_x = 0.5 - 0.1 * np.sin(t)
        p2_y = 0.8 + 0.05 * np.cos(t)

        shuttle_active = 30 <= i <= 120
        shuttle_y = 0.5 + 0.3 * np.sin(t * 3) if shuttle_active else 0.5

        frame_records.append({
            "frame_idx": i,
            "timestamp": t,
            "players": [
                {"player_id": 1, "x_norm": p1_x, "y_norm": p1_y, "confidence": 0.95},
                {"player_id": 2, "x_norm": p2_x, "y_norm": p2_y, "confidence": 0.92},
            ],
            "shuttle": {
                "x_norm": 0.5,
                "y_norm": shuttle_y,
                "visible": shuttle_active,
                "confidence": 0.88,
                "speed_norm": 0.2 if shuttle_active else 0.0,
            },
        })

    result = run_full_analytics(
        frame_records=frame_records,
        fps=fps,
        match_metadata={"match_id": "test-match-01"},
    )

    # Check top-level contract keys
    assert "metadata" in result
    assert "overview" in result
    assert "players" in result
    assert "rallies" in result
    assert "hits" in result
    assert "heatmaps" in result

    # Check players data
    assert "player_1" in result["players"]
    assert "player_2" in result["players"]
    assert result["players"]["player_1"]["distance_meters"] > 0
    assert result["players"]["player_2"]["distance_meters"] > 0

    # Check rallies segmented
    assert len(result["rallies"]) >= 1
