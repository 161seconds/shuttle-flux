"""
Shuttle Flux Async Video Processing Worker:
Executes the full Computer Vision & Analytics Pipeline for uploaded badminton match videos.
"""

import os
import sys
import time
import uuid
import numpy as np

# Ensure root workspace is in sys.path
WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from pipelines.preprocess import extract_video_metadata, frame_generator
from pipelines.calibrate import CourtCalibrator
from pipelines.detect import DetectionPipeline
from pipelines.track import TrackingPipeline
from pipelines.analyze import run_full_analytics
from pipelines.render import render_annotated_frame, render_2d_radar_court
from apps.api.storage import (
    update_job_status,
    save_analytics_result,
    save_partial_analytics,
    clear_partial_analytics,
    is_job_cancelled,
)
from ml.ocr.scoreboard_reader import ScoreboardReader
from ml.court_keypoints.detector import CourtKeypointDetector


def process_video_pipeline(match_id: str, video_path: str):
    """
    Executes the 6-step Badminton AI CV Pipeline:
    1. Preprocessing (Metadata & Validation)
    2. Court Calibration (Homography Matrix)
    3. Detection & Tracking (Players + Shuttlecock) + Scoreboard OCR
    4. Coordinate Transformation (Camera -> 2D Court)
    5. Analytics Engine (Movement, Heatmaps, Rallies, Shots)
    6. Persistence & Completion
    """
    try:
        if is_job_cancelled(match_id):
            return

        update_job_status(match_id, status="processing", progress=22, stage="preprocessing")

        # Step 1: Preprocessing
        metadata = extract_video_metadata(video_path)
        fps = metadata.get("fps", 30.0)
        total_frames = metadata.get("total_frames", 300)

        if is_job_cancelled(match_id):
            return

        # Step 2: Dynamic Court Calibration (from actual video frame)
        update_job_status(match_id, status="processing", progress=38, stage="court_calibration")
        calibrator = CourtCalibrator(is_doubles=False)
        court_detector = CourtKeypointDetector()

        # Read multiple sample frames from video for robust court detection (multi-frame averaging)
        sample_frames = []
        for _, _, f_img in frame_generator(video_path, max_frames=15):
            sample_frames.append(f_img)
            if len(sample_frames) >= 5:
                break

        vid_w = float(metadata.get("width", 1280))
        vid_h = float(metadata.get("height", 720))

        # Run court detection on multiple frames for stability (detector averages internally)
        court_kp = None
        if sample_frames:
            for sf in sample_frames:
                court_kp = court_detector.detect_keypoints(sf)
        else:
            dummy = np.zeros((int(vid_h), int(vid_w), 3), dtype=np.uint8)
            court_kp = court_detector.detect_keypoints(dummy)

        calibrator.calibrate_standard_corners(
            bottom_left_px=court_kp["corner_bottom_left"],
            bottom_right_px=court_kp["corner_bottom_right"],
            top_left_px=court_kp["corner_top_left"],
            top_right_px=court_kp["corner_top_right"],
        )
        detected_court_nodes = court_kp.get("normalized_nodes", {})

        if is_job_cancelled(match_id):
            return

        # Step 3: Detection & Tracking + Scoreboard OCR
        update_job_status(match_id, status="processing", progress=50, stage="detection_and_tracking")
        detector = DetectionPipeline()
        tracker = TrackingPipeline()
        scoreboard_reader = ScoreboardReader()

        extracted_names = {"player_1_name": "VĐV 1 (Gần)", "player_2_name": "VĐV 2 (Xa)", "source": "default"}
        ocr_scanned = False
        frame_records = []
        frame_count = 0

        # Adaptive Frame Stride: Target ~15 FPS analysis for lightning fast processing & 60fps interpolation
        step_stride = max(2, int(fps / 15)) if fps > 15 else 1

        for frame_idx, timestamp, frame in frame_generator(video_path, max_frames=None):
            if is_job_cancelled(match_id):
                print(f"[Worker] Match {match_id} cancelled by user. Terminating worker.")
                return

            if frame_idx % step_stride != 0:
                continue

            # Run detection
            raw_dets = detector.run_frame(frame)

            # Run tracking
            tracked = tracker.update(raw_dets, frame_idx, timestamp)

            # Scoreboard & Jersey OCR scan (scans frames 6, 25, 60 until both names found)
            if (not ocr_scanned or len(extracted_names.get("extracted_list", [])) < 2) and frame_count in [6, 25, 60]:
                try:
                    near_box = tracked.get("players", [{}])[0].get("bbox") if tracked.get("players") else None
                    ocr_res = scoreboard_reader.extract_player_names_from_frame(frame, near_player_bbox=near_box)
                    if ocr_res.get("source") != "default":
                        extracted_names = ocr_res
                        ocr_scanned = True
                        print(f"[Worker OCR] Extracted player names on frame {frame_idx}: {extracted_names}")
                except Exception as ocr_err:
                    print(f"[Worker OCR Warning] {ocr_err}")

            # Step 4: Transform to 2D court coordinates
            h, w, _ = frame.shape
            transformed_players = []
            for p in tracked.get("players", []):
                bc = p.get("bottom_center", [w / 2.0, h / 2.0])
                pt_arr = np.array([[bc[0], bc[1]]], dtype=np.float32)
                court_pt = calibrator.transform_image_to_court(pt_arr)
                p_copy = dict(p)
                p_copy["x_norm"] = round(float(court_pt[0, 0]), 4)
                p_copy["y_norm"] = round(float(court_pt[0, 1]), 4)

                # Assign OCR extracted name or team label
                p_id = p_copy.get("player_id", 1)
                if p_id == 1:
                    p_copy["label"] = extracted_names.get("player_1_name", "VĐV 1 (Gần - Đội 1)")
                elif p_id == 2:
                    p_copy["label"] = extracted_names.get("player_2_name", "VĐV 2 (Xa - Đội 2)")
                elif p_id == 3:
                    p_copy["label"] = extracted_names.get("player_3_name", "VĐV 3 (Gần - Đội 1)")
                elif p_id == 4:
                    p_copy["label"] = extracted_names.get("player_4_name", "VĐV 4 (Xa - Đội 2)")

                # Normalized bounding box coordinates for exact video overlay
                bbox = p.get("bbox", [0, 0, 0, 0])
                if w > 0 and h > 0 and len(bbox) == 4:
                    p_copy["bbox_norm"] = [
                        round(float(bbox[0] / w), 4),
                        round(float(bbox[1] / h), 4),
                        round(float(bbox[2] / w), 4),
                        round(float(bbox[3] / h), 4),
                    ]
                transformed_players.append(p_copy)

            # Shuttle coordinates (Real detection only - NO fake floating yellow dot)
            shuttle = tracked.get("shuttle", {})
            if shuttle and shuttle.get("visible", False) and "center" in shuttle and w > 0 and h > 0:
                cx, cy = shuttle["center"]
                shuttle_pt_arr = np.array([[cx, cy]], dtype=np.float32)
                court_shuttle_pt = calibrator.transform_image_to_court(shuttle_pt_arr)
                shuttle_record = {
                    "frame_idx": frame_idx,
                    "timestamp": round(timestamp, 3),
                    "x_norm": round(float(court_shuttle_pt[0, 0]), 4),
                    "y_norm": round(float(court_shuttle_pt[0, 1]), 4),
                    "center_norm": [round(float(cx / w), 4), round(float(cy / h), 4)],
                    "visible": True,
                    "confidence": shuttle.get("confidence", 0.85),
                    "speed_norm": round(
                        float(
                            np.hypot(
                                tracker.shuttle_tracker.velocity[0] / w,
                                tracker.shuttle_tracker.velocity[1] / h,
                            )
                            * (fps / step_stride)
                        ),
                        5,
                    ),
                }
            else:
                shuttle_record = {
                    "frame_idx": frame_idx,
                    "timestamp": round(timestamp, 3),
                    "visible": False,
                }

            frame_records.append(
                {
                    "frame_idx": frame_idx,
                    "timestamp": round(timestamp, 3),
                    "players": transformed_players,
                    "shuttle": shuttle_record,
                }
            )

            frame_count += 1
            if frame_count % 8 == 0:
                current_pct = min(84, int(50 + (frame_idx / max(total_frames, 1)) * 34))
                update_job_status(match_id, status="processing", progress=current_pct, stage="detection_and_tracking")
                # Save partial analytics for instant live streaming
                save_partial_analytics(
                    match_id,
                    {
                        "metadata": {
                            **metadata,
                            "match_id": match_id,
                            "fps": round(fps, 2),
                            "total_frames": total_frames,
                            "duration_seconds": round(timestamp, 2),
                            "mode": "Đơn (Singles 1v1)",
                        },
                        "court_nodes": detected_court_nodes,
                        "frame_records": list(frame_records),
                        "overview": {
                            "total_rallies": 0,
                            "total_shots": 0,
                            "active_play_duration_sec": 0.0,
                            "total_distance_player_1_m": 0.0,
                            "total_distance_player_2_m": 0.0,
                        },
                        "players": {
                            "player_1": {
                                "player_id": 1,
                                "label": extracted_names.get("player_1_name", "VĐV 1 (Gần)"),
                                "side": "Sân Gần",
                                "distance_meters": 0.0,
                                "avg_speed_mps": 0.0,
                                "max_speed_mps": 0.0,
                                "active_time_seconds": 0.0,
                                "court_control_pct": 50.0,
                                "zone_occupancy": {},
                            },
                            "player_2": {
                                "player_id": 2,
                                "label": extracted_names.get("player_2_name", "VĐV 2 (Xa)"),
                                "side": "Sân Xa",
                                "distance_meters": 0.0,
                                "avg_speed_mps": 0.0,
                                "max_speed_mps": 0.0,
                                "active_time_seconds": 0.0,
                                "court_control_pct": 50.0,
                                "zone_occupancy": {},
                            },
                        },
                        "rallies": [],
                        "hits": [],
                        "heatmaps": {},
                    },
                )

        # Auto-detect match format (Singles 1v1 vs Doubles 2v2)
        is_doubles = tracker.player_tracker.is_doubles_mode or any(
            len(rec.get("players", [])) >= 3 for rec in frame_records
        )

        # Propagate final OCR extracted names to all frames
        for rec in frame_records:
            for p in rec.get("players", []):
                p_id = p.get("player_id", 1)
                if p_id == 1:
                    p["label"] = extracted_names.get("player_1_name", "VĐV 1 (Gần - Đội 1)")
                elif p_id == 2:
                    p["label"] = extracted_names.get("player_2_name", "VĐV 2 (Xa - Đội 2)")
                elif p_id == 3:
                    p["label"] = extracted_names.get("player_3_name", "VĐV 3 (Gần - Đội 1)")
                elif p_id == 4:
                    p["label"] = extracted_names.get("player_4_name", "VĐV 4 (Xa - Đội 2)")

        # Global Trajectory Anti-Jitter Smoothing for Shuttlecock
        visible_shuttle_frames = [
            (i, rec["shuttle"])
            for i, rec in enumerate(frame_records)
            if rec.get("shuttle", {}).get("visible", False) and "x_norm" in rec.get("shuttle", {})
        ]
        if len(visible_shuttle_frames) >= 3:
            for k in range(1, len(visible_shuttle_frames) - 1):
                idx_prev, s_prev = visible_shuttle_frames[k - 1]
                idx_curr, s_curr = visible_shuttle_frames[k]
                idx_next, s_next = visible_shuttle_frames[k + 1]

                # Only smooth if frames are consecutive (within 3 frames)
                if (idx_curr - idx_prev <= 3) and (idx_next - idx_curr <= 3):
                    s_curr["x_norm"] = round(0.22 * s_prev["x_norm"] + 0.56 * s_curr["x_norm"] + 0.22 * s_next["x_norm"], 4)
                    s_curr["y_norm"] = round(0.22 * s_prev["y_norm"] + 0.56 * s_curr["y_norm"] + 0.22 * s_next["y_norm"], 4)
                    if "center_norm" in s_curr and "center_norm" in s_prev and "center_norm" in s_next:
                        s_curr["center_norm"] = [
                            round(0.22 * s_prev["center_norm"][0] + 0.56 * s_curr["center_norm"][0] + 0.22 * s_next["center_norm"][0], 4),
                            round(0.22 * s_prev["center_norm"][1] + 0.56 * s_curr["center_norm"][1] + 0.22 * s_next["center_norm"][1], 4),
                        ]

        # Step 5: Analytics Calculation
        update_job_status(match_id, status="processing", progress=85, stage="analytics")
        analytics_result = run_full_analytics(
            frame_records=frame_records,
            fps=fps,
            match_metadata={"match_id": match_id, "video_metadata": metadata},
            is_doubles=is_doubles,
            player_names=extracted_names,
        )

        analytics_result["metadata"]["is_doubles"] = is_doubles
        analytics_result["metadata"]["mode"] = "Đôi (Doubles 2v2)" if is_doubles else "Đơn (Singles 1v1)"

        update_job_status(match_id, status="processing", progress=95, stage="completed")

        # Attach frame records, scoreboard info, and dynamic court nodes
        analytics_result["frame_records"] = frame_records
        analytics_result["scoreboard"] = extracted_names
        analytics_result["court_nodes"] = detected_court_nodes

        # Step 6: Persist Results
        save_analytics_result(match_id, analytics_result)
        update_job_status(match_id, status="completed", progress=100, stage="completed")
        print(f"[Worker] Successfully completed processing match {match_id}")

    except Exception as e:
        import traceback
        err_msg = f"{str(e)}: {traceback.format_exc()}"
        print(f"[Worker Error] {err_msg}")
        update_job_status(match_id, status="failed", progress=0, stage="error", error=str(e))
    finally:
        clear_partial_analytics(match_id)
