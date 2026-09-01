"""
Integration test for FastAPI Backend REST API endpoints.
"""

from starlette.testclient import TestClient
from apps.api.main import app

client = TestClient(app)


def test_api_root_and_health():
    res = client.get("/")
    assert res.status_code == 200
    assert res.json()["status"] == "online"

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "healthy"


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


def test_api_youtube_endpoint_validation():
    # Test invalid URL
    invalid_res = client.post("/api/v1/matches/youtube", json={"url": "https://invalid-domain.com/video"})
    assert invalid_res.status_code == 400

    # Test valid format URL acceptance
    valid_res = client.post("/api/v1/matches/youtube", json={"url": "https://www.youtube.com/watch?v=sample123"})
    assert valid_res.status_code == 200
    data = valid_res.json()
    assert "match_id" in data
    assert data["status"] == "processing"


def test_api_cancel_endpoint():
    # Trigger demo match first
    res = client.post("/api/v1/matches/demo")
    match_id = res.json()["match_id"]

    # Cancel match
    cancel_res = client.post(f"/api/v1/matches/{match_id}/cancel")
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "cancelled"

    # Status check confirms cancelled
    status_res = client.get(f"/api/v1/matches/{match_id}/processing")
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "cancelled"


