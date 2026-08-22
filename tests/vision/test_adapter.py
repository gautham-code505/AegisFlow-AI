import pytest
from unittest.mock import MagicMock, patch
from vision.adapter import VisionAdapter
from models import TrafficState, Lane, EmergencyState

# Create a mock for the VehicleDetector
class MockVehicleDetector:
    def __init__(self, *args, **kwargs):
        self.detections = []
        
    def detect(self, frame):
        return self.detections

@pytest.fixture
def mock_vision_adapter(tmp_path):
    # Use a dummy config 
    config_file = tmp_path / "config.json"
    import json
    config = {
        "camera_resolution": [640, 480],
        "lanes": {
            "north": {
                "capacity": 10,
                "polygon": [[0, 0], [100, 0], [100, 100], [0, 100]]
            },
            "south": {
                "capacity": 10,
                "polygon": [[100, 100], [200, 100], [200, 200], [100, 200]]
            },
            "east": {
                "capacity": 10,
                "polygon": [[200, 0], [300, 0], [300, 100], [200, 100]]
            },
            "west": {
                "capacity": 10,
                "polygon": [[0, 100], [100, 100], [100, 200], [0, 200]]
            }
        },
        "vehicle_weights": {
            "car": 1.0,
            "bus": 2.5,
            "person": 0.2
        },
        "classes_to_detect": ["car", "bus", "person"]
    }
    with open(config_file, "w") as f:
        json.dump(config, f)
        
    adapter = VisionAdapter(config_path=str(config_file), model_path="dummy.pt")
    # Inject mock detector to avoid YOLO loading
    adapter.detector = MockVehicleDetector()
    return adapter


def test_vision_adapter_rejects_unsupported_topology(tmp_path):
    """A 6/8-way config must not be silently treated as the four-way model."""
    import json

    config_file = tmp_path / "six_way.json"
    config_file.write_text(json.dumps({
        "topology": {"approaches": ["north", "south", "east", "west", "northeast", "southwest"]},
        "lanes": {},
    }))

    with pytest.raises(ValueError, match="Unsupported intersection topology"):
        VisionAdapter(config_path=str(config_file), model_path="dummy.pt")

def test_vision_adapter_detection_conversion(mock_vision_adapter):
    # Set up some dummy detections
    mock_vision_adapter.detector.detections = [
        # Inside north ROI
        {"class": "car", "confidence": 0.9, "bbox": [10, 10, 20, 20], "center": (15, 20)},
        {"class": "bus", "confidence": 0.8, "bbox": [30, 30, 50, 50], "center": (40, 50)},
        {"class": "person", "confidence": 0.95, "bbox": [60, 60, 70, 70], "center": (65, 70)},
        
        # Inside south ROI
        {"class": "car", "confidence": 0.85, "bbox": [110, 110, 120, 120], "center": (115, 120)},
        
        # Outside ROIs
        {"class": "car", "confidence": 0.9, "bbox": [300, 300, 310, 310], "center": (305, 310)}
    ]
    
    # Mock video processor to just run 1 frame and exit
    with patch("vision.adapter.VideoProcessor") as mock_vp:
        instance = mock_vp.return_value
        instance.fps = 30
        instance.read_frame.side_effect = [(True, None), (False, None)]
        
        generator = mock_vision_adapter.process_video("in.mp4", "out.mp4", process_every_n_frames=1)
        states = list(generator)
        
        assert len(states) == 1
        state = states[0]
        
        assert isinstance(state, TrafficState)
        assert state.source == "vision"
        
        # Check NORTH lane (1 car, 1 bus, 1 person)
        north_state = state.lanes[Lane.NORTH]
        # car(1) + bus(1) = 2 vehicles
        assert north_state.vehicle_count == 2
        # bus(1) = 1 heavy vehicle
        assert north_state.heavy_vehicle_count == 1
        # person(1) = 1 pedestrian
        assert north_state.pedestrian_count == 1
        # Occupancy: (1.0 + 2.5 + 0.2) / 10 = 3.7 / 10 = 0.37
        assert north_state.occupancy == 0.37
        
        # Check SOUTH lane (1 car)
        south_state = state.lanes[Lane.SOUTH]
        assert south_state.vehicle_count == 1
        assert south_state.heavy_vehicle_count == 0
        assert south_state.pedestrian_count == 0
        # Occupancy: 1.0 / 10 = 0.1
        assert south_state.occupancy == 0.1
        
        # Check EAST/WEST lanes (empty, outside ROIs ignored)
        assert state.lanes[Lane.EAST].vehicle_count == 0
        assert state.lanes[Lane.WEST].vehicle_count == 0
        
        # Emergency detection should be false
        assert not state.emergency.detected

def test_occupancy_bounded(mock_vision_adapter):
    # Set up detections that exceed capacity
    detections = []
    for i in range(15): # 15 cars in north, capacity is 10
        detections.append({"class": "car", "confidence": 0.9, "bbox": [10, 10, 20, 20], "center": (15, 20)})
    mock_vision_adapter.detector.detections = detections
    
    with patch("vision.adapter.VideoProcessor") as mock_vp:
        instance = mock_vp.return_value
        instance.fps = 30
        instance.read_frame.side_effect = [(True, None), (False, None)]
        

