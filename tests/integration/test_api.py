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
