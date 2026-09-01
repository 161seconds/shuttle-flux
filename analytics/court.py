"""
Badminton Court Dimensions (BWF Standard) and Coordinate Systems.

Standard Dimensions:
- Singles Court: 5.18 m (width) x 13.40 m (length)
- Doubles Court: 6.10 m (width) x 13.40 m (length)
- Net Line: y = 6.70 m (halfway)
- Short Service Line: 1.98 m from net (y = 4.72 m and y = 8.68 m)
- Doubles Long Service Line: 0.76 m inside back boundary (y = 0.76 m and y = 12.64 m)
- Singles Long Service Line: Back boundary line (y = 0.0 m and y = 13.40 m)
- Side tramlines (doubles alley): 0.46 m wide on each side
"""

from typing import Dict, List, Tuple
import numpy as np

# BWF Standard Metric Dimensions (in meters)
SINGLES_WIDTH_M = 5.18
DOUBLES_WIDTH_M = 6.10
COURT_LENGTH_M = 13.40
NET_Y_M = 6.70
SHORT_SERVICE_OFFSET_M = 1.98
DOUBLES_LONG_SERVICE_OFFSET_M = 0.76
DOUBLES_ALLEY_WIDTH_M = 0.46

# Y coordinates of key lines
FRONT_SERVICE_LINE_P1 = NET_Y_M - SHORT_SERVICE_OFFSET_M  # 4.72 m
FRONT_SERVICE_LINE_P2 = NET_Y_M + SHORT_SERVICE_OFFSET_M  # 8.68 m
DOUBLES_REAR_SERVICE_LINE_P1 = DOUBLES_LONG_SERVICE_OFFSET_M  # 0.76 m
DOUBLES_REAR_SERVICE_LINE_P2 = COURT_LENGTH_M - DOUBLES_LONG_SERVICE_OFFSET_M  # 12.64 m


def get_standard_court_keypoints(is_doubles: bool = False) -> Dict[str, Tuple[float, float]]:
    """
    Returns standard metric 2D court coordinates (x, y in meters) for key court landmarks.
    Origin (0,0) is at the bottom-left corner of Player 1's side.
    """
    width = DOUBLES_WIDTH_M if is_doubles else SINGLES_WIDTH_M
    half_width = width / 2.0

    return {
        # 4 Outer Corners
        "corner_bottom_left": (0.0, 0.0),
        "corner_bottom_right": (width, 0.0),
        "corner_top_left": (0.0, COURT_LENGTH_M),
        "corner_top_right": (width, COURT_LENGTH_M),
        # Net landmarks
        "net_left": (0.0, NET_Y_M),
        "net_center": (half_width, NET_Y_M),
        "net_right": (width, NET_Y_M),
        # Player 1 Short Service Line
        "p1_short_service_left": (0.0, FRONT_SERVICE_LINE_P1),
        "p1_short_service_center": (half_width, FRONT_SERVICE_LINE_P1),
        "p1_short_service_right": (width, FRONT_SERVICE_LINE_P1),
        # Player 2 Short Service Line
        "p2_short_service_left": (0.0, FRONT_SERVICE_LINE_P2),
        "p2_short_service_center": (half_width, FRONT_SERVICE_LINE_P2),
        "p2_short_service_right": (width, FRONT_SERVICE_LINE_P2),
        # Center Line ends
        "p1_baseline_center": (half_width, 0.0),
        "p2_baseline_center": (half_width, COURT_LENGTH_M),
    }


def normalize_court_coordinates(
    x_m: float, y_m: float, is_doubles: bool = False
) -> Tuple[float, float]:
    """Converts metric court coordinates (meters) to normalized [0, 1] range."""
    width = DOUBLES_WIDTH_M if is_doubles else SINGLES_WIDTH_M
    norm_x = np.clip(x_m / width, 0.0, 1.0)
    norm_y = np.clip(y_m / COURT_LENGTH_M, 0.0, 1.0)
    return float(norm_x), float(norm_y)


def denormalize_court_coordinates(
    norm_x: float, norm_y: float, is_doubles: bool = False
) -> Tuple[float, float]:
    """Converts normalized [0, 1] coordinates back to metric meters."""
    width = DOUBLES_WIDTH_M if is_doubles else SINGLES_WIDTH_M
    return float(norm_x * width), float(norm_y * COURT_LENGTH_M)


def get_court_zone(norm_x: float, norm_y: float) -> str:
    """
    Categorizes a normalized (x, y) coordinate into one of 12 tactical zones:
    - Side: P1 (Bottom: y < 0.5) vs P2 (Top: y >= 0.5)
    - Depth: Front (near net), Mid, Rear (near baseline)
    - Lateral: Left (x < 0.5) vs Right (x >= 0.5)
    """
    # Determine side
    side = "P1" if norm_y < 0.5 else "P2"

    # Normalize depth within the half-court (0 to 1 where 0 is baseline, 1 is net)
    if side == "P1":
        half_y = norm_y * 2.0  # 0 (baseline) to 1 (net)
        if half_y > 0.70:
            depth = "front"
        elif half_y > 0.35:
            depth = "mid"
        else:
            depth = "rear"
    else:
        half_y = (1.0 - norm_y) * 2.0  # 0 (baseline) to 1 (net)
        if half_y > 0.70:
            depth = "front"
        elif half_y > 0.35:
            depth = "mid"
        else:
            depth = "rear"

    lateral = "left" if norm_x < 0.5 else "right"
    return f"{side}_{depth}_{lateral}"
