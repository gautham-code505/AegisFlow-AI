import pytest
import asyncio
from fastapi.testclient import TestClient
from backend.app import app, camera_manager
from backend.runtime import CameraStartRequest

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
        def process_single_approach_image(self, *args, **kwargs):
            from models import LaneState, EmergencyState
            return LaneState(vehicle_count=5), [], EmergencyState()
    import backend.app
    monkeypatch.setattr(backend.app, "vision_adapter", MockAdapter())
    return MockAdapter()

@pytest.fixture(autouse=True)
def reset_coordinator():
    # Reset state between tests
    camera_manager._legacy_active_count = 0
    camera_manager._active_thread = None

def test_canonical_active_blocks_legacy_video(client, monkeypatch):
    monkeypatch.setattr(camera_manager, "is_active", lambda: True)
    file_content = b"fake video content"
    response = client.post(
        "/api/v1/video/upload/north",
        files={"file": ("test.mp4", file_content, "video/mp4")}
    )
    assert response.status_code == 409

def test_canonical_active_blocks_legacy_image(client, monkeypatch):
    monkeypatch.setattr(camera_manager, "is_active", lambda: True)
    file_content = b"fake image content"
    response = client.post(
        "/api/v1/image/upload/north",
        files={"file": ("test.jpg", file_content, "image/jpeg")}
    )
    assert response.status_code == 409

@pytest.mark.asyncio
async def test_legacy_active_blocks_canonical_start(monkeypatch):
    # Simulate legacy running
    camera_manager._legacy_active_count = 1
    monkeypatch.setattr(camera_manager, "is_active", lambda: False)
    
    success, msg = await camera_manager.start(0)
    assert success is False
    assert "legacy runtime is active" in msg

@pytest.mark.asyncio
async def test_both_inactive_canonical_succeeds(monkeypatch):
    # We mock out thread start so it doesn't actually try to run OpenCV
    class FakeThread:
        def start(self): pass
        def is_alive(self): return False
        def join(self, *args, **kwargs): pass
    
    import threading
    monkeypatch.setattr(threading, "Thread", lambda **kwargs: FakeThread())
    
    success, msg = await camera_manager.start(0)
    assert success is True

def test_both_inactive_legacy_succeeds(client):
    file_content = b"fake video content"
    response = client.post(
        "/api/v1/video/upload/north",
        files={"file": ("test.mp4", file_content, "video/mp4")}
    )
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_after_canonical_stop_legacy_can_start(monkeypatch):
    # Simulate canonical thread stopped
    monkeypatch.setattr(camera_manager, "is_active", lambda: False)
    success = await camera_manager.try_acquire_legacy()
    assert success is True

@pytest.mark.asyncio
async def test_after_legacy_stops_canonical_can_start(monkeypatch):
    # Simulate legacy started then stopped
    await camera_manager.try_acquire_legacy()
    await camera_manager.release_legacy()
    
    class FakeThread:
        def start(self): pass
        def is_alive(self): return False
        def join(self, *args, **kwargs): pass
    import threading
    monkeypatch.setattr(threading, "Thread", lambda **kwargs: FakeThread())
    
    success, msg = await camera_manager.start(0)
    assert success is True

@pytest.mark.asyncio
async def test_concurrent_start_race_handled(monkeypatch):
    """Proves that even if legacy and canonical start nearly simultaneously, they won't both succeed."""
    
    class FakeThread:
        def start(self): pass
        def is_alive(self): return True # Pretend it immediately becomes active
        def join(self, *args, **kwargs): pass
    import threading
    monkeypatch.setattr(threading, "Thread", lambda **kwargs: FakeThread())
    
    # We schedule both coroutines to run concurrently
    results = await asyncio.gather(
        camera_manager.start(0),
        camera_manager.try_acquire_legacy()
    )
    
    # Exactly one should succeed.
    canonical_success = results[0][0]
    legacy_success = results[1]
    
    # They cannot both be true
    assert not (canonical_success and legacy_success)
    # At least one must be true (no deadlock)
    assert canonical_success or legacy_success
