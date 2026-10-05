import pytest
import numpy as np
import time
from vision.tracker import TrackManager, MovementState
from vision.roi import ROIManager
from vision.adapter import VisionAdapter
from models import LaneState, TrafficState, Lane as Approach
import numpy as np

def process_test_frame(adapter, frame):
    detections = adapter.detector.detect(frame, use_tracking=True)
    lane_assignments = []
    vehicles_per_lane = {lane: [] for lane in adapter.roi_mgr.lanes.keys()}
    h, w = frame.shape[:2]
    for det in detections:
        cx, cy = det['center']
        cls = det['class']
        lane = adapter.roi_mgr.get_lane_for_point(cx, cy, w, h)
        lane_assignments.append(lane)
        if lane: vehicles_per_lane[lane].append(cls)
    
    frame_id = getattr(adapter, '_test_frame_id', 0) + 1
    adapter._test_frame_id = frame_id
    
    timestamp = time.time()
    adapter.tracker.update(detections, lane_assignments, timestamp, frame_id)
    
    lane_states = {}
    for lane_str, lane_enum in adapter.LANE_MAPPING.items():
        queued_count = sum(1 for t in adapter.tracker.tracks.values() if t.current_approach == lane_str and t.movement_state == MovementState.QUEUED)
        moving_count = sum(1 for t in adapter.tracker.tracks.values() if t.current_approach == lane_str and t.movement_state == MovementState.MOVING)
        waits = [timestamp - t.queued_at for t in adapter.tracker.tracks.values() if t.current_approach == lane_str and t.movement_state == MovementState.QUEUED and t.queued_at]
        waits = [w if w > 0 else 0.0 for w in waits]
        avg_wait = sum(waits)/len(waits) if waits else 0.0
        max_wait = max(waits) if waits else 0.0
        veh_count, heavy_count, ped_count = adapter._classify_detections(vehicles_per_lane.get(lane_str, []))
        
        lane_states[lane_enum] = LaneState(
            vehicle_count=veh_count,
            queued_vehicle_count=queued_count,
            moving_vehicle_count=moving_count,
            observed_average_wait=avg_wait,
            observed_max_wait=max_wait,
            heavy_vehicle_count=heavy_count
        )
        
    return TrafficState(timestamp=timestamp, frame_id=frame_id, source="test", has_tracking_data=True, lanes=lane_states)


class MockDetector:
    def __init__(self):
        self.detections = []
        
    def detect(self, frame, use_tracking=False, conf=None, imgsz=None):
        return self.detections

class MockROI:
    def __init__(self):
        self.lanes = {"north": [], "south": [], "east": [], "west": []}
        self._point_map = {}
        
    def get_lane_for_point(self, x, y, w, h):
        return self._point_map.get((x, y), None)
        
    def get_polygons(self, w, h):
        return {}

@pytest.fixture
def adapter(tmp_path):
    # Instantiate with fakes
    config = {
        "lanes": {
            "north": {"polygon": [[0,0], [1,0], [1,1], [0,1]]},
            "south": {"polygon": [[0,0], [1,0], [1,1], [0,1]]},
            "east": {"polygon": [[0,0], [1,0], [1,1], [0,1]]},
            "west": {"polygon": [[0,0], [1,0], [1,1], [0,1]]}
        }
    }
    fake_config = tmp_path / "fake.json"
    import json
    with open(fake_config, "w") as f:
        json.dump(config, f)
        
    adapter = VisionAdapter(config_path=str(fake_config))
    adapter.detector = MockDetector()
    adapter.roi_mgr = MockROI()
    adapter.tracker = TrackManager(config_path=str(fake_config))
    # Speed up tests by overriding debounce limits
    adapter.tracker.approach_debounce_frames = 2
    adapter.tracker.stationary_debounce_frames = 2
    adapter.tracker.moving_debounce_frames = 2
    adapter.tracker.history_window_frames = 2
    adapter.tracker.timeout_seconds = 0.5
    return adapter

