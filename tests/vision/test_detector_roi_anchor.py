import pytest
import os
import json
from unittest.mock import patch, MagicMock
from vision.detector import VehicleDetector
from vision.roi import ROIManager

@pytest.fixture
def mock_config(tmp_path):
    config_data = {
        "classes_to_detect": ["car"],
        "roi_anchor": "CENTER",
        "topology": {
            "approach_count": 4,
            "approaches": ["north", "south", "east", "west"]
        },
        "camera_resolution": [1280, 720],
        "lanes": {
            "north": {"capacity": 10, "polygon": [[500, 0], [780, 0], [780, 270], [500, 270]]},
            "south": {"capacity": 10, "polygon": [[500, 450], [780, 450], [780, 720], [500, 720]]},
            "east": {"capacity": 10, "polygon": [[780, 270], [1280, 270], [1280, 450], [780, 450]]},
            "west": {"capacity": 10, "polygon": [[0, 270], [500, 270], [500, 450], [0, 450]]}
        }
    }
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config_data))
    return str(config_path)

@pytest.fixture
def mock_yolo_model():
    with patch("vision.detector.YOLO") as mock_yolo:
        mock_model = MagicMock()
        mock_model.names = {0: "car", 1: "truck"}
        mock_yolo.return_value = mock_model
        
        # Mock prediction results
        mock_box = MagicMock()
        mock_box.cls = [MagicMock(item=lambda: 0)]
        mock_box.conf = [MagicMock(item=lambda: 0.9)]
        mock_xyxy = MagicMock()
        mock_xyxy.tolist.return_value = [100.0, 100.0, 200.0, 200.0]
        mock_box.xyxy = [mock_xyxy]
        mock_box.id = [MagicMock(item=lambda: 1)]
        
        mock_result = MagicMock()
        mock_result.boxes = [mock_box]
        
        mock_model.track.return_value = [mock_result]
        mock_model.predict.return_value = [mock_result]
        yield mock_model

def test_center_anchor(mock_config, mock_yolo_model):
    detector = VehicleDetector("dummy.pt", mock_config)
    detections = detector.detect(None, use_tracking=False)
    
    assert len(detections) == 1
    # Bbox is [100, 100, 200, 200], so center should be (150, 150)
    assert detections[0]["center"] == (150, 150)

def test_bottom_center_anchor(tmp_path, mock_yolo_model):
    config_data = {
        "classes_to_detect": ["car"],
        "roi_anchor": "BOTTOM_CENTER"
    }
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config_data))
    
    detector = VehicleDetector("dummy.pt", str(config_path))
    detections = detector.detect(None, use_tracking=False)
    
    assert len(detections) == 1
    # Bbox is [100, 100, 200, 200], so bottom-center should be (150, 200)
    assert detections[0]["center"] == (150, 200)

def test_default_behavior(tmp_path, mock_yolo_model):
    # Without roi_anchor specified
    config_data = {
        "classes_to_detect": ["car"]
    }
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config_data))
    
    detector = VehicleDetector("dummy.pt", str(config_path))
    detections = detector.detect(None, use_tracking=False)
    
    # Should default to BOTTOM_CENTER
    assert detections[0]["center"] == (150, 200)

def test_roi_assignment_center_intersection(mock_config):
    # Car in the center of the intersection
    roi_manager = ROIManager(mock_config)
    lane = roi_manager.get_lane_for_point(640, 360, 1280, 720)
    assert lane is None

def test_roi_assignment_north(mock_config):
    roi_manager = ROIManager(mock_config)
    lane = roi_manager.get_lane_for_point(640, 100, 1280, 720)
    assert lane == "north"

def test_roi_assignment_south(mock_config):
    roi_manager = ROIManager(mock_config)
    lane = roi_manager.get_lane_for_point(640, 600, 1280, 720)
    assert lane == "south"

def test_roi_assignment_east(mock_config):
    roi_manager = ROIManager(mock_config)
    lane = roi_manager.get_lane_for_point(1000, 360, 1280, 720)
    assert lane == "east"

def test_roi_assignment_west(mock_config):
    roi_manager = ROIManager(mock_config)
    lane = roi_manager.get_lane_for_point(200, 360, 1280, 720)
    assert lane == "west"

def test_roi_assignment_aspect_ratio_rejection(mock_config):
    roi_manager = ROIManager(mock_config)
    # A totally different aspect ratio (100x100 = 1.0 vs 1280x720 = 1.77)
    lane = roi_manager.get_lane_for_point(50, 50, 100, 100)
    assert lane is None
