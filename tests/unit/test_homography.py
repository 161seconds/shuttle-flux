"""
Unit tests for Homography calibration and perspective transformation.
"""

import numpy as np
from pipelines.calibrate import CourtCalibrator, compute_homography, player_floor_point
from pipelines.preprocess import display_target_height


def test_homography_square_to_square():
    # Direct 1:1 mapping from 0-1000 square to normalized 0-1 square
    src = [(0.0, 0.0), (1000.0, 0.0), (0.0, 1000.0), (1000.0, 1000.0)]
    dst = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (1.0, 1.0)]

    calibrator = CourtCalibrator()
    success = calibrator.calibrate_from_points(src, dst)
    assert success is True

    # Center point (500, 500) -> (0.5, 0.5)
    test_pt = np.array([[500.0, 500.0]])
    court_pt = calibrator.transform_image_to_court(test_pt)
    assert np.isclose(court_pt[0, 0], 0.5, atol=1e-3)
    assert np.isclose(court_pt[0, 1], 0.5, atol=1e-3)

    # Invert back (0.5, 0.5) -> (500, 500)
    image_pt = calibrator.transform_court_to_image(court_pt)
    assert np.isclose(image_pt[0, 0], 500.0, atol=1.0)
    assert np.isclose(image_pt[0, 1], 500.0, atol=1.0)


def test_filter_players_keeps_match_court_and_rejects_adjacent_people():
    calibrator = CourtCalibrator()
    assert calibrator.calibrate_standard_corners(
        bottom_left_px=(0.0, 1000.0),
        bottom_right_px=(1000.0, 1000.0),
        top_left_px=(0.0, 0.0),
        top_right_px=(1000.0, 0.0),
    )
    detections = [
        {"bottom_center": [400.0, 200.0], "role": "near", "confidence": 0.9},
        {"bottom_center": [500.0, 250.0], "role": "near", "confidence": 0.8},
        {"bottom_center": [600.0, 300.0], "role": "near", "confidence": 0.7},
        {"bottom_center": [500.0, 750.0], "role": "far", "confidence": 0.6},
        {"bottom_center": [1120.0, 500.0], "role": "near", "confidence": 1.0},
        {"bottom_center": [500.0, 1250.0], "role": "near", "confidence": 1.0},
        {"bottom_center": [500.0, -50.0], "role": "far", "confidence": 1.0},
    ]

    players = calibrator.filter_players(detections)

    assert [player["role"] for player in players] == ["near", "far", "far"]


def test_player_floor_point_prefers_visible_ankles():
    player = {
        "bottom_center": [50.0, 100.0],
        "pose": {
            "keypoints": {
                "left_ankle": [42.0, 94.0, 0.9],
                "right_ankle": [58.0, 98.0, 0.8],
            }
        },
    }

    assert player_floor_point(player) == [50.0, 98.0]


def test_frame_calibration_rejects_broadcast_camera_cut():
    calibrator = CourtCalibrator()
    assert calibrator.calibrate_standard_corners(
        bottom_left_px=(10.0, 90.0),
        bottom_right_px=(90.0, 90.0),
        top_left_px=(10.0, 10.0),
        top_right_px=(90.0, 10.0),
    )
    main_view = np.zeros((100, 100, 3), dtype=np.uint8)
    for x, y in calibrator.calibration_image_points.astype(int):
        main_view[max(0, y - 1) : y + 2, max(0, x - 1) : x + 2] = 255

    assert calibrator.frame_matches_calibration(main_view)
    assert not calibrator.frame_matches_calibration(np.zeros_like(main_view))


def test_display_video_upscale_targets_next_requested_resolution():
    assert display_target_height(360) == 720
    assert display_target_height(720) == 1080
    assert display_target_height(1080) is None
