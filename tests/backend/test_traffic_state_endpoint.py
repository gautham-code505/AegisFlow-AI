"""
Tests for TrafficState REST endpoint GET /api/v1/traffic-state.
"""

from fastapi.testclient import TestClient
from backend.app import app, state_store
from models import TrafficState, LaneState, Lane


def test_traffic_state_endpoint_404_when_empty():
    """Verify GET /api/v1/traffic-state returns 404 when no state exists."""
    state_store.set_traffic_state(None)
    client = TestClient(app)
    response = client.get("/api/v1/traffic-state")
    assert response.status_code == 404
    assert "No traffic state" in response.json()["detail"]


def test_traffic_state_endpoint_200_when_present():
    """Verify GET /api/v1/traffic-state returns latest TrafficState."""
    client = TestClient(app)
    ts = TrafficState(
        timestamp=100.0,
        source="test-cam",
        lanes={
            Lane.NORTH: LaneState(vehicle_count=10, occupancy=0.5),
            Lane.SOUTH: LaneState(vehicle_count=2, occupancy=0.1),
            Lane.EAST: LaneState(vehicle_count=0, occupancy=0.0),
            Lane.WEST: LaneState(vehicle_count=1, occupancy=0.05),
        },
    )
    state_store.set_traffic_state(ts)

    response = client.get("/api/v1/traffic-state")
    assert response.status_code == 200
    data = response.json()
    assert data["timestamp"] == 100.0
    assert data["lanes"]["north"]["vehicle_count"] == 10
