"""Deep-EIoU association for sports player tracking."""

from itertools import permutations
from typing import Any, Dict, List

import numpy as np


def _expand_box(box: List[float], scale: float) -> np.ndarray:
    x1, y1, x2, y2 = np.asarray(box, dtype=np.float32)
    cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    half_w = max(1.0, (x2 - x1) * scale / 2.0)
    half_h = max(1.0, (y2 - y1) * scale / 2.0)
    return np.array([cx - half_w, cy - half_h, cx + half_w, cy + half_h])


def box_iou(first: List[float], second: List[float]) -> float:
    a = np.asarray(first, dtype=np.float32)
    b = np.asarray(second, dtype=np.float32)
    intersection_w = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    intersection_h = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    intersection = intersection_w * intersection_h
    union = max(1e-6, (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - intersection)
    return float(intersection / union)


def expansion_iou(
    first: List[float], second: List[float], scales: tuple[float, ...] = (1.0, 1.25, 1.5, 2.0)
) -> float:
    return max(box_iou(_expand_box(first, scale), _expand_box(second, scale)) for scale in scales)


def cosine_distance(first: Any, second: Any) -> float:
    if first is None or second is None:
        return 0.5
    a = np.asarray(first, dtype=np.float32).reshape(-1)
    b = np.asarray(second, dtype=np.float32).reshape(-1)
    if a.shape != b.shape or a.size == 0:
        return 0.5
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denominator <= 1e-12:
        return 0.5
    return float(np.clip(1.0 - np.dot(a, b) / denominator, 0.0, 1.0))


def association_cost(track: Dict[str, Any], detection: Dict[str, Any]) -> float:
    eiou_cost = 1.0 - expansion_iou(track["bbox"], detection["bbox"])
    track_center = np.asarray(track["bottom_center"], dtype=np.float32)
    detection_center = np.asarray(detection["bottom_center"], dtype=np.float32)
    diagonal = max(1.0, np.hypot(track["bbox"][2] - track["bbox"][0], track["bbox"][3] - track["bbox"][1]))
    motion_cost = min(1.0, float(np.linalg.norm(track_center - detection_center) / (diagonal * 3.0)))

    has_appearance = track.get("embedding") is not None and detection.get("embedding") is not None
    if has_appearance:
        appearance_cost = cosine_distance(track["embedding"], detection["embedding"])
        # Appearance leads during crossings, while EIoU and motion constrain implausible jumps.
        return 0.30 * eiou_cost + 0.15 * motion_cost + 0.55 * appearance_cost
    return 0.72 * eiou_cost + 0.28 * motion_cost


def match_tracks(
    tracks: List[Dict[str, Any]], detections: List[Dict[str, Any]]
) -> List[int]:
    """Returns the detection index assigned to each track."""
    if len(tracks) != len(detections):
        raise ValueError("Deep-EIoU matching requires equal track and detection counts")
    if not tracks:
        return []

    best_assignment = list(range(len(detections)))
    best_cost = float("inf")
    for assignment in permutations(range(len(detections))):
        cost = sum(
            association_cost(track, detections[detection_index])
            for track, detection_index in zip(tracks, assignment)
        )
        if cost < best_cost:
            best_cost = cost
            best_assignment = list(assignment)
    return best_assignment
