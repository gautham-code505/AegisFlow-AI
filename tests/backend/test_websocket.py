"""
Tests for WebSocket endpoint /ws/traffic and WebSocketManager.
"""

from fastapi.testclient import TestClient
from backend.app import app, state_store, virtual_controller
from models import TrafficState, SignalDecision, SignalState, Lane, SignalPhase, SignalColor, SourceType, VisionStatus


def test_websocket_traffic_connection_and_initial_snapshot():
    """Verify WebSocket client connection and initial snapshot structure with real SignalState."""
    client = TestClient(app)

    import time
    now = time.time()
    
    # Initialize virtual_controller to avoid state leakage from other tests
    virtual_controller.state_machine.initialize(now)
    
    # Set up initial state in store
    ts = TrafficState(timestamp=now)
    dec = SignalDecision(
        decision_id="dec-ws-1",
        timestamp=now,
        selected_lane=Lane.NORTH,
        duration=20,
    )
    # Also update virtual controller since app pulls from orchestrator now
    virtual_controller.execute_decision(target_lane=Lane.NORTH, duration=20, current_time=now)

    status = state_store.get_system_status()
    status.camera = SourceType.LIVE_CAMERA
    status.vision = VisionStatus.PROCESSING
    state_store.set_system_status(status)

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

        assert data["trafficState"]["timestamp"] == now
        assert data["signalDecision"]["selected_lane"] == "north"
        assert data["signalState"]["north"] == "GREEN"
        assert data["signalState"]["phase"] == "GREEN"

import pytest
from backend.app import orchestrator

@pytest.mark.asyncio
async def test_websocket_throttling_and_critical_delivery():
    """Verify state-aware WebSocket throttling and immediate delivery of critical events."""
    from backend.websocket_manager import WebSocketManager
    from models import SystemStatus, SystemMode, Status, Priority, Lane, SignalPhase, SignalColor
    import time
    
    manager = WebSocketManager()
    
    # Mock WebSocket
    class MockWebSocket:
        def __init__(self):
            self.messages = []
        async def send_json(self, data):
            self.messages.append(data)
            
    mock_ws = MockWebSocket()
    manager.active_connections.append(mock_ws)
    
    # 1. First broadcast (allowed)
    now = time.time()
    sys_status = SystemStatus(timestamp=now, mode=SystemMode.LOCAL, internet=Status.ONLINE, camera=SourceType.LIVE_CAMERA, vision=VisionStatus.PROCESSING, decision_engine=Status.ONLINE, safety=Status.ONLINE, controller=Status.ONLINE)
    
    await manager.broadcast_snapshot(None, None, None, sys_status, [], [])
    assert len(mock_ws.messages) == 1
    
    # 2. Second broadcast immediately after, no significant change (should be throttled)
    await manager.broadcast_snapshot(None, None, None, sys_status, [], [])
    assert len(mock_ws.messages) == 1 # Still 1
    
    # 3. Third broadcast immediately after, with EMERGENCY decision (should NOT be throttled)
    emg_dec = SignalDecision(decision_id="d1", timestamp=now, selected_lane=Lane.NORTH, duration=10, priority=Priority.EMERGENCY)
    await manager.broadcast_snapshot(None, emg_dec, None, sys_status, [], [])
    assert len(mock_ws.messages) == 2
    
    # 4. Fourth broadcast, SignalState change (should NOT be throttled)
    sig_state = SignalState(timestamp=now, phase=SignalPhase.YELLOW, north=SignalColor.YELLOW, south=SignalColor.YELLOW, east=SignalColor.RED, west=SignalColor.RED, active_lanes=[Lane.NORTH])
    await manager.broadcast_snapshot(None, None, sig_state, sys_status, [], [])
    assert len(mock_ws.messages) == 3
    
    # 5. Fifth broadcast, Safety Rejection (should NOT be throttled)
    safety_res = {"status": "REJECTED"}
    await manager.broadcast_snapshot(None, None, sig_state, sys_status, [], [], safety_result=safety_res)
    assert len(mock_ws.messages) == 4
    
    # 6. Wait 1.1s, normal broadcast (should NOT be throttled due to time)
    manager._last_broadcast_time = now - 1.1
    await manager.broadcast_snapshot(None, None, sig_state, sys_status, [], [])
    assert len(mock_ws.messages) == 5
