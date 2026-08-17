"""
Tests for WebSocket endpoint /ws/traffic and WebSocketManager.
"""

from fastapi.testclient import TestClient
from backend.app import app, state_store, virtual_controller
from models import TrafficState, SignalDecision, SignalState, Lane, SignalPhase, SignalColor


def test_websocket_traffic_connection_and_initial_snapshot():
    """Verify WebSocket client connection and initial snapshot structure with real SignalState."""
    client = TestClient(app)

    # Set up initial state in store
    ts = TrafficState(timestamp=10.0)
    dec = SignalDecision(
        decision_id="dec-ws-1",
        timestamp=10.0,
        selected_lane=Lane.NORTH,
        duration=20,
    )
    # Also update virtual controller since app pulls from orchestrator now
    virtual_controller.execute_decision(target_lane=Lane.NORTH, duration=20, current_time=10.0)

    state_store.set_traffic_state(ts)
    state_store.set_decision(dec)

    with client.websocket_connect("/ws/traffic") as websocket:
        data = websocket.receive_json()

        assert "trafficState" in data
        assert "signalDecision" in data
        assert "signalState" in data
        assert data["signalState"] is not None  # Phase 3 requirement: real SignalState emitted
        assert "systemStatus" in data
        assert "events" in data

        assert data["trafficState"]["timestamp"] == 10.0
        assert data["signalDecision"]["selected_lane"] == "north"
        assert data["signalState"]["north"] == "GREEN"
        assert data["signalState"]["phase"] == "GREEN"
