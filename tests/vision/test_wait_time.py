import pytest
import time
from unittest.mock import MagicMock, patch

from vision.adapter import VisionAdapter
from models import TrafficState, Lane
from vision.tracker import Track, MovementState

class MockTrackManager:
    def __init__(self, tracks_dict=None):
        self.tracks = tracks_dict if tracks_dict else {}
        self.update_count = 0
        
    def update(self, *args, **kwargs):
        self.update_count += 1

class MockDetector:
    def __init__(self):
        self.detections = []
    def detect(self, frame, use_tracking=False):
        return self.detections
    def reset_tracking(self):
        pass

@pytest.fixture
def mock_adapter(tmp_path):
    import json
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({
        "lanes": {
            "north": {"capacity": 10, "polygon": [[0,0],[10,0],[10,10],[0,10]]},
            "south": {"capacity": 10, "polygon": [[0,0],[10,0],[10,10],[0,10]]},
            "east": {"capacity": 10, "polygon": [[0,0],[10,0],[10,10],[0,10]]},
            "west": {"capacity": 10, "polygon": [[0,0],[10,0],[10,10],[0,10]]}
        },
        "classes_to_detect": ["car"]
    }))
    adapter = VisionAdapter(str(cfg), "dummy.pt")
    adapter.detector = MockDetector()
    return adapter

def create_track(track_id, approach, state, queued_at=None):
    t = Track(track_id, "car", approach, 5.0, 5.0, time.time(), 0, 30)
    t.current_approach = approach
    t.movement_state = state
    t.queued_at = queued_at
    return t

def test_wait_time_calculations(mock_adapter):
    """Test wait time scenarios A through H, and K."""
    now = time.time()
    
    # Track 1: QUEUED, north, wait=10
    t1 = create_track(1, "north", MovementState.QUEUED, queued_at=now - 10)
    # Track 2: QUEUED, north, wait=20
    t2 = create_track(2, "north", MovementState.QUEUED, queued_at=now - 20)
    # Track 3: QUEUED, north, queued_at=None (Scenario E: no wait contributed)
    t3 = create_track(3, "north", MovementState.QUEUED, queued_at=None)
    # Track 4: MOVING, north (Scenario D: no wait contributed)
    t4 = create_track(4, "north", MovementState.MOVING, queued_at=now - 30)
    # Track 5: APPROACHING, north (Scenario C: no wait contributed)
    t5 = create_track(5, "north", MovementState.APPROACHING, queued_at=now - 40)
    
    # Track 6: QUEUED, south, negative wait (anomaly, Scenario K)
    t6 = create_track(6, "south", MovementState.QUEUED, queued_at=now + 50)
    
    # Track 7: QUEUED, south, newly queued (Scenario H)
    t7 = create_track(7, "south", MovementState.QUEUED, queued_at=now)
    
    tracks = {
        1: t1, 2: t2, 3: t3, 4: t4, 5: t5, 6: t6, 7: t7
    }
    
    tm = MockTrackManager(tracks)
    
    with patch('vision.adapter.TrackManager', return_value=tm), \
         patch('vision.adapter.VideoProcessor') as MockVP, \
         patch('vision.adapter.time.time', return_value=now):
        
        instance = MockVP.return_value
        instance.read_frame.side_effect = [(True, "frame"), (False, None)]
        
        gen = mock_adapter.process_video("0", None, use_tracking=True)
        states = list(gen)
        
        state = states[0]
        
        # North lane checks
        north = state.lanes[Lane.NORTH]
        assert north.queued_vehicle_count == 3  # t1, t2, t3
        assert north.moving_vehicle_count == 1  # t4
        assert north.observed_average_wait == 15.0  # (10 + 20) / 2 (t1, t2)
        assert north.observed_max_wait == 20.0
        
        # South lane checks
        south = state.lanes[Lane.SOUTH]
        assert south.queued_vehicle_count == 2 # t6, t7
        assert south.observed_average_wait == 0.0 # t6 is clamped to 0, t7 is 0
        assert south.observed_max_wait == 0.0
        
def test_wait_time_no_tracking(mock_adapter):
    """Scenario I: Tracking-disabled path does not fabricate observed wait."""
    
    with patch('vision.adapter.VideoProcessor') as MockVP:
        instance = MockVP.return_value
        instance.read_frame.side_effect = [(True, "frame"), (False, None)]
        
        gen = mock_adapter.process_video("0", None, use_tracking=False, process_every_n_frames=1)
        states = list(gen)
        
        state = states[0]
        assert state.has_tracking_data is False
        
        north = state.lanes[Lane.NORTH]
        assert north.queued_vehicle_count == 0
        assert north.moving_vehicle_count == 0
        assert north.observed_average_wait == 0.0
        assert north.observed_max_wait == 0.0
