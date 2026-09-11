import pytest
from unittest.mock import MagicMock, patch
from vision.adapter import VisionAdapter
from vision.tracker import MovementState
import time

@pytest.fixture
def adapter(tmp_path):
    import json
    config_file = tmp_path / "config.json"
    config = {
        "camera_resolution": [640, 480],
        "lanes": {
            "north": {"capacity": 10, "polygon": [[0, 0], [100, 0], [100, 100], [0, 100]]},
            "south": {"capacity": 10, "polygon": [[200, 200], [300, 200], [300, 300], [200, 300]]},
            "east": {"capacity": 10, "polygon": [[0, 200], [100, 200], [100, 300], [0, 300]]},
            "west": {"capacity": 10, "polygon": [[200, 0], [300, 0], [300, 100], [200, 100]]}
        },
        "vehicle_weights": {"car": 1.0, "bus": 2.5},
        "tracking": {
            "timeout_seconds": 2.0,
            "stationary_pixel_threshold": 5.0,
            "history_window_frames": 5
        }
    }
    with open(config_file, "w") as f:
        json.dump(config, f)
    
    # Instantiate the adapter but mock out the heavy components
    adapter = VisionAdapter(str(config_file))
    return adapter

@patch("vision.adapter.VideoProcessor")
@patch("vision.adapter.VehicleDetector")
def test_tracking_integration_creates_and_updates_tracks(MockDetector, MockProcessor, adapter):
    mock_vp = MagicMock()
    # Mock read_frame to return 3 frames then stop
    mock_vp.read_frame.side_effect = [
        (True, "frame1"),
        (True, "frame2"),
        (True, "frame3"),
        (True, "frame4"),
        (True, "frame5"),
        (False, None)
    ]
    MockProcessor.return_value = mock_vp
    
    mock_detector = MagicMock()
    # Mock detect to return detections with tracking IDs
    # Frame 1: Create a car in north
    # Frame 2: Small movement (Queued)
    # Frame 3: Large movement (Moving)
    mock_detector.detect.side_effect = [
        [{"track_id": 1, "class": "car", "center": (50, 50), "confidence": 0.9}],
        [{"track_id": 1, "class": "car", "center": (52, 52), "confidence": 0.9}],
        [{"track_id": 1, "class": "car", "center": (60, 60), "confidence": 0.9}],
        [{"track_id": 1, "class": "car", "center": (70, 70), "confidence": 0.9}],
        [{"track_id": 1, "class": "car", "center": (80, 80), "confidence": 0.9}]
    ]
    adapter.detector = mock_detector
    
    # We must patch TrackManager to inspect it, or we can just mock the tracker property/creation.
    # Actually, we can intercept the created TrackManager by patching TrackManager class,
    # or just let it run and patch the update method to capture state.
    # A cleaner way is to mock TrackManager but keep a real one inside the mock to inspect it.
    
    real_tracker = None
    from vision.tracker import TrackManager
    original_init = TrackManager.__init__
    original_update = TrackManager.update
    
    captured_tracks = []
    
    def side_effect_update(self, detections, lane_assignments, timestamp, frame_id):
        nonlocal real_tracker
        real_tracker = self
        tracks = original_update(self, detections, lane_assignments, timestamp, frame_id)
        # Capture the state of tracks at this frame
        captured_tracks.append({t.track_id: t.movement_state for t in tracks})
        return tracks
        
    with patch.object(TrackManager, 'update', side_effect=side_effect_update, autospec=True):
        # Process the video with tracking
        states = list(adapter.process_video("dummy.mp4", "out.mp4", use_tracking=True))
        
        assert len(states) == 5
        assert len(captured_tracks) == 5
        
        # Frame 1: Track created, state should be APPROACHING
        # It's APPROACHING, so queued and moving are 0
        from models import Lane
        assert states[0].lanes[Lane.NORTH].queued_vehicle_count == 0
        assert states[0].lanes[Lane.NORTH].moving_vehicle_count == 0
        assert states[0].lanes[Lane.NORTH].vehicle_count == 1
        
        # Frame 2: Track updated, small movement (2.82 px), state should be QUEUED
        assert states[1].lanes[Lane.NORTH].queued_vehicle_count == 1
        assert states[1].lanes[Lane.NORTH].moving_vehicle_count == 0
        assert states[1].lanes[Lane.NORTH].vehicle_count == 1
        
        # Frame 3: Track updated, large movement, but debounce keeps it QUEUED
        assert states[2].lanes[Lane.NORTH].queued_vehicle_count == 1
        assert states[2].lanes[Lane.NORTH].moving_vehicle_count == 0
        
        # Frame 4: Second moving frame
        assert states[3].lanes[Lane.NORTH].queued_vehicle_count == 1
        assert states[3].lanes[Lane.NORTH].moving_vehicle_count == 0

        # Frame 5: Third moving frame, transitions to MOVING
        assert states[4].lanes[Lane.NORTH].queued_vehicle_count == 0
        assert states[4].lanes[Lane.NORTH].moving_vehicle_count == 1
        assert states[4].lanes[Lane.NORTH].vehicle_count == 1

