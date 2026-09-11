import pytest
import numpy as np
from vision.detector import VehicleDetector

@pytest.fixture
def real_detector(tmp_path):
    import json
    config_file = tmp_path / "config.json"
    config = {
        "classes_to_detect": ["car", "bus", "person", "ambulance"],
        "emergency_classes": ["ambulance"]
    }
    with open(config_file, "w") as f:
        json.dump(config, f)
        
    return VehicleDetector("yolov8n.pt", str(config_file))

def test_tracker_stream_isolation(real_detector):
    # Stream A begins
    # We use a blank frame to initialize the predictor and tracker
    frame = np.zeros((640, 640, 3), dtype=np.uint8)
    
    # Run once to initialize the predictor and tracker
    real_detector.detect(frame, use_tracking=True)
    
    assert hasattr(real_detector.model, "predictor")
    assert hasattr(real_detector.model.predictor, "trackers")
    
    tracker = real_detector.model.predictor.trackers[0]
    
    # Force some state into the tracker to simulate active tracks
    # We manually add mock tracks to its internal state
    class MockTrack:
        def __init__(self, track_id):
            self.track_id = track_id
            
    tracker.tracked_stracks = [MockTrack(1), MockTrack(2)]
    
    assert len(tracker.tracked_stracks) == 2
    
    # Stream A ends, Stream B begins
    real_detector.reset_tracking()
    
    # If reset worked, the tracker's internal state (tracked_stracks, etc) should be cleared.
    # Note: We do NOT assert that the next ID is 1, just that state doesn't leak.
    assert len(tracker.tracked_stracks) == 0
