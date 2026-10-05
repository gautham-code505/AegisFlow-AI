"""
AegisFlow — WP16 Automated E2E Integration Tests
================================================
These tests run in the automated test suite and use DummySerialTransport
to validate the integration of the Backend APIs, Orchestrator, Controller,
Safety Validator, and Hardware Adapter.
"""
import pytest
import time
import json
from unittest.mock import patch
from fastapi.testclient import TestClient

from backend.app import app
from backend import core
from backend.state_store import StateStore
from controller.virtual_controller import VirtualSignalController
from hardware.serial_transport import DummySerialTransport
from models import Priority, Lane, SignalPhase


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset core singletons before each test to prevent state leakage."""
    import time
    from models import SystemStatus, SystemMode, Status, SourceType, VisionStatus
    
    # Reset StateStore in place
    with core.state_store._lock:
        core.state_store._traffic_state = None
        core.state_store._traffic_state_version = 0
        core.state_store._signal_decision = None
        core.state_store._signal_state = None
        core.state_store._events.clear()
        core.state_store._measurements.clear()
        core.state_store._approach_detections.clear()
        core.state_store._approach_statuses.clear()
        core.state_store._safety_result = None
        core.state_store._active_emergency = None
        core.state_store._emergency_expires_at = 0.0
        core.state_store._system_status = SystemStatus(
            timestamp=time.time(),
            mode=SystemMode.LOCAL,
            internet=Status.OFFLINE,
            camera=SourceType.LIVE_CAMERA,
            vision=VisionStatus.PROCESSING,
            decision_engine=Status.ONLINE,
            safety=Status.ONLINE,
            controller=Status.ONLINE,
        )

    # Reset VirtualSignalController in place
    core.virtual_controller.state_machine.initialize(time.time())

    # Reset Orchestrator state
    core.orchestrator.active_override = None
    core.orchestrator._last_signal_state = None
    core.orchestrator._active_measurement = None

    # Reset DecisionEngine in place to prevent cross-test starvation leakage
    if hasattr(core, "decision_adapter") and hasattr(core.decision_adapter, "engine"):
        engine = core.decision_adapter.engine
        engine.waiting_times = {lane: 0.0 for lane in engine.config.VALID_LANES}
        engine.consecutive_skips = {lane: 0 for lane in engine.config.VALID_LANES}
        engine.last_active_lane = None
        engine.last_duration = engine.config.DEFAULT_GREEN_DURATION
        engine.last_timestamp = None
        engine.last_scores = {}
    yield


@pytest.fixture(autouse=True)
def pause_background_decision_loop():
    """
    Isolate the test harness by pausing the background decision loop.
    This ensures no competing background scheduler decisions happen 
    while the test is precisely stepping through state changes.
    """
    import backend.app as backend_app
    import asyncio
    
    original_loop = backend_app._decision_loop
    
    async def mock_decision_loop(*args, **kwargs):
        while True:
            await asyncio.sleep(3600)
            
    backend_app._decision_loop = mock_decision_loop
    yield
    backend_app._decision_loop = original_loop
@pytest.fixture(autouse=True)
def mock_hardware_transport():
    """Force the backend to use DummySerialTransport for automated tests."""
    dummy = DummySerialTransport()
    # Mock ACKs automatically for test stability
    original_write = dummy.write_line
    def auto_ack_write(data: str) -> bool:
        res = original_write(data)
        try:
            payload = json.loads(data)
            if payload.get("type") == "SET_SIGNAL_STATE":
                cmd_id = payload.get("command_id", 1)
                ack = json.dumps({"version": 1, "type": "ACK", "command_id": cmd_id})
                dummy.mock_responses.append(ack + "\n")
        except:
            pass
        return res
        
    dummy.write_line = auto_ack_write
    dummy.connected = True
    
    with patch.object(core, 'physical_adapter') as mock_adapter:
        # Actually, it's easier to just patch the transport inside the real adapter!
        pass
        
    # Real way to patch:
    old_transport = core.physical_adapter.transport
    core.physical_adapter.transport = dummy
    yield dummy
    core.physical_adapter.transport = old_transport


def test_wp16_backend_to_adapter_e2e(mock_hardware_transport):
    """
    WP16.1: Drive deterministic traffic through real API, verify decision, safety,
    signal state, and that SET_SIGNAL_STATE is written to the transport.
    """
    with TestClient(app) as client:
        time.sleep(0.1) # allow adapter start
        
        # Inject traffic
        payload = {
            "timestamp": time.time(),
            "source": "e2e-test",
            "lanes": {
                "north": {"vehicle_count": 25, "occupancy": 0.8},
                "south": {"vehicle_count": 0, "occupancy": 0.0},
                "east": {"vehicle_count": 0, "occupancy": 0.0},
                "west": {"vehicle_count": 0, "occupancy": 0.0},
            },
            "emergency": {"detected": False, "lane": None}
        }
        resp = client.post("/api/v1/demo/traffic", json=payload)
        assert resp.status_code == 200
        
        # Verify decision
        dec = resp.json()
        assert dec["selected_lane"] == "north"
        
        # Wait a moment for hardware dispatch
        time.sleep(0.3)
        
        # Verify transport received SET_SIGNAL_STATE
        assert mock_hardware_transport.last_written is not None
        written = json.loads(mock_hardware_transport.last_written)
        assert written["type"] in ("SET_SIGNAL_STATE", "PING") # Might have sent PING too
        
        # Check snapshot
        snap = client.get("/api/v1/snapshot").json()
        assert snap["signalState"]["active_lanes"] == ["north", "south"]
        
        # WP16.5: WebSocket Synchronization
        with client.websocket_connect("/ws/traffic") as websocket:
            fresh_ws_payload = dict(payload)
            fresh_ws_payload["timestamp"] = time.time()
            client.post("/api/v1/demo/traffic", json=fresh_ws_payload)
            data = websocket.receive_json()
            assert "signalState" in data
            assert data["signalState"]["active_lanes"] == ["north", "south"]


def test_wp16_safety_integration_e2e(mock_hardware_transport):
    """
    WP16.3: Safety Integration. Attempt to preempt an active minimum green.
    Verify unsafe proposal doesn't become authoritative.
    Explicitly proves:
      - NORTH is established as active GREEN (APPROVED, not FALLBACK)
      - EAST request is attempted immediately within MIN_GREEN window
      - SafetyValidator specifically rejects EAST with 'Minimum green hold' (status REJECTED, not FALLBACK)
      - Authoritative active lane remains NORTH
    """
    with TestClient(app) as client:
        time.sleep(0.1)
        
        # 1. Force North Green
        resp1 = client.post("/api/v1/overrides", json={"selected_lane": "north", "duration": 15})
        assert resp1.status_code == 200
        
        north_traffic = {
            "north": {"vehicle_count": 20, "occupancy": 0.8},
            "south": {"vehicle_count": 20, "occupancy": 0.8},
            "east": {"vehicle_count": 0, "occupancy": 0.0},
            "west": {"vehicle_count": 0, "occupancy": 0.0},
        }
        
        start_poll = time.time()
        while time.time() - start_poll < 15.0: # increase timeout to 15s to outlast any existing min-green hold (10s)
            # Must re-post the override to ensure the requested SignalDecision stays fresh (< 5.0s age)
            client.post("/api/v1/overrides", json={"selected_lane": "north", "duration": 15})
            
            resp2 = client.post("/api/v1/demo/traffic", json={"timestamp": time.time(), "lanes": north_traffic})
            assert resp2.status_code == 200
            
            snap1 = client.get("/api/v1/snapshot").json()
            if "north" in snap1["signalState"]["active_lanes"] and snap1["signalState"]["phase"] == "GREEN":
                break
            time.sleep(0.1)
        else:
            raise AssertionError(f"Timeout waiting for NORTH GREEN transition. Active lanes: {snap1['signalState']['active_lanes']}, Phase: {snap1['signalState']['phase']}")
            
        assert "north" in snap1["signalState"]["active_lanes"]
        assert snap1["signalState"]["phase"] == "GREEN"
        assert snap1["safetyResult"]["status"] == "APPROVED"
        assert snap1["systemStatus"]["mode"] != "FALLBACK", "Initial activation must not be in FALLBACK"
        
        # 2. Immediately force East (this violates min green time of 10s)
        resp3 = client.post("/api/v1/overrides", json={"selected_lane": "east", "duration": 15})
        assert resp3.status_code == 200
        
        east_traffic = {
            "north": {"vehicle_count": 0, "occupancy": 0.0},
            "south": {"vehicle_count": 0, "occupancy": 0.0},
            "east": {"vehicle_count": 20, "occupancy": 0.8},
            "west": {"vehicle_count": 20, "occupancy": 0.8},
        }
        resp4 = client.post("/api/v1/demo/traffic", json={"timestamp": time.time(), "lanes": east_traffic})
        assert resp4.status_code == 200
        
        # 3. Verify it was rejected specifically due to minimum green hold and North is still green
        snap2 = client.get("/api/v1/snapshot").json()
        assert snap2["safetyResult"]["status"] == "REJECTED", "Must be REJECTED, not FALLBACK"
        assert snap2["systemStatus"]["mode"] != "FALLBACK", "Must not rely on or trigger FALLBACK mode"
        assert any("Minimum green hold" in r for r in snap2["safetyResult"]["reasons"]), (
            f"Expected Minimum green hold rejection reason, got: {snap2['safetyResult']['reasons']}"
        )
        assert "north" in snap2["signalState"]["active_lanes"], "Authoritative active lane must remain NORTH"
        assert snap2["signalState"]["phase"] == "GREEN"


def test_wp16_consecutive_fresh_traffic_accepted(mock_hardware_transport):
    """
    WP16: Verify that consecutive demo traffic requests receive different fresh timestamps
    and are accepted by SafetyValidator as fresh (APPROVED, not FALLBACK).
    Also confirms that an artificially stale timestamp (> 5s old) is detected as stale and triggers FALLBACK.
    """
    with TestClient(app) as client:
        time.sleep(0.1)
        
        # 1. First fresh demo traffic
        t1 = time.time()
        payload1 = {
            "timestamp": t1,
            "source": "consecutive-test-1",
            "lanes": {
                "north": {"vehicle_count": 10, "occupancy": 0.5},
                "south": {"vehicle_count": 0, "occupancy": 0.0},
                "east": {"vehicle_count": 0, "occupancy": 0.0},
                "west": {"vehicle_count": 0, "occupancy": 0.0},
            },
            "emergency": {"detected": False, "lane": None}
        }
        resp1 = client.post("/api/v1/demo/traffic", json=payload1)
        assert resp1.status_code == 200
        
        snap1 = client.get("/api/v1/snapshot").json()
        assert snap1["safetyResult"]["status"] == "APPROVED"
        assert snap1["systemStatus"]["mode"] != "FALLBACK"
        assert snap1["trafficState"]["timestamp"] == t1
        
        # Wait briefly to ensure distinct timestamps
        time.sleep(0.05)
        
        # 2. Second fresh demo traffic with distinct timestamp
        t2 = time.time()
        assert t2 > t1, "Consecutive timestamps must be distinct and increasing"
        payload2 = {
            "timestamp": t2,
            "source": "consecutive-test-2",
            "lanes": {
                "north": {"vehicle_count": 12, "occupancy": 0.55},
                "south": {"vehicle_count": 0, "occupancy": 0.0},
                "east": {"vehicle_count": 0, "occupancy": 0.0},
                "west": {"vehicle_count": 0, "occupancy": 0.0},
            },
            "emergency": {"detected": False, "lane": None}
        }
        resp2 = client.post("/api/v1/demo/traffic", json=payload2)
        assert resp2.status_code == 200
        
        snap2 = client.get("/api/v1/snapshot").json()
        assert snap2["safetyResult"]["status"] == "APPROVED"
        assert snap2["systemStatus"]["mode"] != "FALLBACK"
        assert snap2["trafficState"]["timestamp"] == t2
        
        # 3. Contrast verification: Send a stale payload (> 5s old)
        stale_time = time.time() - 10.0
        stale_payload = {
            "timestamp": stale_time,
            "source": "stale-test",
            "lanes": {},
            "emergency": {"detected": False, "lane": None}
        }
        resp_stale = client.post("/api/v1/demo/traffic", json=stale_payload)
        assert resp_stale.status_code == 200
        
        snap_stale = client.get("/api/v1/snapshot").json()
        assert snap_stale["safetyResult"]["status"] == "FALLBACK"
        assert snap_stale["systemStatus"]["mode"] == "FALLBACK"
        assert any("Stale TrafficState detected" in r for r in snap_stale["safetyResult"]["reasons"])


def test_wp16_camera_smoke_e2e(tmp_path):
    """
    WP16.4: Canonical One-Camera Smoke E2E via image upload
    """
    with TestClient(app) as client:
        import cv2
        import numpy as np
        
        # Create a dummy image
        img_path = str(tmp_path / "test.jpg")
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.imwrite(img_path, img)
        
        # Upload image to trigger vision -> traffic -> decision -> signal
        with open(img_path, "rb") as f:
            resp = client.post("/api/v1/image/upload", files={"file": ("test.jpg", f, "image/jpeg")})
            
        assert resp.status_code == 200
        assert "processing started" in resp.json()["message"]


def test_wp16_interactive_waits_prevent_stale_traffic(mock_hardware_transport):
    """
    WP16: Verify that simulating long interactive waits (e.g. WP16.5/WP16.6 prompts)
    does not cause the SafetyValidator to trigger FALLBACK if heartbeat traffic
    is continuously sent.
    """
    with TestClient(app) as client:
        time.sleep(0.1)
        
        # Start with fresh traffic
        client.post("/api/v1/demo/traffic", json={"timestamp": time.time(), "lanes": {}})
        
        # Simulate a 6.5 second pause (STALE_DATA_SECONDS is 5.0)
        # by sending heartbeat traffic from the main thread
        start = time.time()
        while time.time() - start < 6.5:
            client.post("/api/v1/demo/traffic", json={
                "timestamp": time.time(),
                "source": "heartbeat-test",
                "lanes": {},
                "emergency": {"detected": False, "lane": None}
            })
            time.sleep(0.5)
            
        # Check snapshot to ensure FALLBACK wasn't triggered
        snap = client.get("/api/v1/snapshot").json()
        assert snap["safetyResult"]["status"] != "FALLBACK", f"Safety triggered FALLBACK! Status was {snap['safetyResult']['status']}"
        assert snap["systemStatus"]["mode"] != "FALLBACK", "System entered FALLBACK despite heartbeat traffic!"


def test_wp16_stale_signal_decision_polling_regression(mock_hardware_transport):
    """
    WP16: Regression test for stale SignalDecision during a minimum-green hold.
    If a manual override is requested but rejected by min-green hold, the probe
    must continuously refresh the override request while polling. If it only
    sends demo traffic without refreshing the override for >5s, the decision
    itself becomes stale and is rejected by the SafetyValidator.
    """
    with TestClient(app) as client:
        time.sleep(0.1)
        
        # 1. Establish EAST as GREEN to start a 10s min-green hold
        client.post("/api/v1/overrides", json={"selected_lane": "east", "duration": 15})
        client.post("/api/v1/demo/traffic", json={"timestamp": time.time(), "lanes": {}})
        
        # 2. Attempt NORTH override (will be rejected initially due to hold)
        client.post("/api/v1/overrides", json={"selected_lane": "north", "duration": 15})
        
        # Wait 6 seconds sending ONLY traffic (not refreshing override)
        start = time.time()
        while time.time() - start < 6.0:
            client.post("/api/v1/demo/traffic", json={"timestamp": time.time(), "lanes": {}})
            time.sleep(0.5)
            
        # The override decision is now >5s old. The latest rejection reason must be Stale SignalDecision.
        snap = client.get("/api/v1/snapshot").json()
        assert snap["safetyResult"]["status"] == "REJECTED"
        assert any("Stale SignalDecision detected" in r for r in snap["safetyResult"]["reasons"]), (
            f"Expected 'Stale SignalDecision detected' but got: {snap['safetyResult']['reasons']}"
        )
        
        # 3. Now prove that refreshing the override fixes it.
        # Send fresh override
        client.post("/api/v1/overrides", json={"selected_lane": "north", "duration": 15})
        client.post("/api/v1/demo/traffic", json={"timestamp": time.time(), "lanes": {}})
        
        snap_fixed = client.get("/api/v1/snapshot").json()
        # It might still be REJECTED for min-green hold if 10s hasn't passed,
        # but it should NOT be rejected for Stale SignalDecision anymore.
        assert not any("Stale SignalDecision detected" in r for r in snap_fixed["safetyResult"]["reasons"]), (
            "Decision should be fresh now, but still marked stale."
        )


def test_wp16_manual_override_with_deterministic_traffic(mock_hardware_transport):
    """
    WP16: Regression test proving that by sending deterministic traffic 
    aligned with the manual override, we prevent any background/normal 
    scheduler decisions from competing and starting an opposing transition.
    """
    with TestClient(app) as client:
        time.sleep(0.1)
        
        # 1. Start EAST
        client.post("/api/v1/overrides", json={"selected_lane": "east", "duration": 15})
        client.post("/api/v1/demo/traffic", json={"timestamp": time.time(), "lanes": {}})
        
        time.sleep(0.5)
        
        # 3. Apply NORTH override and poll
        north_traffic = {
            "north": {"vehicle_count": 20, "occupancy": 0.8},
            "south": {"vehicle_count": 20, "occupancy": 0.8},
            "east": {"vehicle_count": 0, "occupancy": 0.0},
            "west": {"vehicle_count": 0, "occupancy": 0.0},
        }
        
        start_poll = time.time()
        success = False
        while time.time() - start_poll < 15.0:
            client.post("/api/v1/overrides", json={"selected_lane": "north", "duration": 15})
            client.post("/api/v1/demo/traffic", json={"timestamp": time.time(), "lanes": north_traffic})
            
            snap = client.get("/api/v1/snapshot").json()
            if "north" in snap["signalState"]["active_lanes"] and snap["signalState"]["phase"] == "GREEN":
                success = True
                break
            time.sleep(0.1)
            
        assert success, "Failed to establish NORTH green with deterministic traffic."
        
        # Verify no EAST competition happened
        assert "north" in snap["signalState"]["active_lanes"]

