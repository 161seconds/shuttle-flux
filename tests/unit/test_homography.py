"""
Unit tests for Homography calibration and perspective transformation.
"""

import numpy as np
from pipelines.calibrate import CourtCalibrator, compute_homography


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
