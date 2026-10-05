"""
Automated regression tests for the WP16 fast physical probe logic.
These tests use DummySerialTransport to validate the logic without physical hardware.
"""
import pytest
import time
from fastapi.testclient import TestClient

from backend.app import app
import backend.app as backend_app
from backend import core
from hardware.serial_transport import DummySerialTransport
from models.enums import PhysicalControllerStatus

@pytest.fixture(autouse=True)
def mock_hardware_transport():
    """Force the backend to use DummySerialTransport for automated tests."""
    dummy = DummySerialTransport()
    original_transport = core.physical_adapter.transport
    core.physical_adapter.transport = dummy
    core.physical_adapter.status = PhysicalControllerStatus.CONNECTED
    yield
    core.physical_adapter.transport = original_transport

@pytest.fixture(autouse=True)
def pause_background_decision_loop():
    """Isolate the test harness by pausing the background decision loop."""
    import asyncio
    
    original_loop = backend_app._decision_loop
    
    async def mock_decision_loop(*args, **kwargs):
        while True:
            await asyncio.sleep(3600)
            
    backend_app._decision_loop = mock_decision_loop
    yield
    backend_app._decision_loop = original_loop

@pytest.fixture(autouse=True)
def reset_state():
    """Reset the core singleton state before the test."""
    from models import SystemStatus, SystemMode, Status, SourceType, VisionStatus
    with core.state_store._lock:
        core.state_store._traffic_state = None
        core.state_store._traffic_state_version = 0
        core.state_store._signal_decision = None
        core.state_store._signal_state = None
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
    core.virtual_controller.state_machine.initialize(time.time())
    core.orchestrator.active_override = None

def make_demo_traffic(lanes=None):
    return {
        "timestamp": time.time(),
        "source": "fast-probe-test",
        "lanes": lanes or {
            "north": {"vehicle_count": 0, "occupancy": 0.0},
            "south": {"vehicle_count": 0, "occupancy": 0.0},
            "east": {"vehicle_count": 0, "occupancy": 0.0},
            "west": {"vehicle_count": 0, "occupancy": 0.0},
        },
        "emergency": {"detected": False, "lane": None}
    }

def test_fast_probe_north_east_exclusion():
    """
    Regression test proving that the manual NORTH safety test cannot result 
    in simultaneous NORTH and EAST GREEN states.
    """
    with TestClient(app) as client:
        # 1. Establish NORTH override
        resp = client.post("/api/v1/overrides", json={"selected_lane": "north", "duration": 15})
        assert resp.status_code == 200
        
        north_traffic = {
            "north": {"vehicle_count": 20, "occupancy": 0.8},
            "south": {"vehicle_count": 20, "occupancy": 0.8},
            "east": {"vehicle_count": 0, "occupancy": 0.0},
            "west": {"vehicle_count": 0, "occupancy": 0.0},
        }
        
        start_poll = time.time()
        north_established = False
        while time.time() - start_poll < 15.0:
            client.post("/api/v1/overrides", json={"selected_lane": "north", "duration": 15})
            client.post("/api/v1/demo/traffic", json=make_demo_traffic(lanes=north_traffic))
            
            snap = client.get("/api/v1/snapshot").json()
            active = set(snap["signalState"]["active_lanes"])
            phase = snap["signalState"]["phase"]
            
            # Assert NORTH and EAST are NEVER green at the same time
            if phase == "GREEN":
                assert not ("north" in active and "east" in active), "Simultaneous NORTH and EAST GREEN detected!"
                
            if "north" in active and phase == "GREEN":
                north_established = True
                break
            time.sleep(0.1)
            
        assert north_established, "Failed to establish NORTH GREEN."
        
        # 2. Preempt with EAST (should be rejected by SafetyValidator min-green)
        resp = client.post("/api/v1/overrides", json={"selected_lane": "east", "duration": 15})
        assert resp.status_code == 200
        
        east_traffic = {
            "north": {"vehicle_count": 0, "occupancy": 0.0},
            "south": {"vehicle_count": 0, "occupancy": 0.0},
            "east": {"vehicle_count": 20, "occupancy": 0.8},
            "west": {"vehicle_count": 20, "occupancy": 0.8},
        }
        
        client.post("/api/v1/demo/traffic", json=make_demo_traffic(lanes=east_traffic))
        
        snap = client.get("/api/v1/snapshot").json()
        active = set(snap["signalState"]["active_lanes"])
        phase = snap["signalState"]["phase"]
        
        assert snap["safetyResult"]["status"] == "REJECTED"
        assert not ("north" in active and "east" in active), "Simultaneous NORTH and EAST GREEN detected!"
        assert "north" in active, "State mutated despite rejection!"
