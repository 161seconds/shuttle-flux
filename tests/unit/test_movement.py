"""
Unit tests for player movement calculations, smoothing, and zone occupancy.
"""

import numpy as np
from analytics.movement import (
    smooth_court_trajectory,
    compute_distance_meters,
    compute_speed_profile,
    compute_zone_occupancy,
)
from analytics.court import get_court_zone, normalize_court_coordinates, SINGLES_WIDTH_M, COURT_LENGTH_M


def test_get_court_zone():
    # Near court (P1) rear left
    assert get_court_zone(0.2, 0.1) == "P1_rear_left"
    # Near court (P1) front right (near net y=0.5)
    assert get_court_zone(0.8, 0.45) == "P1_front_right"
    # Far court (P2) rear right
    assert get_court_zone(0.8, 0.9) == "P2_rear_right"
    # Far court (P2) front left
    assert get_court_zone(0.2, 0.55) == "P2_front_left"


def test_smooth_court_trajectory():
    noisy_traj = [(0.5, 0.5), (0.52, 0.48), (0.49, 0.51), (0.51, 0.49), (0.50, 0.50)]
    smoothed = smooth_court_trajectory(noisy_traj, window_size=3)
    assert len(smoothed) == len(noisy_traj)
    # Output should be valid coordinates within [0, 1]
    assert np.all(smoothed >= 0.0) and np.all(smoothed <= 1.0)


def test_compute_distance_meters():
    # Move from (0, 0) to (1, 0) in normalized singles court (width = 5.18m)
    traj = np.array([[0.0, 0.0], [1.0, 0.0]])
    dist = compute_distance_meters(traj, is_doubles=False)
    assert np.isclose(dist, SINGLES_WIDTH_M)

    # Move from (0, 0) to (0, 1) in normalized court (length = 13.40m)
    traj_y = np.array([[0.0, 0.0], [0.0, 1.0]])
    dist_y = compute_distance_meters(traj_y, is_doubles=False)
    assert np.isclose(dist_y, COURT_LENGTH_M)


def test_compute_speed_profile():
    # Moving 6.7 meters in 1 second (30 frames at 30 fps)
    pts = np.zeros((30, 2))
    pts[:, 1] = np.linspace(0.0, 0.5, 30)  # y moves from 0 to 0.5 (6.70 meters)

    profile = compute_speed_profile(pts, fps=30.0)
    assert profile["total_distance_m"] > 6.0
    assert profile["avg_speed_mps"] > 5.0
