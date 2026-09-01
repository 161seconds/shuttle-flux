"""
Pydantic Data Models & API Schemas for Shuttle Flux.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class MatchUploadResponse(BaseModel):
    match_id: str
    filename: str
    status: str = "queued"
    created_at: str


class ProcessingStatusResponse(BaseModel):
    match_id: str
    status: str  # queued, processing, completed, failed
    progress_percentage: int = 0
    current_stage: str = "init"
    error_message: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class PlayerStatItem(BaseModel):
    player_id: int
    label: str
    side: str
    distance_meters: float
    avg_speed_mps: float
    max_speed_mps: float
    active_time_seconds: float
    zone_occupancy: Dict[str, float] = {}


class RallyItem(BaseModel):
    rally_id: int
    name: str
    start_frame: int
    end_frame: int
    start_time: float
    end_time: float
    duration_seconds: float
    estimated_shot_count: int
    confidence: float


class HitItem(BaseModel):
    hit_index: int
    frame_idx: int
    timestamp: float
    player_id: int
    hit_position: Dict[str, float]
    shot_type: str
    confidence: float


class MatchOverview(BaseModel):
    total_rallies: int
    total_shots: int
    active_play_duration_sec: float
    total_distance_player_1_m: float
    total_distance_player_2_m: float


class MatchAnalyticsResponse(BaseModel):
    match_id: str
    metadata: Dict[str, Any]
    overview: MatchOverview
    players: Dict[str, PlayerStatItem]
    rallies: List[RallyItem]
    hits: List[HitItem]
    heatmaps: Dict[str, Any]
