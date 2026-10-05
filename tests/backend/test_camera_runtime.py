import pytest
import asyncio
import numpy as np
from fastapi.testclient import TestClient

from backend.app import app, camera_manager, state_store, orchestrator
from models import TrafficState, SystemStatus, Status

class FakeCameraSource:
    def __init__(self, frame_count=10, delay=0.01):
        self.frame_count = frame_count
        self.frames_read = 0
        self.released = False
        self.delay = delay
        self.error_on_frame = -1

    def read_frame(self):
        if self.error_on_frame == self.frames_read:
            raise RuntimeError("Fake camera hardware failure")
        if self.frames_read < self.frame_count:
            self.frames_read += 1
            return True, np.zeros((480, 640, 3), dtype=np.uint8)
        return False, None
        
    def release(self):
        self.released = True

    def draw_polygons(self, frame, polygons):
        pass

    def draw_detections(self, frame, detections, lane_assignments):
        pass

    def draw_state(self, frame, vis_state):
        pass

    def write_frame(self, frame):
        pass

@pytest.fixture
def clean_manager(mocker):
    # Stop any active tasks
    if camera_manager._active_thread:
        camera_manager._stop_event.set()
        camera_manager._active_thread = None
    state_store.set_traffic_state(None)
    
    # Prevent YOLO model download during tests
    mock_detector = mocker.MagicMock()
    mock_detector.detect.return_value = []
    camera_manager.vision_adapter.detector = mock_detector
    
    yield
    # Cleanup
    if camera_manager._active_thread:
        camera_manager._stop_event.set()
        camera_manager._active_thread = None
    camera_manager.vision_adapter.detector = None

@pytest.mark.asyncio
async def test_canonical_camera_runtime_success(clean_manager, mocker):
    """
    Test that the canonical one-camera runtime processes frames and pushes 
    TrafficState to the StateStore WITHOUT invoking the DecisionEngine directly.
    """
    # Mock orchestrator to prove it's not called directly by the camera loop
    mock_process = mocker.patch("backend.orchestrator.Orchestrator.process_traffic_state", new_callable=mocker.AsyncMock)
    
    # Mock VideoProcessor to use our FakeCameraSource
    mocker.patch("vision.video_processor.VideoProcessor", return_value=FakeCameraSource(frame_count=5))
    
    success, msg = await camera_manager.start("fake")
    assert success
    
    # Wait for processing to complete (5 frames should be very fast)
    await asyncio.sleep(0.5)
    
    # 1. TrafficState should have been populated in StateStore
    # (Note: Since the 5-frame source finishes immediately, the runtime's
    # finally block will clear the traffic state to handle STOPPED scenarios.
    # Therefore we verify it processed at least once via the version counter).
    assert state_store._traffic_state_version > 0
    
    # 2. DecisionEngine MUST NOT be invoked directly by the camera manager
    # (The camera manager just pushes to StateStore. Only the 10B scheduler invokes orchestrator).
    # Since we didn't start the 10B scheduler in this test context, orchestrator should have 0 calls.
    mock_process.assert_not_called()
    
    # 3. Source should be released because it hit EOS
    # The active thread should naturally finish
    assert not camera_manager._active_thread.is_alive()

@pytest.mark.asyncio
async def test_duplicate_start_prevented(clean_manager, mocker):
    """Test that a second start call is rejected while runtime is active."""
    mocker.patch("vision.video_processor.VideoProcessor", return_value=FakeCameraSource(frame_count=100))
    
    s1, _ = await camera_manager.start("fake")
    assert s1
    
    s2, msg = await camera_manager.start("fake")
    assert not s2
    assert "already active" in msg
    
    await camera_manager.stop()

@pytest.mark.asyncio
async def test_stop_releases_source(clean_manager, mocker):
    """Test that calling stop() cleanly releases the source mid-stream."""
    source = FakeCameraSource(frame_count=100)
    mocker.patch("vision.video_processor.VideoProcessor", return_value=source)
    
    await camera_manager.start("fake")
    await asyncio.sleep(0.1) # Let it read a few frames
    
    await camera_manager.stop()
    assert source.released

@pytest.mark.asyncio
async def test_source_failure_releases_source(clean_manager, mocker):
    """Test that an exception during processing releases the source and updates status."""
    source = FakeCameraSource(frame_count=10)
    source.error_on_frame = 2 # Crash on 3rd frame
    mocker.patch("vision.video_processor.VideoProcessor", return_value=source)
    
    await camera_manager.start("fake")
    await asyncio.sleep(0.2)
    
    # Task should have crashed and finished
    assert not camera_manager._active_thread.is_alive()
    assert source.released
    
    # Status should reflect ERROR
    status = state_store.get_system_status()
    assert status.vision == Status.ERROR

@pytest.mark.asyncio
async def test_shutdown_releases_source(clean_manager, mocker):
    """Test that application shutdown properly cleans up the camera manager."""
    source = FakeCameraSource(frame_count=100)
    mocker.patch("vision.video_processor.VideoProcessor", return_value=source)
    
    await camera_manager.start("fake")
    await asyncio.sleep(0.1)
    
    # Simulate FastAPI lifespan shutdown
    await camera_manager.shutdown()
    assert source.released

@pytest.mark.asyncio
async def test_stop_timeout_retains_source(clean_manager, mocker):
    """Test that a blocked thread prevents unsafe duplicate starts."""
    class BlockedFakeSource:
        def read_frame(self):
            import time
            time.sleep(3.0)  # Exceeds the 2.0s join timeout
            return False, None
        def release(self):
            pass
            
    mocker.patch("vision.video_processor.VideoProcessor", return_value=BlockedFakeSource())
    await camera_manager.start("fake")
    await asyncio.sleep(0.1)
    
    success, msg = await camera_manager.stop()
    assert not success
    assert "still busy" in msg
    assert camera_manager._active_thread is not None
    
    # Wait for the thread to actually finish to not leak in the test runner
    await asyncio.to_thread(camera_manager._active_thread.join)

@pytest.mark.asyncio
async def test_emergency_state_latch_prevents_overwrite(clean_manager, mocker):
    """
    Demonstrates the emergency latching behavior: a transient normal state 
    does not wipe out a latched emergency before the scheduler wakes up.
    """
    from models import EmergencyState, TrafficState
    from backend.app import _decision_event
    
    # 1. State A: Emergency
    state_a = TrafficState(timestamp=100.0, emergency=EmergencyState(detected=True, vehicle_type="ambulance"))
    state_store.set_traffic_state(state_a)
    _decision_event.set()  # Camera thread sets the event
    
    # 2. State B: Normal (before scheduler wakes up)
    state_b = TrafficState(timestamp=101.0, emergency=EmergencyState(detected=False))
    state_store.set_traffic_state(state_b)
    
    # 3. Scheduler wakes up
    fetched_state, _ = state_store.get_traffic_state_with_version()
    
    # 4. Assert the emergency was retained by the latch
    assert fetched_state.emergency.detected is True
