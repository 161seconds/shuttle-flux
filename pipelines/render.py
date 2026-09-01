"""
Video & 2D Radar View Rendering Pipeline:
Draws annotations on video frames and generates the 2D Top-Down Radar View.
"""

from typing import Dict, Any, List, Optional
import cv2
import numpy as np


# Palette colors (BGR)
COLOR_PLAYER_1 = (255, 180, 0)   # Cyan / Light Blue
COLOR_PLAYER_2 = (0, 140, 255)   # Amber / Orange
COLOR_SHUTTLE = (0, 255, 255)    # Yellow
COLOR_COURT_LINE = (200, 200, 200)
COLOR_RADAR_BG = (26, 22, 18)    # Dark background


def render_annotated_frame(
    frame: np.ndarray,
    frame_data: Dict[str, Any],
    trailing_shuttle_pts: Optional[List[List[float]]] = None,
) -> np.ndarray:
    """
    Renders bounding boxes, player IDs, and shuttlecock onto a video frame.
    """
    annotated = frame.copy()

    # 1. Draw Players
    for p in frame_data.get("players", []):
        p_id = p.get("player_id", 1)
        color = COLOR_PLAYER_1 if p_id == 1 else COLOR_PLAYER_2
        bbox = p.get("bbox")

        if bbox and len(bbox) == 4:
            x1, y1, x2, y2 = [int(c) for c in bbox]
            # Draw rounded/corner-focused bounding box
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

            # Draw Label Tag
            label = f"P{p_id} ({p.get('confidence', 0.9):.2f})"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(annotated, (x1, y1 - th - 6), (x1 + tw + 6, y1), color, -1)
            cv2.putText(
                annotated,
                label,
                (x1 + 3, y1 - 4),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 0, 0),
                1,
                cv2.LINE_AA,
            )

            # Draw foot point
            bc = p.get("bottom_center")
            if bc and len(bc) == 2:
                cv2.circle(annotated, (int(bc[0]), int(bc[1])), 4, color, -1)

    # 2. Draw Shuttlecock & Trajectory
    shuttle = frame_data.get("shuttle")
    if shuttle and shuttle.get("visible", False):
        center = shuttle.get("center")
        if center and len(center) == 2:
            cx, cy = int(center[0]), int(center[1])
            cv2.circle(annotated, (cx, cy), 6, COLOR_SHUTTLE, -1)
            cv2.circle(annotated, (cx, cy), 8, (0, 0, 0), 1)

    # Draw trailing trajectory line
    if trailing_shuttle_pts and len(trailing_shuttle_pts) > 1:
        for i in range(1, len(trailing_shuttle_pts)):
            pt1 = (int(trailing_shuttle_pts[i - 1][0]), int(trailing_shuttle_pts[i - 1][1]))
            pt2 = (int(trailing_shuttle_pts[i][0]), int(trailing_shuttle_pts[i][1]))
            alpha = i / len(trailing_shuttle_pts)
            thickness = max(1, int(alpha * 3))
            cv2.line(annotated, pt1, pt2, COLOR_SHUTTLE, thickness, cv2.LINE_AA)

    return annotated


def render_2d_radar_court(
    frame_data: Dict[str, Any],
    width: int = 300,
    height: int = 600,
    padding: int = 25,
) -> np.ndarray:
    """
    Renders standard 2D Top-down Radar Court with player and shuttle positions.
    """
    radar = np.full((height, width, 3), COLOR_RADAR_BG, dtype=np.uint8)

    court_w = width - 2 * padding
    court_h = height - 2 * padding

    x0, y0 = padding, padding
    x1, y1 = padding + court_w, padding + court_h

    # Outer Boundary
    cv2.rectangle(radar, (x0, y0), (x1, y1), COLOR_COURT_LINE, 2)

    # Net (y = 0.5)
    net_y = int(y0 + 0.5 * court_h)
    cv2.line(radar, (x0, net_y), (x1, net_y), (255, 255, 255), 2)

    # Center Lines
    center_x = int(x0 + 0.5 * court_w)
    cv2.line(radar, (center_x, y0), (center_x, int(y0 + 0.35 * court_h)), COLOR_COURT_LINE, 1)
    cv2.line(radar, (center_x, int(y0 + 0.65 * court_h)), (center_x, y1), COLOR_COURT_LINE, 1)

    # Short Service Lines (at ~35% and ~65% from baselines)
    p1_service_y = int(y0 + 0.35 * court_h)
    p2_service_y = int(y0 + 0.65 * court_h)
    cv2.line(radar, (x0, p1_service_y), (x1, p1_service_y), COLOR_COURT_LINE, 1)
    cv2.line(radar, (x0, p2_service_y), (x1, p2_service_y), COLOR_COURT_LINE, 1)

    # Draw Players on Radar (norm_x: 0 to 1, norm_y: 0 to 1)
    for p in frame_data.get("players", []):
        p_id = p.get("player_id", 1)
        nx = p.get("x_norm", 0.5)
        ny = p.get("y_norm", 0.5)

        px = int(x0 + nx * court_w)
        py = int(y0 + ny * court_h)

        color = COLOR_PLAYER_1 if p_id == 1 else COLOR_PLAYER_2
        cv2.circle(radar, (px, py), 8, color, -1)
        cv2.circle(radar, (px, py), 9, (255, 255, 255), 1)
        cv2.putText(
            radar,
            f"P{p_id}",
            (px - 6, py + 4),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.35,
            (0, 0, 0),
            1,
            cv2.LINE_AA,
        )

    # Draw Shuttle on Radar
    shuttle = frame_data.get("shuttle")
    if shuttle and shuttle.get("visible", False):
        sx = int(x0 + shuttle.get("x_norm", 0.5) * court_w)
        sy = int(y0 + shuttle.get("y_norm", 0.5) * court_h)
        cv2.circle(radar, (sx, sy), 5, COLOR_SHUTTLE, -1)

    return radar
