import pytest
import numpy as np
from vision.video_processor import VideoProcessor
from vision.adapter import VisionAdapter
from models import TrafficState

class FakeSource:
    def __init__(self, frame_count=5):
        self.frame_count = frame_count
        self.frames_read = 0
        self.released = False

    def read_frame(self):
        if self.frames_read < self.frame_count:
            self.frames_read += 1
            # Return a blank 640x480 frame
            return True, np.zeros((480, 640, 3), dtype=np.uint8)
        return False, None
        
    def release(self):
        self.released = True


class ErrorSource:
    def __init__(self):
        self.released = False

    def read_frame(self):
        raise RuntimeError("Mock hardware failure")
        
    def release(self):
        self.released = True


def test_fake_source_lifecycle():
    """Test that a fake source yields frames and hits EOS."""
    source = FakeSource(frame_count=3)
    count = 0
    while True:
        ret, frame = source.read_frame()
        if not ret:
            break
        count += 1
        assert frame.shape == (480, 640, 3)
    
    assert count == 3
    source.release()
    assert source.released


def test_vision_adapter_with_fake_source():
    """Test that VisionAdapter consumes a fake source without knowing it's not a file."""
    adapter = VisionAdapter(
        model_path="tests/data/fake_model.pt", 
        config_path="vision/config.json"
    )
    
    # Mock the detector to avoid loading real YOLO in tests
    class MockDetector:
        def detect(self, frame, conf_threshold=None, use_tracking=False, conf=None, imgsz=None):
            return []
        def reset_tracking(self):
            pass
            
    adapter.detector = MockDetector()
    
    source = FakeSource(frame_count=10)
    
    # process_every_n_frames=5 means we should yield 2 states for 10 frames
    states = list(adapter.process_source(source, process_every_n_frames=5, use_tracking=False))
    
    assert len(states) == 2
    assert isinstance(states[0], TrafficState)
    assert source.released


def test_vision_adapter_handles_source_error():
    """Test that VisionAdapter ensures source is released even on exception."""
    adapter = VisionAdapter(
        model_path="tests/data/fake_model.pt", 
        config_path="vision/config.json"
    )
    
    # Just assign a MockDetector directly so process_source skips YOLO loading
    class MockDetector:
        def detect(self, frame, conf_threshold=None, use_tracking=False, conf=None, imgsz=None):
            return []
        def reset_tracking(self):
            pass
            
    adapter.detector = MockDetector()
    source = ErrorSource()
    
    with pytest.raises(RuntimeError, match="Mock hardware failure"):
        list(adapter.process_source(source, process_every_n_frames=5, use_tracking=False))
        
    assert source.released
