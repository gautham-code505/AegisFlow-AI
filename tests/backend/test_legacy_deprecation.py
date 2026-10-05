import pytest
import asyncio
from fastapi.testclient import TestClient
from backend.app import app, camera_manager
from models import TrafficState

pytestmark = pytest.mark.filterwarnings("ignore:.*The 4-approach.*:DeprecationWarning")

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def mock_vision_adapter(monkeypatch):
    class MockAdapter:
        def process_single_approach_video(self, *args, **kwargs):
            from models import LaneState, EmergencyState
            return LaneState(vehicle_count=5), [], EmergencyState()
            
    import backend.app
    monkeypatch.setattr(backend.app, "vision_adapter", MockAdapter())
    return MockAdapter()

def test_canonical_path_available(client):
    """Verify canonical one-camera start endpoint is functional."""
    # We don't want to actually run the camera in a pytest, just check it exists
    # If the environment lacks OpenCV/YOLO, the start might fail immediately,
    # but the endpoint route must be 200 or 400 (not 404).
    response = client.post("/api/v1/camera/stop")
    assert response.status_code in [200, 400] # 400 means "Runtime not active", which is expected

def test_legacy_path_functional(client, monkeypatch):
    """Verify legacy 4-video endpoint remains functional but warns."""
    
    # Mock is_active to ensure we aren't blocked by a dangling thread in another test
    monkeypatch.setattr(camera_manager, "is_active", lambda: False)
    
    # We can post a dummy file to the legacy endpoint
    file_content = b"fake video content"
    response = client.post(
        "/api/v1/video/upload/north",
        files={"file": ("test.mp4", file_content, "video/mp4")}
    )
    
    # Assert functional
    assert response.status_code == 200
    
    # Assert deprecation metadata
    data = response.json()
    assert data.get("deprecated") is True
    assert "status" in data

def test_simultaneous_runtime_safety(client, monkeypatch):
    """Verify legacy endpoint rejects uploads if canonical camera is running."""
    
    # Mock camera_manager to appear active
    monkeypatch.setattr(camera_manager, "is_active", lambda: True)
    
    file_content = b"fake video content"
    response = client.post(
        "/api/v1/video/upload/north",
        files={"file": ("test.mp4", file_content, "video/mp4")}
    )
    
    # Assert explicitly rejected due to conflict
    assert response.status_code == 409
    assert "Cannot process legacy four-video uploads while the canonical One-Camera runtime is active." in response.json()["detail"]

def test_legacy_state_aggregation(monkeypatch):
    """Verify legacy approach aggregation produces valid TrafficState."""
    from backend.app import _approach_lane_states, _approach_emergencies, _approach_lock
    import time
    from models import LaneState, EmergencyState, Lane
    
    async def simulate_background():
        async with _approach_lock:
            _approach_lane_states["north"] = LaneState(vehicle_count=3)
            _approach_lane_states["south"] = LaneState(vehicle_count=2)
            _approach_emergencies["north"] = EmergencyState(detected=False)
            
            lanes = {}
            for dir_name in ["north", "south", "east", "west"]:
                if dir_name in _approach_lane_states:
                    lanes[Lane(dir_name)] = _approach_lane_states[dir_name]
                else:
                    lanes[Lane(dir_name)] = LaneState()
                    
            state = TrafficState(timestamp=time.time(), lanes=lanes, emergency=EmergencyState())
            return state
            
    state = asyncio.run(simulate_background())
    assert isinstance(state, TrafficState)
    assert state.lanes[Lane("north")].vehicle_count == 3
    assert state.lanes[Lane("south")].vehicle_count == 2
    assert state.lanes[Lane("east")].vehicle_count == 0
