"""
Tests for SignalDecision REST endpoint GET /api/v1/decision.
"""

from fastapi.testclient import TestClient
from backend.app import app, state_store
from models import SignalDecision, Lane, Priority


def test_decision_endpoint_404_when_empty():
    """Verify GET /api/v1/decision returns 404 when no decision exists."""
    state_store.set_decision(None)
    client = TestClient(app)
    response = client.get("/api/v1/decision")
    assert response.status_code == 404
    assert "No signal decision" in response.json()["detail"]


def test_decision_endpoint_200_when_present():
    """Verify GET /api/v1/decision returns latest SignalDecision."""
    client = TestClient(app)
    dec = SignalDecision(
        decision_id="dec-test-01",
        timestamp=200.0,
        selected_lane=Lane.EAST,
        duration=35,
        priority=Priority.HIGH,
        reasons=["High queue demand on east approach"],
    )
    state_store.set_decision(dec)

    response = client.get("/api/v1/decision")
    assert response.status_code == 200
    data = response.json()
    assert data["decision_id"] == "dec-test-01"
    assert data["selected_lane"] == "east"
    assert data["duration"] == 35
    assert data["priority"] == "HIGH"