def test_stable_track_identity_and_aggregation(adapter):
    """Test that a vehicle staying in one ROI produces correct aggregation."""
    
    adapter.roi_mgr._point_map[(100, 100)] = "north"
    
    # Frame 1: Vehicle appears in North, moving
    adapter.detector.detections = [{
        "class": "car", "confidence": 0.9, "bbox": [0,0,200,200], "center": (100, 100), 
        "is_emergency": False, "track_id": 1
    }]
    
    # Using a fake frame of zeros just for shape
    fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    
    t1 = time.time()
    state1 = process_test_frame(adapter, fake_frame)
    
    assert state1.lanes[Approach.NORTH].vehicle_count == 1
    assert state1.lanes[Approach.NORTH].queued_vehicle_count == 0
    assert state1.lanes[Approach.NORTH].moving_vehicle_count == 0 # Hasn't hit moving debounce yet (starts APPROACHING)
    
    # Frame 2: Same vehicle, moved slightly (still in North)
    adapter.roi_mgr._point_map[(110, 110)] = "north"
    adapter.detector.detections[0]["center"] = (110, 110)
    
    t2 = t1 + 0.1
    with pytest.MonkeyPatch.context() as m:
        m.setattr(time, "time", lambda: t2)
        state2 = process_test_frame(adapter, fake_frame)
        
    assert state2.lanes[Approach.NORTH].vehicle_count == 1
    assert state2.lanes[Approach.NORTH].moving_vehicle_count == 1
    
    # Frame 3: Same vehicle, stopped
    adapter.detector.detections[0]["center"] = (110, 110)
    
    t3 = t2 + 0.1
    with pytest.MonkeyPatch.context() as m:
        m.setattr(time, "time", lambda: t3)
        state3 = process_test_frame(adapter, fake_frame)
        
    # Frame 4: Still stopped -> becomes QUEUED
    t4 = t3 + 0.1
    with pytest.MonkeyPatch.context() as m:
        m.setattr(time, "time", lambda: t4)
        state4 = process_test_frame(adapter, fake_frame)
        
    assert state4.lanes[Approach.NORTH].queued_vehicle_count == 1
    assert state4.lanes[Approach.NORTH].moving_vehicle_count == 0
    assert state4.lanes[Approach.NORTH].observed_max_wait >= 0.0

def test_boundary_crossing_debounce(adapter):
    """Test crossing from North to None requires debounce to change approach."""
    
    adapter.roi_mgr._point_map[(100, 100)] = "north"
    adapter.roi_mgr._point_map[(200, 200)] = None # Outside ROI
    
    # Frame 1 & 2: Establish in North
    adapter.detector.detections = [{
        "class": "car", "confidence": 0.9, "bbox": [0,0,200,200], "center": (100, 100), 
        "is_emergency": False, "track_id": 1
    }]
    fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    
    process_test_frame(adapter, fake_frame)
    process_test_frame(adapter, fake_frame) # Now firmly North
    
    # Frame 3: Centroid flickers outside ROI
    adapter.detector.detections[0]["center"] = (200, 200)
    state = process_test_frame(adapter, fake_frame)
    
    # Tracker should STILL consider it North due to debounce!
    # Wait, the current adapter logic calculates moving/queued based on tracking, 
    # but instantaneous vehicle_count based on raw ROI.
    # So tracking counts remain in North.
    assert state.lanes[Approach.NORTH].vehicle_count == 0 # Instantaneous drops
    
    # Let's check track directly
    track = adapter.tracker.tracks[1]
    assert track.current_approach == "north" # Still north!
    
    # Frame 4: Second frame outside ROI (hits debounce = 2)
    state2 = process_test_frame(adapter, fake_frame)
    assert adapter.tracker.tracks[1].current_approach is None # Now it has changed

def test_track_disappearance_cleanup(adapter):
    """Test that vanished tracks are cleaned up and queues decrease."""
    adapter.roi_mgr._point_map[(100, 100)] = "north"
    adapter.detector.detections = [{
        "class": "car", "confidence": 0.9, "bbox": [0,0,200,200], "center": (100, 100), 
        "is_emergency": False, "track_id": 1
    }]
    fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    
    process_test_frame(adapter, fake_frame)
    assert 1 in adapter.tracker.tracks
    
    # Vehicle disappears (simulated by empty detections list)
    adapter.detector.detections = []
    
    # Time travels past timeout (0.5s)
    with pytest.MonkeyPatch.context() as m:
        mock_t = time.time() + 1.0
        m.setattr(time, "time", lambda: mock_t)
        state_after = process_test_frame(adapter, fake_frame)
        
    assert 1 not in adapter.tracker.tracks
    assert state_after.lanes[Approach.NORTH].queued_vehicle_count == 0
    assert state_after.lanes[Approach.NORTH].moving_vehicle_count == 0
    assert state_after.lanes[Approach.NORTH].vehicle_count == 0

