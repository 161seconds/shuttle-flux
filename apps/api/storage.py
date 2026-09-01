"""
File and Results Storage Manager:
Handles saving video files, caching JSON match analytics, and tracking job states.
"""

import os
import json
from typing import Dict, Any, Optional
from datetime import datetime, timezone


STORAGE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "storage")
MATCHES_DIR = os.path.join(STORAGE_DIR, "matches")
RESULTS_DIR = os.path.join(STORAGE_DIR, "results")

os.makedirs(MATCHES_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)

# In-memory registry for jobs and metadata
_JOB_REGISTRY: Dict[str, Dict[str, Any]] = {}
_MATCH_REGISTRY: Dict[str, Dict[str, Any]] = {}


def save_uploaded_video(match_id: str, filename: str, content: bytes) -> str:
    """Saves uploaded video file to storage."""
    ext = os.path.splitext(filename)[1]
    saved_name = f"{match_id}{ext}"
    target_path = os.path.join(MATCHES_DIR, saved_name)
    with open(target_path, "wb") as f:
        f.write(content)

    _MATCH_REGISTRY[match_id] = {
        "match_id": match_id,
        "filename": filename,
        "video_path": target_path,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "queued",
    }
    return target_path


def register_youtube_match(match_id: str, url: str) -> str:
    """Registers a YouTube match and returns target destination path."""
    target_path = os.path.join(MATCHES_DIR, f"{match_id}.mp4")
    _MATCH_REGISTRY[match_id] = {
        "match_id": match_id,
        "filename": f"YouTube: {url}",
        "video_path": target_path,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "queued",
    }
    return target_path


def get_match_info(match_id: str) -> Optional[Dict[str, Any]]:
    return _MATCH_REGISTRY.get(match_id)


def update_job_status(
    match_id: str,
    status: str,
    progress: int,
    stage: str,
    error: Optional[str] = None,
):
    """Updates job progress in registry."""
    if match_id not in _JOB_REGISTRY:
        _JOB_REGISTRY[match_id] = {
            "match_id": match_id,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }

    _JOB_REGISTRY[match_id].update(
        {
            "status": status,
            "progress_percentage": progress,
            "current_stage": stage,
            "error_message": error,
        }
    )
    if status == "completed":
        _JOB_REGISTRY[match_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
        if match_id in _MATCH_REGISTRY:
            _MATCH_REGISTRY[match_id]["status"] = "completed"


def get_job_status(match_id: str) -> Dict[str, Any]:
    return _JOB_REGISTRY.get(
        match_id,
        {
            "match_id": match_id,
            "status": "queued",
            "progress_percentage": 0,
            "current_stage": "init",
        },
    )


def cancel_job(match_id: str) -> bool:
    """Marks an active job as cancelled."""
    if match_id in _JOB_REGISTRY:
        _JOB_REGISTRY[match_id]["status"] = "cancelled"
        _JOB_REGISTRY[match_id]["cancelled"] = True
        _JOB_REGISTRY[match_id]["error_message"] = "Processing cancelled by user"
        if match_id in _MATCH_REGISTRY:
            _MATCH_REGISTRY[match_id]["status"] = "cancelled"
        return True
    return False


def is_job_cancelled(match_id: str) -> bool:
    """Checks whether a job has been cancelled."""
    job = _JOB_REGISTRY.get(match_id)
    return bool(job and (job.get("status") == "cancelled" or job.get("cancelled", False)))


def save_analytics_result(match_id: str, result_data: Dict[str, Any]):
    """Persists analytics result to disk as JSON."""
    path = os.path.join(RESULTS_DIR, f"{match_id}_analytics.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result_data, f, indent=2)


def get_analytics_result(match_id: str) -> Optional[Dict[str, Any]]:
    """Loads analytics result from disk."""
    path = os.path.join(RESULTS_DIR, f"{match_id}_analytics.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def update_player_names(match_id: str, p1_name: str, p2_name: str) -> Optional[Dict[str, Any]]:
    """Updates player names in saved match analytics JSON."""
    analytics = get_analytics_result(match_id)
    if analytics:
        if "players" in analytics:
            if "player_1" in analytics["players"]:
                analytics["players"]["player_1"]["label"] = p1_name
            if "player_2" in analytics["players"]:
                analytics["players"]["player_2"]["label"] = p2_name
        save_analytics_result(match_id, analytics)
        return analytics
    return None


def list_all_matches() -> list:
    return list(_MATCH_REGISTRY.values())


def cleanup_storage(keep_latest_n: int = 1) -> Dict[str, Any]:
    """Deletes cached video files in storage/matches to free up disk space."""
    freed_bytes = 0
    deleted_files = []
    
    if os.path.exists(MATCHES_DIR):
        files = [
            os.path.join(MATCHES_DIR, f)
            for f in os.listdir(MATCHES_DIR)
            if os.path.isfile(os.path.join(MATCHES_DIR, f))
        ]
        # Sort by modification time (oldest first)
        files.sort(key=lambda p: os.path.getmtime(p))
        
        to_delete = files[:-keep_latest_n] if keep_latest_n > 0 else files
        for file_path in to_delete:
            try:
                size = os.path.getsize(file_path)
                os.remove(file_path)
                freed_bytes += size
                deleted_files.append(os.path.basename(file_path))
            except Exception as e:
                print(f"[Cleanup Warning] Failed to delete {file_path}: {e}")
                
    return {
        "freed_mb": round(freed_bytes / (1024 * 1024), 2),
        "deleted_count": len(deleted_files),
        "deleted_files": deleted_files,
    }
