import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from vision.detector import VehicleDetector

class MockBox:
    def __init__(self, cls, conf, xyxy, id_val=None):
        self.cls = [MagicMock(item=lambda: cls)]
        self.conf = [MagicMock(item=lambda: conf)]
        self.xyxy = [MagicMock(tolist=lambda: xyxy)]
        self.id = [MagicMock(item=lambda: id_val)] if id_val is not None else None

class MockResult:
    def __init__(self, boxes_data):
        self.boxes = [MockBox(*b) for b in boxes_data]

class MockModel:
    def __init__(self):
        self.names = {0: 'car', 1: 'person', 2: 'bus', 3: 'ambulance'}
        
    def predict(self, frame, classes=None, verbose=False):
        # Return standard detections
        return [MockResult([
            (0, 0.9, [10, 10, 50, 50]), # car
            (2, 0.8, [100, 100, 150, 150]) # bus
        ])]
        
    def track(self, frame, classes=None, verbose=False, persist=True, tracker="bytetrack.yaml"):
        # Return detections with IDs
        return [MockResult([
            (0, 0.9, [10, 10, 50, 50], 42), # car with id 42
            (2, 0.8, [100, 100, 150, 150], 43) # bus with id 43
        ])]

@pytest.fixture
def detector(tmp_path):
    import json
    config_file = tmp_path / "config.json"
    config = {
        "classes_to_detect": ["car", "bus", "person", "ambulance"],
        "emergency_classes": ["ambulance"]
    }
    with open(config_file, "w") as f:
        json.dump(config, f)
        
    with patch("vision.detector.YOLO", return_value=MockModel()):
        return VehicleDetector("dummy.pt", str(config_file))


def test_detector_normal_prediction(detector):
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    detections = detector.detect(frame, use_tracking=False)
    
    assert len(detections) == 2
    
    # Check first detection
    assert detections[0]["class"] == "car"
    assert detections[0]["confidence"] == 0.9
    assert detections[0]["bbox"] == [10, 10, 50, 50]
    assert detections[0]["center"] == (30, 50)
    assert not detections[0]["is_emergency"]
    assert detections[0]["track_id"] is None
    
def test_detector_tracking(detector):
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    detections = detector.detect(frame, use_tracking=True)
    
    assert len(detections) == 2
    
    # Check first detection
    assert detections[0]["class"] == "car"
    assert detections[0]["confidence"] == 0.9
    assert detections[0]["bbox"] == [10, 10, 50, 50]
    assert detections[0]["center"] == (30, 50)
    assert not detections[0]["is_emergency"]
    assert detections[0]["track_id"] == 42
    
    # Check second detection
    assert detections[1]["class"] == "bus"
    assert detections[1]["track_id"] == 43
