"""Unit tests for analytics calculations"""

import numpy as np
from analytics.movement import compute_player_distance, compute_smoothed_positions
from analytics.court import normalize_court_coordinates, SINGLES_WIDTH_M, COURT_LENGTH_M


def test_normalize_court_coordinates():
    nx, ny = normalize_court_coordinates(SINGLES_WIDTH_M, COURT_LENGTH_M, is_doubles=False)
    assert np.isclose(nx, 1.0)
    assert np.isclose(ny, 1.0)


def test_compute_player_distance():
    positions = np.array([
        [0.0, 0.0],
        [3.0, 4.0],  # distance = 5.0
        [3.0, 0.0],  # distance = 4.0
    ])
    distance = compute_player_distance(positions)
    assert np.isclose(distance, 9.0)
