"""BWF badminton court geometry normalized to the doubles outer boundary."""

from typing import Dict, Tuple

from analytics.court import (
    COURT_LENGTH_M,
    DOUBLES_ALLEY_WIDTH_M,
    DOUBLES_LONG_SERVICE_OFFSET_M,
    DOUBLES_WIDTH_M,
    NET_Y_M,
    SHORT_SERVICE_OFFSET_M,
)


Point = Tuple[float, float]
LineSegment = Tuple[Point, Point]

SINGLES_LEFT_X = DOUBLES_ALLEY_WIDTH_M / DOUBLES_WIDTH_M
SINGLES_RIGHT_X = 1.0 - SINGLES_LEFT_X
DOUBLES_LONG_FAR_Y = DOUBLES_LONG_SERVICE_OFFSET_M / COURT_LENGTH_M
DOUBLES_LONG_NEAR_Y = 1.0 - DOUBLES_LONG_FAR_Y
SHORT_SERVICE_FAR_Y = (NET_Y_M - SHORT_SERVICE_OFFSET_M) / COURT_LENGTH_M
SHORT_SERVICE_NEAR_Y = (NET_Y_M + SHORT_SERVICE_OFFSET_M) / COURT_LENGTH_M
NET_Y = NET_Y_M / COURT_LENGTH_M


COURT_LINES: Dict[str, LineSegment] = {
    "outer_left": ((0.0, 0.0), (0.0, 1.0)),
    "singles_left": ((SINGLES_LEFT_X, 0.0), (SINGLES_LEFT_X, 1.0)),
    "center_far": ((0.5, 0.0), (0.5, SHORT_SERVICE_FAR_Y)),
    "center_near": ((0.5, SHORT_SERVICE_NEAR_Y), (0.5, 1.0)),
    "singles_right": ((SINGLES_RIGHT_X, 0.0), (SINGLES_RIGHT_X, 1.0)),
    "outer_right": ((1.0, 0.0), (1.0, 1.0)),
    "far_baseline": ((0.0, 0.0), (1.0, 0.0)),
    "far_doubles_service": ((0.0, DOUBLES_LONG_FAR_Y), (1.0, DOUBLES_LONG_FAR_Y)),
    "far_short_service": ((0.0, SHORT_SERVICE_FAR_Y), (1.0, SHORT_SERVICE_FAR_Y)),
    "near_short_service": ((0.0, SHORT_SERVICE_NEAR_Y), (1.0, SHORT_SERVICE_NEAR_Y)),
    "near_doubles_service": ((0.0, DOUBLES_LONG_NEAR_Y), (1.0, DOUBLES_LONG_NEAR_Y)),
    "near_baseline": ((0.0, 1.0), (1.0, 1.0)),
}

VERTICAL_LINE_POSITIONS = {
    "outer_left": (0.0, ((0.0, 1.0),)),
    "singles_left": (SINGLES_LEFT_X, ((0.0, 1.0),)),
    "center": (0.5, ((0.0, SHORT_SERVICE_FAR_Y), (SHORT_SERVICE_NEAR_Y, 1.0))),
    "singles_right": (SINGLES_RIGHT_X, ((0.0, 1.0),)),
    "outer_right": (1.0, ((0.0, 1.0),)),
}

HORIZONTAL_LINE_POSITIONS = {
    "far_baseline": 0.0,
    "far_doubles_service": DOUBLES_LONG_FAR_Y,
    "far_short_service": SHORT_SERVICE_FAR_Y,
    "near_short_service": SHORT_SERVICE_NEAR_Y,
    "near_doubles_service": DOUBLES_LONG_NEAR_Y,
    "near_baseline": 1.0,
}
