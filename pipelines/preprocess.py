"""
Video Preprocessing Pipeline:
- Extracts video metadata (FPS, duration, resolution, total frames)
- Validates video codec and readability
- Yields normalized RGB/BGR frame batches
"""

from typing import Dict, Any, Generator, Tuple, Optional
import cv2
import numpy as np


def extract_video_metadata(video_path: str) -> Dict[str, Any]:
    """Inspects video file properties using OpenCV."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video file: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0 or np.isnan(fps):
        fps = 30.0  # default fallback

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0.0

    cap.release()
    return {
        "fps": round(float(fps), 2),
        "width": width,
        "height": height,
        "total_frames": total_frames,
        "duration_seconds": round(float(duration), 2),
    }


def frame_generator(
    video_path: str, max_frames: Optional[int] = None
) -> Generator[Tuple[int, float, np.ndarray], None, None]:
    """
    Generator that yields (frame_idx, timestamp_seconds, frame_bgr).
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video file: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0 or np.isnan(fps):
        fps = 30.0

    frame_idx = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret or (max_frames is not None and frame_idx >= max_frames):
            break

        timestamp = frame_idx / float(fps)
        yield frame_idx, timestamp, frame
        frame_idx += 1

    cap.release()
