import pytest
from vision.tracker import TrackManager, Track, MovementState

@pytest.fixture
def manager(tmp_path):
    import json
    config_file = tmp_path / "config.json"
    config = {
        "tracking": {
            "timeout_seconds": 2.0,
            "stationary_pixel_threshold": 5.0,
            "history_window_frames": 5,
            "approach_debounce_frames": 3,
            "stationary_debounce_frames": 3,
            "moving_debounce_frames": 3
        }
    }
    with open(config_file, "w") as f:
        json.dump(config, f)
    
    return TrackManager(str(config_file))

def test_track_creation(manager):
    detections = [{"track_id": 1, "class": "car", "center": (100, 100)}]
    lane_assignments = ["north"]
    
    tracks = manager.update(detections, lane_assignments, timestamp=1.0, frame_id=1)
    
    assert len(tracks) == 1
    assert tracks[0].track_id == 1
    assert tracks[0].class_name == "car"
    assert tracks[0].initial_approach == "north"
    assert tracks[0].current_approach == "north"
    assert tracks[0].movement_state == MovementState.APPROACHING
    assert tracks[0].first_seen_at == 1.0
    assert len(tracks[0].position_history) == 1
    assert tracks[0].position_history[0] == (100, 100, 1.0, 1)

def test_track_update(manager):
    # Frame 1: Create
    manager.update([{"track_id": 1, "class": "car", "center": (100, 100)}], ["north"], 1.0, 1)
    
    # Frame 2: Update position
    tracks = manager.update([{"track_id": 1, "class": "car", "center": (102, 105)}], ["north"], 1.1, 2)
    
    assert len(tracks) == 1
    assert tracks[0].last_seen_at == 1.1
    assert len(tracks[0].position_history) == 2
    assert tracks[0].position_history[-1] == (102, 105, 1.1, 2)

def test_missing_track_id_handling(manager):
    # Missing track_id should simply be ignored
    detections = [{"class": "car", "center": (100, 100)}]
    lane_assignments = ["north"]
    
    tracks = manager.update(detections, lane_assignments, timestamp=1.0, frame_id=1)
    
    assert len(tracks) == 0
    assert len(manager.tracks) == 0

def test_approaching_to_queued(manager):
    manager.update([{"track_id": 1, "class": "car", "center": (100, 100)}], ["north"], 1.0, 1)
    track = manager.tracks[1]
    assert track.movement_state == MovementState.APPROACHING
    
    # Very small movement, displacement = sqrt(2^2 + 2^2) = 2.82 < 5.0
    manager.update([{"track_id": 1, "class": "car", "center": (102, 102)}], ["north"], 1.1, 2)
    
    assert track.movement_state == MovementState.QUEUED

def test_queued_to_moving(manager):
    # First get to queued state
    manager.update([{"track_id": 1, "class": "car", "center": (100, 100)}], ["north"], 1.0, 1)
    manager.update([{"track_id": 1, "class": "car", "center": (102, 102)}], ["north"], 1.1, 2)
    assert manager.tracks[1].movement_state == MovementState.QUEUED
    
    # Now large movement, displacement > 5.0
    manager.update([{"track_id": 1, "class": "car", "center": (110, 110)}], ["north"], 1.2, 3)
    # Debounce is 3, so after 1st moving frame it's still QUEUED
    assert manager.tracks[1].movement_state == MovementState.QUEUED
    
    manager.update([{"track_id": 1, "class": "car", "center": (120, 120)}], ["north"], 1.3, 4)
    assert manager.tracks[1].movement_state == MovementState.QUEUED
    
    manager.update([{"track_id": 1, "class": "car", "center": (130, 130)}], ["north"], 1.4, 5)
    assert manager.tracks[1].movement_state == MovementState.MOVING

def test_multiple_simultaneous_tracks(manager):
    detections = [
        {"track_id": 1, "class": "car", "center": (100, 100)},
        {"track_id": 2, "class": "bus", "center": (200, 200)}
    ]
    lane_assignments = ["north", "south"]
    
    tracks = manager.update(detections, lane_assignments, timestamp=1.0, frame_id=1)
    assert len(tracks) == 2
    
    assert manager.tracks[1].class_name == "car"
    assert manager.tracks[2].class_name == "bus"

