import pytest
from fastapi.testclient import TestClient
from backend.app import app, _approach_lane_states
from backend.state_store import StateStore
import time

client = TestClient(app)

def test_reset_approach_state():
    # First set some dummy data via demo endpoint or directly
    response = client.post("/api/v1/traffic/reset/north")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "Approach NORTH state reset"}
    
    # Check the state in snapshot
    snap_resp = client.get("/api/v1/snapshot")
    snap_data = snap_resp.json()
    assert snap_data["approachStatuses"]["north"] == "WAITING_FOR_INPUT"
    assert "north" not in snap_data["approachDetections"] or snap_data["approachDetections"]["north"] == {}

def test_reset_all_approaches():
    response = client.post("/api/v1/traffic/reset")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "All approaches state reset"}
    
    snap_resp = client.get("/api/v1/snapshot")
    snap_data = snap_resp.json()
    for approach in ["north", "south", "east", "west"]:
        assert snap_data["approachStatuses"][approach] == "WAITING_FOR_INPUT"
