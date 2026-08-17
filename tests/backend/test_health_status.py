"""
Tests for SystemStatus REST endpoint GET /api/v1/status.
"""

from fastapi.testclient import TestClient
from backend.app import app


def test_health_status_endpoint():
    """Verify GET /api/v1/status returns accurate SystemStatus JSON."""
    client = TestClient(app)
    response = client.get("/api/v1/status")
    assert response.status_code == 200

    data = response.json()
    assert data["mode"] == "LOCAL"
    assert data["decision_engine"] == "ONLINE"
    assert data["safety"] == "ONLINE"
    assert data["controller"] == "ONLINE"
    assert data["vision"] == "OFFLINE"
    assert data["camera"] == "OFFLINE"
    assert data["internet"] == "OFFLINE"
