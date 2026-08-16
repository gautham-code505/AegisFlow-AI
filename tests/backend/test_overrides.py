import pytest
from fastapi.testclient import TestClient
from backend.app import app, state_store, orchestrator
from models import Priority, Lane, SignalDecision

client = TestClient(app)

def setup_function():
    orchestrator.active_override = None

def test_override_activates_and_clears():
    # 1. Post Override
    response = client.post("/api/v1/overrides", json={
        "selected_lane": "north",
        "duration": 45
    })
    assert response.status_code == 200
    assert response.json()["message"] == "Manual override set to NORTH"
    
    assert orchestrator.active_override is not None
    assert orchestrator.active_override.selected_lane == Lane.NORTH
    assert orchestrator.active_override.duration == 45
    assert orchestrator.active_override.priority == Priority.MANUAL
    
    # 2. Check snapshot includes the override logic
    snap_resp = client.get("/api/v1/snapshot")
    assert snap_resp.status_code == 200
    events = snap_resp.json().get("events", [])
    assert any(e["type"] == "OPERATOR_OVERRIDE" for e in events)

    # 3. Clear Override
    del_resp = client.delete("/api/v1/overrides/current")
    assert del_resp.status_code == 200
    assert orchestrator.active_override is None
    
    # 4. Check clear event
    snap_resp = client.get("/api/v1/snapshot")
    events = snap_resp.json().get("events", [])
    assert any(e["type"] == "OPERATOR_OVERRIDE_CLEARED" for e in events)

def test_override_invalid_lane():
    response = client.post("/api/v1/overrides", json={
        "selected_lane": "diagonal",
        "duration": 45
    })
    assert response.status_code == 400