def test_multi_vehicle_aggregation(adapter):
    """Test multiple vehicles across lanes."""
    adapter.roi_mgr._point_map[(100, 100)] = "north"
    adapter.roi_mgr._point_map[(300, 300)] = "south"
    
    adapter.detector.detections = [
        {"class": "car", "confidence": 0.9, "bbox": [0,0,1,1], "center": (100, 100), "is_emergency": False, "track_id": 1},
        {"class": "bus", "confidence": 0.9, "bbox": [0,0,1,1], "center": (100, 100), "is_emergency": False, "track_id": 2},
        {"class": "car", "confidence": 0.9, "bbox": [0,0,1,1], "center": (300, 300), "is_emergency": False, "track_id": 3}
    ]
    fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    
    state = process_test_frame(adapter, fake_frame)
    
    # 2 vehicles in North (1 car, 1 bus = 1 heavy vehicle)
    assert state.lanes[Approach.NORTH].vehicle_count == 2
    assert state.lanes[Approach.NORTH].heavy_vehicle_count == 1
    
    # 1 vehicle in South
    assert state.lanes[Approach.SOUTH].vehicle_count == 1

def test_legitimate_roi_crossing(adapter):
    """Test N -> E crossing requires consecutive frames to update approach assignment without changing Track ID."""
    adapter.roi_mgr._point_map[(100, 100)] = "north"
    adapter.roi_mgr._point_map[(300, 300)] = "east"
    adapter.tracker.approach_debounce_frames = 3
    
    # Setup initial stable North track
    adapter.detector.detections = [{"class": "car", "confidence": 0.9, "bbox": [0,0,1,1], "center": (100, 100), "is_emergency": False, "track_id": 99}]
    fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    process_test_frame(adapter, fake_frame)
    process_test_frame(adapter, fake_frame)
    process_test_frame(adapter, fake_frame)
    
    track = adapter.tracker.tracks[99]
    assert track.current_approach == "north"
    
    # Begin Crossing
    adapter.detector.detections[0]["center"] = (300, 300)
    
    # Frame 1: Candidate = East, Current = North
    process_test_frame(adapter, fake_frame)
    assert track.current_approach == "north"
    assert track.candidate_approach == "east"
    assert track.candidate_approach_count == 1
    
    # Frame 2: Candidate = East, Current = North
    process_test_frame(adapter, fake_frame)
    assert track.current_approach == "north"
    assert track.candidate_approach_count == 2
    
    # Frame 3: Debounce met. Current = East. Track ID remains identical!
    process_test_frame(adapter, fake_frame)
    assert track.current_approach == "east"
    assert 99 in adapter.tracker.tracks

def test_intermittent_debounce_reset(adapter):
    """Test N -> E -> N -> E does not falsely trigger approach transition."""
    adapter.roi_mgr._point_map[(100, 100)] = "north"
    adapter.roi_mgr._point_map[(300, 300)] = "east"
    adapter.tracker.approach_debounce_frames = 3
    
    adapter.detector.detections = [{"class": "car", "confidence": 0.9, "bbox": [0,0,1,1], "center": (100, 100), "is_emergency": False, "track_id": 77}]
    fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    
    # Establish North
    process_test_frame(adapter, fake_frame)
    process_test_frame(adapter, fake_frame)
    process_test_frame(adapter, fake_frame)
    track = adapter.tracker.tracks[77]
    assert track.current_approach == "north"
    
    # Frame 1: East
    adapter.detector.detections[0]["center"] = (300, 300)
    process_test_frame(adapter, fake_frame)
    assert track.candidate_approach_count == 1
    
    # Frame 2: Back to North (should reset candidate counter)
    adapter.detector.detections[0]["center"] = (100, 100)
    process_test_frame(adapter, fake_frame)
    assert track.candidate_approach_count == 0
    assert track.current_approach == "north"
    
    # Frame 3: East again
    adapter.detector.detections[0]["center"] = (300, 300)
    process_test_frame(adapter, fake_frame)
    assert track.candidate_approach_count == 1
    assert track.current_approach == "north"
