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

from pipelines.preprocess import (
    cleanup_analysis_video,
    extract_video_metadata,
    frame_generator,
    prepare_analysis_video,
    prepare_display_video,
)
from pipelines.calibrate import CourtCalibrator, player_floor_point
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
    analysis_video_path = video_path
    try:
        if is_job_cancelled(match_id):
            return

        update_job_status(match_id, status="processing", progress=22, stage="preprocessing")

        # Step 1: Preprocessing
        display_video_path = prepare_display_video(video_path)
        analysis_video_path = prepare_analysis_video(video_path)
        metadata = extract_video_metadata(analysis_video_path)
        display_metadata = extract_video_metadata(display_video_path)
        metadata["display_width"] = display_metadata["width"]
        metadata["display_height"] = display_metadata["height"]
        fps = metadata.get("fps", 30.0)
        total_frames = metadata.get("total_frames", 300)

        if is_job_cancelled(match_id):
            return

        # Step 2: Dynamic Court Calibration (from actual video frame)
        update_job_status(match_id, status="processing", progress=38, stage="court_calibration")
        calibrator = CourtCalibrator(is_doubles=False)
        court_detector = CourtKeypointDetector()

        # Sample across the opening seconds so intros, occlusions, and motion blur
        # cannot force calibration from a single weak frame.
        sample_frames = []
        calibration_window = min(
            int(total_frames), max(60, int(float(fps) * 12.0))
        )
        calibration_stride = max(1, calibration_window // 8)
        for sample_idx, _, f_img in frame_generator(
            analysis_video_path, max_frames=calibration_window
        ):
            if sample_idx % calibration_stride != 0:
                continue
            sample_frames.append(f_img)
            if len(sample_frames) >= 8:
                break

        # The detector retains only the strongest BWF-template fit.
        court_kp = None
        if sample_frames:
            for sf in sample_frames:
                court_kp = court_detector.detect_keypoints(sf)

        if court_kp is None:
            raise RuntimeError("Khong doc duoc frame de can chinh san")

        court_calibration = court_kp.get("calibration", {})
        min_court_confidence = float(os.getenv("COURT_MIN_CONFIDENCE", "0.65"))
        min_court_lines = int(os.getenv("COURT_MIN_DETECTED_LINES", "8"))
        max_court_error = float(os.getenv("COURT_MAX_REPROJECTION_ERROR", "0.035"))
        allow_court_fallback = os.getenv("ALLOW_COURT_FALLBACK", "0") == "1"
        reprojection_error = court_calibration.get("reprojection_error_norm")
        has_reliable_court = (
            not court_calibration.get("used_fallback", True)
            and float(court_calibration.get("confidence", 0.0)) >= min_court_confidence
            and int(court_calibration.get("detected_line_count", 0)) >= min_court_lines
            and reprojection_error is not None
            and float(reprojection_error) <= max_court_error
            and len(court_calibration.get("image_points", [])) >= 6
        )

        if has_reliable_court:
            calibrated = calibrator.calibrate_from_points(
                court_calibration["image_points"],
                court_calibration["court_points_norm"],
            )
        elif allow_court_fallback:
            calibrated = calibrator.calibrate_standard_corners(
                bottom_left_px=court_kp["corner_bottom_left"],
                bottom_right_px=court_kp["corner_bottom_right"],
                top_left_px=court_kp["corner_top_left"],
                top_right_px=court_kp["corner_top_right"],
            )
            court_calibration = {
                **court_calibration,
                "source": "explicit-legacy-fallback",
                "used_fallback": True,
            }
        else:
            raise RuntimeError(
                "Khong nhan dien du tin cay cac vach san cau long; "
                "dung phan tich de tranh tao ban do 2D sai"
            )

        if not calibrated:
            raise RuntimeError("Khong the tinh homography tu cac giao diem vach san")

        detected_court_nodes = court_kp.get("normalized_nodes", {})
        detected_court_lines = court_kp.get("line_segments", {})
        detected_net = court_kp.get("net_detection")

        if is_job_cancelled(match_id):
            return

        # Step 3: Detection & Tracking + Scoreboard OCR
        update_job_status(match_id, status="processing", progress=50, stage="detection_and_tracking")
        detector = DetectionPipeline()
        tracker = TrackingPipeline()
        scoreboard_reader = ScoreboardReader()

        extracted_names = {
            "player_1_name": "VĐV 1 (Gần)",
            "player_2_name": "VĐV 2 (Xa)",
            "player_1_country": None,
            "player_2_country": None,
            "score_player_1": None,
            "score_player_2": None,
            "serving_player_id": None,
            "confidence": 0.0,
            "source": "unresolved",
            "extracted_list": [],
        }
        ocr_scan_times = [0.0, 5.0, 12.0]
        ocr_scan_index = 0
        frame_records = []
        frame_count = 0

        # Preserve every source frame up to the configured analysis rate.
        target_fps = max(1.0, float(os.getenv("ANALYSIS_TARGET_FPS", "30")))
        step_stride = max(1, int(round(fps / min(fps, target_fps))))

        for frame_idx, timestamp, frame in frame_generator(analysis_video_path, max_frames=None):
            if is_job_cancelled(match_id):
                print(f"[Worker] Match {match_id} cancelled by user. Terminating worker.")
                return

            if frame_idx % step_stride != 0:
                continue

            if calibrator.frame_matches_calibration(frame):
                raw_dets = detector.run_frame(frame, player_filter=calibrator.filter_players)
                tracked = tracker.update(raw_dets, frame_idx, timestamp, frame=frame)
            else:
                # Age existing tracks, but never draw them over close-ups or alternate cameras.
                tracker.update(
                    {"players": [], "rackets": [], "shuttle": None},
                    frame_idx,
                    timestamp,
                    frame=frame,
                )
                if detector.shuttle_detector is not None:
                    detector.shuttle_detector.reset_temporal_state(frame)
                tracked = {
                    "players": [],
                    "rackets": [],
                    "shuttle": {"visible": False, "observed": False},
                }

            if (
                scoreboard_reader.available
                and ocr_scan_index < len(ocr_scan_times)
                and timestamp >= ocr_scan_times[ocr_scan_index]
            ):
                try:
                    players_for_ocr = tracked.get("players", [])
                    near_player = max(
                        players_for_ocr,
                        key=lambda player: player.get("bottom_center", [0, 0])[1],
                        default=None,
                    )
                    near_box = near_player.get("bbox") if near_player else None
                    ocr_res = scoreboard_reader.extract_player_names_from_frame(frame, near_player_bbox=near_box)
                    changed = False
                    for key in ("player_1_name", "player_2_name"):
                        value = ocr_res.get(key)
                        if value and (
                            extracted_names[key].startswith("VĐV")
                            or float(ocr_res.get("confidence", 0.0))
                            >= float(extracted_names.get("confidence", 0.0))
                        ):
                            extracted_names[key] = value
                            changed = True
                    for key in (
                        "player_1_country",
                        "player_2_country",
                        "score_player_1",
                        "score_player_2",
                        "serving_player_id",
                    ):
                        if ocr_res.get(key) is not None:
                            extracted_names[key] = ocr_res[key]
                    extracted_names["confidence"] = max(
                        float(extracted_names.get("confidence", 0.0)),
                        float(ocr_res.get("confidence", 0.0)),
                    )
                    extracted_names["extracted_list"] = list(
                        dict.fromkeys(
                            extracted_names.get("extracted_list", [])
                            + ocr_res.get("extracted_list", [])
                        )
                    )
                    if changed:
                        extracted_names["source"] = ocr_res.get(
                            "source", "scoreboard_ocr"
                        )
                        print(f"[Worker OCR] Extracted player names on frame {frame_idx}: {extracted_names}")
                except Exception as ocr_err:
                    print(f"[Worker OCR Warning] {ocr_err}")
                finally:
                    ocr_scan_index += 1

            # Step 4: Transform to 2D court coordinates
            h, w, _ = frame.shape
            transformed_players = []
            for p in tracked.get("players", []):
                bc = player_floor_point(p)
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
                pose = p.get("pose")
                if pose and w > 0 and h > 0:
                    p_copy["pose"] = {
                        "source": pose.get("source"),
                        "angles": pose.get("angles", {}),
                        "keypoints": {
                            name: [
                                round(float(values[0] / w), 4),
                                round(float(values[1] / h), 4),
                                round(float(values[2]), 3),
                            ]
                            for name, values in pose.get("keypoints", {}).items()
                        },
                    }
                transformed_players.append(p_copy)

            transformed_rackets = []
            for racket in tracked.get("rackets", []):
                racket_copy = dict(racket)
                bbox = racket.get("bbox", [0, 0, 0, 0])
                center = racket.get("center", [0, 0])
                if w > 0 and h > 0 and len(bbox) == 4:
                    racket_copy["bbox_norm"] = [
                        round(float(bbox[0] / w), 4),
                        round(float(bbox[1] / h), 4),
                        round(float(bbox[2] / w), 4),
                        round(float(bbox[3] / h), 4),
                    ]
                    racket_copy["center_norm"] = [
                        round(float(center[0] / w), 4),
                        round(float(center[1] / h), 4),
                    ]
                if racket.get("keypoints") and w > 0 and h > 0:
                    racket_copy["keypoints_norm"] = {
                        name: [
                            round(float(values[0] / w), 4),
                            round(float(values[1] / h), 4),
                            round(float(values[2]), 3),
                        ]
                        for name, values in racket["keypoints"].items()
                    }
                transformed_rackets.append(racket_copy)

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
                    "observed": shuttle.get("observed", False),
                    "confidence": shuttle.get("confidence", 0.85),
                    # Monocular homography only maps the floor plane; airborne
                    # shuttle depth/height needs a second calibrated camera.
                    "projection_valid": False,
                    "projection_mode": "image-only",
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
                    "observed": False,
                }

            frame_records.append(
                {
                    "frame_idx": frame_idx,
                    "timestamp": round(timestamp, 3),
                    "players": transformed_players,
                    "rackets": transformed_rackets,
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
                        "court_lines": detected_court_lines,
                        "net_detection": detected_net,
                        "court_calibration": court_calibration,
                        "scoreboard": dict(extracted_names),
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
        analytics_result["court_lines"] = detected_court_lines
        analytics_result["net_detection"] = detected_net
        analytics_result["court_calibration"] = court_calibration

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
        cleanup_analysis_video(analysis_video_path, video_path)