@patch("vision.adapter.VideoProcessor")
@patch("vision.adapter.VehicleDetector")
def test_tracking_integration_multiple_approaches(MockDetector, MockProcessor, adapter):
    mock_vp = MagicMock()
    mock_vp.read_frame.side_effect = [(True, "frame1"), (False, None)]
    MockProcessor.return_value = mock_vp
    
    mock_detector = MagicMock()
    # Car 1 in north, Car 2 in south
    mock_detector.detect.side_effect = [
        [
            {"track_id": 1, "class": "car", "center": (50, 50), "confidence": 0.9},
            {"track_id": 2, "class": "bus", "center": (250, 250), "confidence": 0.9}
        ]
    ]
    adapter.detector = mock_detector
    
    from vision.tracker import TrackManager
    original_update = TrackManager.update
    
    captured_tracks = []
    
    def side_effect_update(self, detections, lane_assignments, timestamp, frame_id):
        tracks = original_update(self, detections, lane_assignments, timestamp, frame_id)
        captured_tracks.append({t.track_id: t.initial_approach for t in tracks})
        return tracks
        
    with patch.object(TrackManager, 'update', side_effect=side_effect_update, autospec=True):
        list(adapter.process_video("dummy.mp4", "out.mp4", use_tracking=True))
        
        assert len(captured_tracks) == 1
        assert captured_tracks[0][1] == "north"
        assert captured_tracks[0][2] == "south"

@patch("vision.adapter.VideoProcessor")
@patch("vision.adapter.VehicleDetector")
def test_tracking_integration_new_video_resets_state(MockDetector, MockProcessor, adapter):
    # Two videos, each 1 frame
    mock_vp1 = MagicMock()
    mock_vp1.read_frame.side_effect = [(True, "f1"), (False, None)]
    
    mock_vp2 = MagicMock()
    mock_vp2.read_frame.side_effect = [(True, "f1"), (False, None)]
    
    MockProcessor.side_effect = [mock_vp1, mock_vp2]
    
    mock_detector = MagicMock()
    mock_detector.detect.side_effect = [
        [{"track_id": 1, "class": "car", "center": (50, 50), "confidence": 0.9}],
        [{"track_id": 1, "class": "car", "center": (70, 70), "confidence": 0.9}]
    ]
    adapter.detector = mock_detector
    
    from vision.tracker import TrackManager
    
    track_manager_instances = []
    original_init = TrackManager.__init__
    
    def side_effect_init(self, config_path):
        track_manager_instances.append(self)
        original_init(self, config_path)
        
    with patch.object(TrackManager, '__init__', side_effect=side_effect_init, autospec=True):
        list(adapter.process_video("vid1.mp4", "out1.mp4", use_tracking=True))
        list(adapter.process_video("vid2.mp4", "out2.mp4", use_tracking=True))
        
        # Should have instantiated two separate TrackManagers
        assert len(track_manager_instances) == 2
        assert track_manager_instances[0] is not track_manager_instances[1]

@patch("vision.adapter.VideoProcessor")
@patch("vision.adapter.VehicleDetector")
def test_tracking_integration_non_tracking_mode_unchanged(MockDetector, MockProcessor, adapter):
    mock_vp = MagicMock()
    # 6 frames
    mock_vp.read_frame.side_effect = [
        (True, "f1"), (True, "f2"), (True, "f3"), (True, "f4"), (True, "f5"), (True, "f6"), (False, None)
    ]
    MockProcessor.return_value = mock_vp
    
    mock_detector = MagicMock()
    mock_detector.detect.return_value = [{"track_id": 1, "class": "car", "center": (50, 50), "confidence": 0.9}]
    adapter.detector = mock_detector
    
    from vision.tracker import TrackManager
    
    manager_called = False
    def init_mock(self, config_path):
        nonlocal manager_called
        manager_called = True
        
    with patch.object(TrackManager, '__init__', side_effect=init_mock, autospec=True):
        # Process every 2 frames
        states = list(adapter.process_video("vid.mp4", "out.mp4", process_every_n_frames=2, use_tracking=False))
        
        # Out of 6 frames, frames 2, 4, 6 should be processed
        assert len(states) == 3
        assert mock_detector.detect.call_count == 3
        # Should not have created a track manager
        assert not manager_called
        
        # Tracking disabled -> both fields remain 0 despite detections
        from models import Lane
        assert states[0].lanes[Lane.NORTH].queued_vehicle_count == 0
        assert states[0].lanes[Lane.NORTH].moving_vehicle_count == 0
        assert states[0].lanes[Lane.NORTH].vehicle_count == 1 # existing count is unchanged

@patch("vision.adapter.VideoProcessor")
@patch("vision.adapter.VehicleDetector")
def test_tracking_integration_expired_tracks_not_counted(MockDetector, MockProcessor, adapter):
    mock_vp = MagicMock()
    # 2 frames
    mock_vp.read_frame.side_effect = [
        (True, "f1"), (True, "f2"), (False, None)
    ]
    MockProcessor.return_value = mock_vp
    
    mock_detector = MagicMock()
    # Frame 1: detect car (will be Queued by our mock below or just standard update)
    # Frame 2: detect nothing, track should expire
    mock_detector.detect.side_effect = [
        [{"track_id": 1, "class": "car", "center": (50, 50), "confidence": 0.9}],
        []
    ]
    adapter.detector = mock_detector
    
    from vision.tracker import TrackManager
    original_update = TrackManager.update
    
    def side_effect_update(self, detections, lane_assignments, timestamp, frame_id):
        # Make timestamp jump by 3 seconds for frame 2 so track expires
        ts = timestamp if frame_id == 1 else timestamp + 3.0
        return original_update(self, detections, lane_assignments, ts, frame_id)
        
    with patch.object(TrackManager, 'update', side_effect=side_effect_update, autospec=True):
        states = list(adapter.process_video("vid.mp4", "out.mp4", use_tracking=True))
        
        assert len(states) == 2
        
        from models import Lane
        # Frame 2 has no vehicles and track expired
        assert states[1].lanes[Lane.NORTH].queued_vehicle_count == 0
        assert states[1].lanes[Lane.NORTH].moving_vehicle_count == 0
        assert states[1].lanes[Lane.NORTH].vehicle_count == 0
