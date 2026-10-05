import pytest
from backend.runtime import CameraRuntimeManager
from backend.core import StateStore
import asyncio
from unittest.mock import MagicMock

@pytest.fixture
def manager():
    store = StateStore()
    adapter = MagicMock()
    decision_event = asyncio.Event()
    logger = MagicMock()
    
    # Mock adapter to return a fast empty generator
    def mock_process(*args, **kwargs):
        yield MagicMock()
    adapter.process_source = mock_process
    
    return CameraRuntimeManager(store, adapter, decision_event, lambda: None, logger)

@pytest.mark.asyncio
async def test_valid_numeric_source(manager, mocker):
    """Test that a valid numeric source can be started."""
    # Mock VideoProcessor to not actually open a camera
    mock_vp = mocker.patch("vision.video_processor.VideoProcessor")
    
    success, msg = await manager.start(2)
    assert success is True
    
    await asyncio.sleep(0.1) # Let thread run
    mock_vp.assert_called_once()
    assert mock_vp.call_args[0][0] == 2
    await manager.stop()

@pytest.mark.asyncio
async def test_unavailable_source(manager, mocker):
    """Test that an unavailable source fails cleanly."""
    # Mock VideoProcessor to raise ValueError (simulate cv2 failing to open)
    mocker.patch("vision.video_processor.VideoProcessor", side_effect=ValueError("Could not open video file/stream"))
    
    success, msg = await manager.start(99)
    assert success is True # Start returns True because _run_sync is async
    
    await asyncio.sleep(0.1)
    # The background thread should have caught the error
    status = manager.state_store.get_system_status()
    assert status.vision.value == "ERROR"
    assert status.camera.value == "NO INPUT"

@pytest.mark.asyncio
async def test_source_configuration_matches(manager, mocker):
    """Test that if verify_res matches, it proceeds."""
    mock_vp = mocker.patch("vision.video_processor.VideoProcessor")
    
    success, msg = await manager.start(2, verify_res=[1280, 720])
    assert success is True
    
    await asyncio.sleep(0.1)
    mock_vp.assert_called_once()
    assert mock_vp.call_args[1]["expected_width"] == 1280
    assert mock_vp.call_args[1]["expected_height"] == 720
    await manager.stop()

@pytest.mark.asyncio
async def test_no_accidental_fallback_resolution_mismatch(manager, mocker):
    """Test that if the wrong camera is opened (resolution mismatch), it fails and does not continue."""
    # We simulate the VideoProcessor raising the ValueError when expected dimensions don't match
    mocker.patch("vision.video_processor.VideoProcessor", side_effect=ValueError("Camera resolution mismatch. Expected 1280x720, got 640x480"))
    
    success, msg = await manager.start(0, verify_res=[1280, 720])
    assert success is True
    
    await asyncio.sleep(0.1)
    status = manager.state_store.get_system_status()
    # It must fail cleanly, stopping perception
    assert status.vision.value == "ERROR"
    assert status.camera.value == "NO INPUT"
