"""
Shuttle Flux FastAPI Backend REST API:
Provides endpoints for video upload, job polling, analytics retrieval, and video streaming.
"""

import os
import sys
import uuid
import math
import numpy as np
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

# Ensure root workspace is in sys.path
WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from apps.api.models import (
    MatchUploadResponse,
    ProcessingStatusResponse,
    MatchAnalyticsResponse,
)
from apps.api.storage import (
    save_uploaded_video,
    get_match_info,
    get_job_status,
    get_analytics_result,
    list_all_matches,
    update_job_status,
    save_analytics_result,
)
from apps.worker.worker import process_video_pipeline

app = FastAPI(
    title="Shuttle Flux API",
    description="Badminton AI Video Analytics REST API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "app": "Shuttle Flux API",
        "version": "1.0.0",
        "status": "online",
        "docs_url": "/docs",
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.post("/api/v1/matches/upload", response_model=MatchUploadResponse)
async def upload_match_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """Uploads a badminton video file and triggers async pipeline worker."""
    if not file.filename.lower().endswith((".mp4", ".mov", ".avi", ".mkv")):
        raise HTTPException(
            status_code=400,
            detail="Unsupported video format. Please upload MP4, MOV, AVI, or MKV.",
        )

    match_id = str(uuid.uuid4())[:8]
    content = await file.read()
    video_path = save_uploaded_video(match_id, file.filename, content)

    # Spawn async processing worker
    background_tasks.add_task(process_video_pipeline, match_id, video_path)

    return MatchUploadResponse(
        match_id=match_id,
        filename=file.filename,
        status="queued",
        created_at=get_match_info(match_id)["created_at"],
    )


@app.get("/api/v1/matches/{match_id}/processing", response_model=ProcessingStatusResponse)
async def get_match_processing_status(match_id: str):
    """Polls processing progress and pipeline stage."""
    status_data = get_job_status(match_id)
    return ProcessingStatusResponse(**status_data)


@app.get("/api/v1/matches/{match_id}/analytics")
async def get_match_analytics(match_id: str):
    """Retrieves full computed match analytics (players, rallies, heatmaps, shots)."""
    analytics = get_analytics_result(match_id)
    if not analytics:
        raise HTTPException(
            status_code=404,
            detail="Analytics not found. Match may still be processing or failed.",
        )
    return analytics


@app.get("/api/v1/matches/{match_id}/rallies")
async def get_match_rallies(match_id: str):
    """Retrieves list of segmented rallies with timestamps."""
    analytics = get_analytics_result(match_id)
    if not analytics:
        raise HTTPException(status_code=404, detail="Rallies data not ready.")
    return analytics.get("rallies", [])


@app.get("/api/v1/matches/{match_id}/video")
async def stream_match_video(match_id: str):
    """Streams the uploaded match video file."""
    info = get_match_info(match_id)
    if not info or not os.path.exists(info["video_path"]):
        raise HTTPException(status_code=404, detail="Video file not found.")
    return FileResponse(info["video_path"], media_type="video/mp4")


@app.get("/api/v1/matches")
async def list_matches():
    """Lists all uploaded matches."""
    return list_all_matches()


@app.post("/api/v1/matches/demo")
async def create_demo_match():
    """Creates an instant synthetic demo match with complete rich analytics."""
    match_id = f"demo-{str(uuid.uuid4())[:4]}"
    mock_analytics = {
        "metadata": {
            "match_id": match_id,
            "fps": 30.0,
            "total_frames": 900,
            "duration_seconds": 30.0,
            "mode": "Singles (BWF Standard)",
        },
        "overview": {
            "total_rallies": 3,
            "total_shots": 16,
            "active_play_duration_sec": 21.4,
            "total_distance_player_1_m": 84.6,
            "total_distance_player_2_m": 92.1,
        },
        "players": {
            "player_1": {
                "player_id": 1,
                "label": "Player 1 (Viktor A.)",
                "side": "Near Court (Bottom)",
                "distance_meters": 84.6,
                "avg_speed_mps": 3.12,
                "max_speed_mps": 6.84,
                "active_time_seconds": 19.8,
                "zone_occupancy": {
                    "P1_rear_left": 28.5,
                    "P1_rear_right": 22.1,
                    "P1_mid_left": 18.2,
                    "P1_mid_right": 15.0,
                    "P1_front_left": 9.2,
                    "P1_front_right": 7.0,
                },
            },
            "player_2": {
                "player_id": 2,
                "label": "Player 2 (Shi Y.)",
                "side": "Far Court (Top)",
                "distance_meters": 92.1,
                "avg_speed_mps": 3.45,
                "max_speed_mps": 7.15,
                "active_time_seconds": 20.4,
                "zone_occupancy": {
                    "P2_rear_left": 24.0,
                    "P2_rear_right": 29.5,
                    "P2_mid_left": 19.5,
                    "P2_mid_right": 14.0,
                    "P2_front_left": 7.0,
                    "P2_front_right": 6.0,
                },
            },
        },
        "rallies": [
            {
                "rally_id": 1,
                "name": "Rally #1 - Opening Exchange",
                "start_frame": 30,
                "end_frame": 240,
                "start_time": 1.0,
                "end_time": 8.0,
                "duration_seconds": 7.0,
                "estimated_shot_count": 5,
                "confidence": 0.94,
            },
            {
                "rally_id": 2,
                "name": "Rally #2 - Fast Net Play & Smash",
                "start_frame": 300,
                "end_frame": 570,
                "start_time": 10.0,
                "end_time": 19.0,
                "duration_seconds": 9.0,
                "estimated_shot_count": 7,
                "confidence": 0.91,
            },
            {
                "rally_id": 3,
                "name": "Rally #3 - Rear Court Battle",
                "start_frame": 630,
                "end_frame": 792,
                "start_time": 21.0,
                "end_time": 26.4,
                "duration_seconds": 5.4,
                "estimated_shot_count": 4,
                "confidence": 0.89,
            },
        ],
        "hits": [
            {"hit_index": 1, "frame_idx": 35, "timestamp": 1.17, "player_id": 1, "hit_position": {"x": 0.52, "y": 0.28}, "shot_type": "serve", "confidence": 0.95},
            {"hit_index": 2, "frame_idx": 75, "timestamp": 2.50, "player_id": 2, "hit_position": {"x": 0.48, "y": 0.72}, "shot_type": "clear", "confidence": 0.88},
            {"hit_index": 3, "frame_idx": 120, "timestamp": 4.00, "player_id": 1, "hit_position": {"x": 0.65, "y": 0.15}, "shot_type": "smash", "confidence": 0.92},
            {"hit_index": 4, "frame_idx": 160, "timestamp": 5.33, "player_id": 2, "hit_position": {"x": 0.35, "y": 0.55}, "shot_type": "net_shot", "confidence": 0.85},
            {"hit_index": 5, "frame_idx": 210, "timestamp": 7.00, "player_id": 1, "hit_position": {"x": 0.40, "y": 0.45}, "shot_type": "drop", "confidence": 0.82},
        ],
        "heatmaps": {
            "player_1": {"max_density": 12.4, "grid_size": [30, 60], "grid": []},
            "player_2": {"max_density": 14.1, "grid_size": [30, 60], "grid": []},
        },
        "frame_records": [],
    }

    # Generate synthetic radar frames for full 30 seconds
    for f in range(0, 900, 3):
        t = f / 30.0
        p1_x = 0.5 + 0.20 * np.sin(t * 1.5)
        p1_y = 0.25 + 0.12 * np.cos(t * 1.2)
        p2_x = 0.5 - 0.22 * np.sin(t * 1.4)
        p2_y = 0.75 + 0.10 * np.cos(t * 1.1)
        shuttle_x = 0.5 + 0.25 * np.cos(t * 2.5)
        shuttle_y = 0.5 + 0.38 * np.sin(t * 2.8)

        mock_analytics["frame_records"].append({
            "frame_idx": f,
            "timestamp": round(t, 2),
            "players": [
                {"player_id": 1, "x_norm": round(p1_x, 3), "y_norm": round(p1_y, 3), "bbox": [450, 600, 550, 800], "confidence": 0.95},
                {"player_id": 2, "x_norm": round(p2_x, 3), "y_norm": round(p2_y, 3), "bbox": [460, 250, 540, 420], "confidence": 0.93},
            ],
            "shuttle": {
                "x_norm": round(shuttle_x, 3),
                "y_norm": round(shuttle_y, 3),
                "visible": True,
                "confidence": 0.90,
            },
        })

    save_analytics_result(match_id, mock_analytics)
    update_job_status(match_id, status="completed", progress=100, stage="completed")

    return {"match_id": match_id, "status": "completed", "analytics": mock_analytics}