def test_vision_adapter_detection_conversion(mock_vision_adapter):
    # Set up some dummy detections
    mock_vision_adapter.detector.detections = [
        # Inside north ROI
        {"class": "car", "confidence": 0.9, "bbox": [10, 10, 20, 20], "center": (15, 20)},
        {"class": "bus", "confidence": 0.8, "bbox": [30, 30, 50, 50], "center": (40, 50)},
        {"class": "person", "confidence": 0.95, "bbox": [60, 60, 70, 70], "center": (65, 70)},
        
        # Inside south ROI
        {"class": "car", "confidence": 0.85, "bbox": [110, 110, 120, 120], "center": (115, 120)},
        
        # Outside ROIs
        {"class": "car", "confidence": 0.9, "bbox": [300, 300, 310, 310], "center": (305, 310)}
    ]
    
    # Mock video processor to just run 1 frame and exit
    with patch("vision.adapter.VideoProcessor") as mock_vp:
        instance = mock_vp.return_value
        instance.fps = 30
        instance.read_frame.side_effect = [(True, None), (False, None)]
        
        generator = mock_vision_adapter.process_video("in.mp4", "out.mp4", process_every_n_frames=1)
        states = list(generator)
        
        assert len(states) == 1
        state = states[0]
        
        assert isinstance(state, TrafficState)
        assert state.source == "vision"
        
        # Check NORTH lane (1 car, 1 bus, 1 person)
        north_state = state.lanes[Lane.NORTH]
        # car(1) + bus(1) = 2 vehicles
        assert north_state.vehicle_count == 2
        # bus(1) = 1 heavy vehicle
        assert north_state.heavy_vehicle_count == 1
        # person(1) = 1 pedestrian
        assert north_state.pedestrian_count == 1
        # Occupancy: (1.0 + 2.5 + 0.2) / 10 = 3.7 / 10 = 0.37
        assert north_state.occupancy == 0.37
        
        # Check SOUTH lane (1 car)
        south_state = state.lanes[Lane.SOUTH]
        assert south_state.vehicle_count == 1
        assert south_state.heavy_vehicle_count == 0
        assert south_state.pedestrian_count == 0
        # Occupancy: 1.0 / 10 = 0.1
        assert south_state.occupancy == 0.1
        
        # Check EAST/WEST lanes (empty, outside ROIs ignored)
        assert state.lanes[Lane.EAST].vehicle_count == 0
        assert state.lanes[Lane.WEST].vehicle_count == 0
        
        # Emergency detection should be false
        assert not state.emergency.detected

def test_occupancy_bounded(mock_vision_adapter):
    # Set up detections that exceed capacity
    detections = []
    for i in range(15): # 15 cars in north, capacity is 10
        detections.append({"class": "car", "confidence": 0.9, "bbox": [10, 10, 20, 20], "center": (15, 20)})
    mock_vision_adapter.detector.detections = detections
    
    with patch("vision.adapter.VideoProcessor") as mock_vp:
        instance = mock_vp.return_value
        instance.fps = 30
        instance.read_frame.side_effect = [(True, None), (False, None)]
        
        generator = mock_vision_adapter.process_video("in.mp4", "out.mp4", process_every_n_frames=1)
        states = list(generator)
        
        state = states[0]
        north_state = state.lanes[Lane.NORTH]
        
        assert north_state.vehicle_count == 15
        # Occupancy should be clamped to 1.0 in occ_calc.calculate_occupancy
        assert north_state.occupancy == 1.0

def test_vision_adapter_process_image(mock_vision_adapter, tmp_path):
    import cv2
    import numpy as np
    
    # Create a dummy image
    dummy_image_path = str(tmp_path / "dummy.jpg")
    dummy_output_path = str(tmp_path / "output.jpg")
    dummy_img = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.imwrite(dummy_image_path, dummy_img)
    
    mock_vision_adapter.detector.detections = [
        # Inside north ROI
        {"class": "car", "confidence": 0.9, "bbox": [10, 10, 20, 20], "center": (15, 20)},
        {"class": "bus", "confidence": 0.8, "bbox": [30, 30, 50, 50], "center": (40, 50)},
    ]
    
    # Mock video processor drawing methods used in process_image
    with patch("vision.adapter.cv2.imread", return_value=dummy_img), \
         patch("vision.adapter.cv2.imwrite") as mock_imwrite:
         
        state = mock_vision_adapter.process_image(dummy_image_path, dummy_output_path)
        
        assert isinstance(state, TrafficState)
        assert state.source == "vision"
        
        # Check NORTH lane
        north_state = state.lanes[Lane.NORTH]
        assert north_state.vehicle_count == 2
        assert north_state.heavy_vehicle_count == 1
        
        mock_imwrite.assert_called_once()
        assert mock_imwrite.call_args[0][0] == dummy_output_path
