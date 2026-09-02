"""
Integration test for FastAPI Backend REST API endpoints.
"""

from starlette.testclient import TestClient
from apps.api.main import app
from apps.api.storage import update_job_status

client = TestClient(app)


def test_api_root_and_health():
    res = client.get("/")
    assert res.status_code == 200
    assert res.json()["status"] == "online"

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "healthy"


def test_runtime_capabilities_contract():
    response = client.get("/api/v1/runtime")

    assert response.status_code == 200
    payload = response.json()
    assert payload["selected_backend"] in {"pytorch", "onnx", "tensorrt"}
    assert payload["inference_mode"] in {"local", "remote"}
    assert "ultralytics_yolo" in payload["components"]
    assert "deep_eiou" in payload["components"]
    assert "athlete_pose" in payload["components"]
    assert "racket_detection" in payload["components"]
    assert "inference_service" in payload


def test_api_demo_match():
    res = client.post("/api/v1/matches/demo")
    assert res.status_code == 200
    data = res.json()
    assert "match_id" in data
    assert data["status"] == "completed"

    match_id = data["match_id"]

    # Test get analytics
    analytics_res = client.get(f"/api/v1/matches/{match_id}/analytics")
    assert analytics_res.status_code == 200
    analytics = analytics_res.json()
    assert analytics["overview"]["total_rallies"] == 3
    assert "player_1" in analytics["players"]
    assert "player_2" in analytics["players"]

    # Test get processing status
    status_res = client.get(f"/api/v1/matches/{match_id}/processing")
    assert status_res.status_code == 200
    assert status_res.json()["progress_percentage"] == 100

    # Test get rallies
    rallies_res = client.get(f"/api/v1/matches/{match_id}/rallies")
    assert rallies_res.status_code == 200
    assert len(rallies_res.json()) == 3


def test_api_youtube_endpoint_validation(monkeypatch):
    monkeypatch.setattr(
        "apps.api.main.process_youtube_download_and_pipeline",
        lambda *_args, **_kwargs: None,
    )

    # Test invalid URL
    invalid_res = client.post("/api/v1/matches/youtube", json={"url": "https://invalid-domain.com/video"})
    assert invalid_res.status_code == 400

    lookalike_res = client.post(
        "/api/v1/matches/youtube",
        json={"url": "https://youtube.com.attacker.example/watch?v=sample123"},
    )
    assert lookalike_res.status_code == 400

    # Test valid format URL acceptance
    valid_res = client.post("/api/v1/matches/youtube", json={"url": "https://www.youtube.com/watch?v=sample123"})
    assert valid_res.status_code == 200
    data = valid_res.json()
    assert "match_id" in data
    assert data["status"] == "processing"


def test_api_cancel_endpoint():
    match_id = "cancel-test-job"
    update_job_status(match_id, status="processing", progress=25, stage="preprocessing")

    # Cancel match
    cancel_res = client.post(f"/api/v1/matches/{match_id}/cancel")
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "cancelled"

    # Status check confirms cancelled
    status_res = client.get(f"/api/v1/matches/{match_id}/processing")
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "cancelled"

    update_job_status(match_id, status="processing", progress=50, stage="detection_and_tracking")
    status_res = client.get(f"/api/v1/matches/{match_id}/processing")
    assert status_res.json()["status"] == "cancelled"


def test_api_unknown_job_returns_not_found():
    status_res = client.get("/api/v1/matches/does-not-exist/processing")
    assert status_res.status_code == 404


def test_api_cannot_cancel_completed_job():
    res = client.post("/api/v1/matches/demo")
    match_id = res.json()["match_id"]

    cancel_res = client.post(f"/api/v1/matches/{match_id}/cancel")

    assert cancel_res.status_code == 409


def test_update_player_names_updates_frame_labels():
    res = client.post("/api/v1/matches/demo")
    match_id = res.json()["match_id"]

    update_res = client.put(
        f"/api/v1/matches/{match_id}/players",
        json={"player_1_name": "Near Player", "player_2_name": "Far Player"},
    )

    assert update_res.status_code == 200
    analytics = update_res.json()["analytics"]
    assert analytics["players"]["player_1"]["label"] == "Near Player"
    assert analytics["players"]["player_2"]["label"] == "Far Player"
    assert analytics["frame_records"][0]["players"][0]["label"] == "Near Player"
    assert analytics["frame_records"][0]["players"][1]["label"] == "Far Player"
