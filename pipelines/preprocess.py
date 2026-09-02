"""
Video Preprocessing Pipeline:
- Extracts video metadata (FPS, duration, resolution, total frames)
- Validates video codec and readability
- Yields normalized RGB/BGR frame batches
"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, Generator, Tuple, Optional

import cv2
import numpy as np

from ml.runtime.capabilities import get_runtime_capabilities


def prepare_analysis_video(video_path: str) -> str:
    """Creates an FFmpeg-normalized analysis copy while preserving the uploaded source."""
    if os.getenv("ENABLE_FFMPEG_NORMALIZATION", "0") != "1":
        return video_path

    ffmpeg_path = get_runtime_capabilities()["components"]["ffmpeg"].get("path")
    if not ffmpeg_path:
        print("[FFmpeg] Normalization requested but no FFmpeg binary is available")
        return video_path

    temp_root = Path(tempfile.gettempdir()) / "shuttle-flux"
    temp_root.mkdir(parents=True, exist_ok=True)
    fd, output_path = tempfile.mkstemp(prefix="analysis-", suffix=".mp4", dir=temp_root)
    os.close(fd)

    command = [
        str(ffmpeg_path),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(Path(video_path).resolve()),
        "-map",
        "0:v:0",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        os.getenv("FFMPEG_PRESET", "veryfast"),
        "-crf",
        os.getenv("FFMPEG_CRF", "20"),
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        output_path,
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        print(f"[FFmpeg] Created normalized analysis copy: {output_path}")
        return output_path
    except Exception as exc:
        Path(output_path).unlink(missing_ok=True)
        print(f"[FFmpeg] Normalization failed, using original video: {exc}")
        return video_path


def cleanup_analysis_video(analysis_path: str, original_path: str) -> None:
    """Removes only a temporary copy created by prepare_analysis_video."""
    analysis = Path(analysis_path).resolve()
    original = Path(original_path).resolve()
    expected_root = (Path(tempfile.gettempdir()) / "shuttle-flux").resolve()
    if analysis != original and expected_root in analysis.parents:
        analysis.unlink(missing_ok=True)


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
