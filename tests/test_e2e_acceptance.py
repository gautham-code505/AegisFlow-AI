import pytest
import time
from unittest.mock import patch
import numpy as np

from vision.adapter import VisionAdapter
from decision_engine.engine import DecisionEngine
from decision_engine.config import DecisionEngineConfig
from models import TrafficState, Lane, SignalDecision

class MockVehicleDetector:
    def __init__(self, *args, **kwargs):
        self.detections = []
        
    def detect(self, frame):
        return self.detections

def test_yolo_to_decision_e2e(tmp_path):
    """
    Acceptance test demonstrating the logic flow:
    IMAGE -> YOLO -> Tracked Objects: > 0 
    -> North, South, East, West actual vehicles 
    -> Occupancy calculated 
    -> Decision Engine -> EAST - 17 sec 
    -> Reason: Highest occupancy, Highest vehicle count, Highest priority score.
    """
    # 1. Setup Vision Adapter with mocked YOLO detector
    # We use a dummy model path as it's mocked
    adapter = VisionAdapter(config_path="vision/config.json", model_path="dummy.pt")
    adapter.detector = MockVehicleDetector()
    
    # 2. Setup Detections for North, South, East, West
    # We need EAST to have the highest occupancy and vehicle count resulting in exactly 17 seconds.
    # 17s duration calculation: 17 = 10 + 35 * demand_factor => demand_factor = 0.2
    # demand_factor = (occupancy + norm_vehicles)/2 => 0.4
    # For exactly 3 cars in East: occupancy=0.3, norm_vehicles=3/30=0.1 => sum=0.4 => 17s!
    
    adapter.detector.detections = [
        # North (1 car, center ~50,50)
        {"class": "car", "confidence": 0.9, "bbox": [10, 10, 20, 20], "center": (320, 90)}, # inside North poly [250,0]-[390,180]
        # South (1 car, center ~150,150)
        {"class": "car", "confidence": 0.85, "bbox": [110, 110, 120, 120], "center": (320, 390)}, # inside South poly [250,300]-[390,480]
        # West (1 car, center ~50,150)
        {"class": "car", "confidence": 0.9, "bbox": [50, 150, 60, 160], "center": (125, 240)}, # inside West poly [0,180]-[250,300]
        # East (3 cars, center ~250,50)
        {"class": "car", "confidence": 0.95, "bbox": [260, 60, 270, 70], "center": (515, 240)}, # inside East poly [390,180]-[640,300]
        {"class": "car", "confidence": 0.95, "bbox": [270, 60, 280, 70], "center": (525, 240)},
        {"class": "car", "confidence": 0.95, "bbox": [280, 60, 290, 70], "center": (535, 240)},
    ]
    
    # Create dummy image to pass to process_image
    dummy_image_path = str(tmp_path / "dummy.jpg")
    dummy_output_path = str(tmp_path / "output.jpg")
    import cv2
    dummy_img = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.imwrite(dummy_image_path, dummy_img)
    
    # 3. Process Image -> YOLO -> Tracked Objects -> Occupancy Calculated -> TrafficState
    with patch("vision.adapter.cv2.imread", return_value=dummy_img), \
         patch("vision.adapter.cv2.imwrite"):
         
        traffic_state = adapter.process_image(dummy_image_path, dummy_output_path)
    
    # Assert conditions were met
    assert traffic_state.lanes[Lane.NORTH].vehicle_count > 0, "North should have actual vehicles"
    assert traffic_state.lanes[Lane.SOUTH].vehicle_count > 0, "South should have actual vehicles"
    assert traffic_state.lanes[Lane.EAST].vehicle_count > 0, "East should have actual vehicles"
    assert traffic_state.lanes[Lane.WEST].vehicle_count > 0, "West should have actual vehicles"
    
    # Adapter uses Enum for lane keys, DecisionEngine uses strings
    # We must bridge them as done in the actual VirtualController
    state_dict = {
        "timestamp": traffic_state.timestamp,
        "lanes": {
            lane.value: {
                "vehicle_count": lane_state.vehicle_count,
                "occupancy": lane_state.occupancy
            }
            for lane, lane_state in traffic_state.lanes.items()
        },
        "emergency": {
            "detected": traffic_state.emergency.detected,
            "lane": traffic_state.emergency.lane
        }
    }
    
    # 4. Decision Engine
    engine = DecisionEngine(DecisionEngineConfig())
    decision = engine.decide(state_dict)
    
    # 5. Verify Decision
    assert decision.active_lane == "east", f"Expected EAST to be chosen, got {decision.active_lane}"
    assert decision.duration == 17, f"Expected 17 sec duration, got {decision.duration}"
    
    # Reason Validation
    assert any("highest occupancy" in r.lower() for r in decision.reason), "Missing Highest occupancy reason"
    assert any("detected vehicles" in r.lower() for r in decision.reason), "Missing Highest vehicle count reason"
    assert any("highest priority score" in r.lower() for r in decision.reason), "Missing Highest priority score reason"
    
    print("Acceptance Test Flow Verified successfully:")
    print(f"Chosen Lane: {decision.active_lane.upper()}")
    print(f"Duration: {decision.duration} sec")
    print("Reasons:")
    for r in decision.reason:
        print(f"  - {r}")
