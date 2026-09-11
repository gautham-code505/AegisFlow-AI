import pytest
import time
import threading
from unittest.mock import patch

from vision.video_processor import VideoProcessor
from vision.adapter import VisionAdapter
from models import TrafficState, Lane


class MockVideoCapture:
    def __init__(self, frames_sequence):
        """
        frames_sequence is a list of tuples (ret, frame, delay)
        """
        self.frames = frames_sequence
        self.index = 0
        self.is_opened = True
        self.lock = threading.Lock()
        
    def isOpened(self):
        return self.is_opened
        
    def read(self):
        with self.lock:
            if self.index < len(self.frames):
                ret, frame, delay = self.frames[self.index]
                self.index += 1
            else:
                return False, None
                
        if delay > 0:
            time.sleep(delay)
        return ret, frame
        
    def release(self):
        self.is_opened = False
        
    def get(self, propId):
        if propId == 3: # CV_CAP_PROP_FRAME_WIDTH
            return 640
        elif propId == 4: # CV_CAP_PROP_FRAME_HEIGHT
            return 480
        elif propId == 5: # CV_CAP_PROP_FPS
            return 30
        return 0


def test_latest_frame_replacement():
    """A. Latest-frame replacement"""
    # sequence: A (0s), B (0s), stop
    seq = [
        (True, "A", 0),
        (True, "B", 0),
        (False, None, 0.5)
    ]
    mock_cap = MockVideoCapture(seq)
    
    with patch('vision.video_processor.cv2.VideoCapture', return_value=mock_cap):
        vp = VideoProcessor("0", output_path=None, is_live=True)
        time.sleep(0.1)
        
        ret, frame = vp.read_frame()
        assert ret is True
        assert frame == "B"
        
        vp.release()


def test_multiple_replacements():
    """B. Multiple replacements"""
    seq = [
        (True, "A", 0),
        (True, "B", 0),
        (True, "C", 0),
        (True, "D", 0),
        (False, None, 0.5)
    ]
    mock_cap = MockVideoCapture(seq)
    
    with patch('vision.video_processor.cv2.VideoCapture', return_value=mock_cap):
        vp = VideoProcessor("0", output_path=None, is_live=True)
        time.sleep(0.1)
        
        ret, frame = vp.read_frame()
        assert ret is True
        assert frame == "D"
        
        vp.release()


def test_no_duplicate_delivery():
    """C. No duplicate delivery"""
    seq = [
        (True, "A", 0),
        (False, None, 1.0)
    ]
    mock_cap = MockVideoCapture(seq)
    
    with patch('vision.video_processor.cv2.VideoCapture', return_value=mock_cap):
        vp = VideoProcessor("0", output_path=None, is_live=True)
        time.sleep(0.1)
        
        ret, frame = vp.read_frame()
        assert ret is True
        assert frame == "A"
        
        ret2, frame2 = vp.read_frame()
        assert ret2 is False
        assert frame2 is None
        
        vp.release()


def test_producer_non_blocking():
    """E. Producer non-blocking behavior"""
    seq = [(True, f"F{i}", 0) for i in range(100)] + [(False, None, 0)]
    mock_cap = MockVideoCapture(seq)
    
    with patch('vision.video_processor.cv2.VideoCapture', return_value=mock_cap):
        vp = VideoProcessor("0", output_path=None, is_live=True)
        time.sleep(0.2)
        
        assert mock_cap.index == 101
        
        ret, frame = vp.read_frame()
        assert frame == "F99"
        
        vp.release()


def test_clean_shutdown():
    """F. Clean shutdown"""
    seq = [(True, "A", 0.1) for _ in range(100)]
    mock_cap = MockVideoCapture(seq)
    
    with patch('vision.video_processor.cv2.VideoCapture', return_value=mock_cap):
        vp = VideoProcessor("0", output_path=None, is_live=True)
        time.sleep(0.2)
        
        assert vp._capture_thread.is_alive()
        vp.release()
        
        assert not vp._capture_thread.is_alive()
        assert not mock_cap.is_opened


def test_consumer_shutdown():
    """G. Consumer shutdown"""
    seq = [(True, "A", 10.0)]
    mock_cap = MockVideoCapture(seq)
    
    with patch('vision.video_processor.cv2.VideoCapture', return_value=mock_cap):
        vp = VideoProcessor("0", output_path=None, is_live=True)
        
        def call_release():
            time.sleep(0.1)
            vp.release()
            
        threading.Thread(target=call_release).start()
        
        ret, frame = vp.read_frame()
        assert ret is False
        assert frame is None


def test_offline_compatibility():
    """J. Offline compatibility"""
    seq = [
        (True, "A", 0),
        (True, "B", 0),
        (True, "C", 0),
        (False, None, 0)
    ]
    mock_cap = MockVideoCapture(seq)
    
    with patch('vision.video_processor.cv2.VideoCapture', return_value=mock_cap):
        vp = VideoProcessor("test.mp4", output_path=None, is_live=False)
        
        assert not hasattr(vp, '_capture_thread') or vp._capture_thread is None
        
        ret, f = vp.read_frame()
        assert f == "A"
        ret, f = vp.read_frame()
        assert f == "B"
        ret, f = vp.read_frame()
        assert f == "C"
        ret, f = vp.read_frame()
        assert ret is False
        
        vp.release()


class MockDetector:
    def __init__(self):
        self.detections = []
    def detect(self, frame, use_tracking=False):
        return self.detections
    def reset_tracking(self):
        pass

class MockTrackManager:
    def __init__(self, *args):
        self.tracks = {}
        self.update_count = 0
    def update(self, det, lanes, t, fc):
        self.update_count += 1

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

def test_tracker_continuity(mock_adapter):
    """H. Tracker continuity: Dropped frames do not reset tracker state"""
    seq = [
        (True, "A", 0),
        (True, "B", 0),
        (False, None, 0.5)
    ]
    mock_cap = MockVideoCapture(seq)
    
    with patch('vision.adapter.VideoProcessor') as MockVP, \
         patch('vision.adapter.TrackManager', MockTrackManager):
         
        instance = MockVP.return_value
        instance.read_frame.side_effect = [(True, "A"), (True, "B"), (False, None)]
        
        gen = mock_adapter.process_video("0", None, use_tracking=True, is_live=True)
        states = list(gen)
        
        assert len(states) == 2
        assert states[0].frame_id == 1
        assert states[1].frame_id == 2