def test_timeout_cleanup(manager):
    # Create track at t=1.0
    manager.update([{"track_id": 1, "class": "car", "center": (100, 100)}], ["north"], 1.0, 1)
    assert len(manager.tracks) == 1
    
    # Update with nothing at t=2.0 (timeout is 2.0, last seen was 1.0, diff = 1.0 < 2.0) -> keeps track
    manager.update([], [], 2.0, 2)
    assert len(manager.tracks) == 1
    
    # Update with nothing at t=3.1 (diff = 2.1 > 2.0) -> removes track
    manager.update([], [], 3.1, 3)
    assert len(manager.tracks) == 0

def test_bounded_history(manager):
    manager.update([{"track_id": 1, "class": "car", "center": (100, 100)}], ["north"], 1.0, 1)
    
    # History size is configured to 5. Update 10 times.
    for i in range(2, 12):
        manager.update([{"track_id": 1, "class": "car", "center": (100 + i, 100 + i)}], ["north"], 1.0 + i*0.1, i)
        
    track = manager.tracks[1]
    assert len(track.position_history) == 5
    # The oldest element should be from frame 7
    assert track.position_history[0][3] == 7
    # The newest element should be from frame 11
    assert track.position_history[-1][3] == 11

def test_queued_at_lifecycle(manager):
    # 1. new track starts with queued_at = None
    manager.update([{"track_id": 1, "class": "car", "center": (100, 100)}], ["north"], 1.0, 1)
    track = manager.tracks[1]
    assert track.movement_state == MovementState.APPROACHING
    assert track.queued_at is None

    # 2. APPROACHING -> QUEUED sets queued_at
    # Small movement, displacement < 5.0
    manager.update([{"track_id": 1, "class": "car", "center": (102, 102)}], ["north"], 2.0, 2)
    assert track.movement_state == MovementState.QUEUED
    assert track.queued_at == 2.0

    # 3. repeated QUEUED updates preserve the original queued_at
    manager.update([{"track_id": 1, "class": "car", "center": (102, 102)}], ["north"], 3.0, 3)
    assert track.movement_state == MovementState.QUEUED
    assert track.queued_at == 2.0

    # 4. QUEUED -> MOVING clears queued_at
    # Requires 3 consecutive moving frames due to hysteresis
    manager.update([{"track_id": 1, "class": "car", "center": (110, 110)}], ["north"], 4.0, 4)
    manager.update([{"track_id": 1, "class": "car", "center": (120, 120)}], ["north"], 5.0, 5)
    manager.update([{"track_id": 1, "class": "car", "center": (130, 130)}], ["north"], 6.0, 6)
    assert track.movement_state == MovementState.MOVING
    assert track.queued_at is None

    # 5. unrelated movement-state transitions do not corrupt queued_at
    # Moving -> Moving
    manager.update([{"track_id": 1, "class": "car", "center": (140, 140)}], ["north"], 7.0, 7)
    assert track.movement_state == MovementState.MOVING
    assert track.queued_at is None

    # 6. MOVING -> QUEUED creates a new queued_at
    # We must flush the old position_history (size 5) to trigger stationary
    for i in range(8, 14):
        manager.update([{"track_id": 1, "class": "car", "center": (140, 140)}], ["north"], float(i), i)
    assert track.movement_state == MovementState.QUEUED
    assert track.queued_at == 13.0

def test_sticky_approach_assignment(manager):
    # Track starts in north
    manager.update([{"track_id": 1, "class": "car", "center": (100, 100)}], ["north"], 1.0, 1)
    track = manager.tracks[1]
    assert track.current_approach == "north"
    assert track.initial_approach == "north"
    
    # 1 jitter frame to south
    manager.update([{"track_id": 1, "class": "car", "center": (100, 100)}], ["south"], 2.0, 2)
    assert track.current_approach == "north" # hasn't changed yet
    assert track.candidate_approach == "south"
    assert track.candidate_approach_count == 1
    
    # Back to north (jitter ends)
    manager.update([{"track_id": 1, "class": "car", "center": (100, 100)}], ["north"], 3.0, 3)
    assert track.current_approach == "north"
    assert track.candidate_approach_count == 0
    
    # 3 consecutive south observations should trigger change
    manager.update([{"track_id": 1, "class": "car", "center": (100, 100)}], ["south"], 4.0, 4)
    manager.update([{"track_id": 1, "class": "car", "center": (100, 100)}], ["south"], 5.0, 5)
    manager.update([{"track_id": 1, "class": "car", "center": (100, 100)}], ["south"], 6.0, 6)
    
    assert track.current_approach == "south"
    assert track.initial_approach == "north" # MUST remain unchanged

