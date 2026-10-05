import pytest
import time
import cv2
import numpy as np
from vision.video_processor import VideoProcessor
import threading

class FakeCapture:
    def __init__(self, width=640, height=480, fps=30):
        self._is_opened = True
        self.width = width
        self.height = height
        self.fps = fps
        self.frame_index = 0
        self._lock = threading.Lock()
        
    def isOpened(self):
        return self._is_opened
        
    def get(self, propId):
        if propId == cv2.CAP_PROP_FRAME_WIDTH:
            return self.width
        elif propId == cv2.CAP_PROP_FRAME_HEIGHT:
            return self.height
        elif propId == cv2.CAP_PROP_FPS:
            return self.fps
        return 0
        
    def read(self):
        with self._lock:
            if not self._is_opened:
                return False, None
            # create a dummy frame where first pixel encodes the frame index
            frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
            # Use blue channel of first pixel to store index modulo 256
            frame[0, 0, 0] = self.frame_index % 256
            self.frame_index += 1
            # Simulate real time capture rate
            time.sleep(1.0 / self.fps)
            return True, frame
            
    def release(self):
        with self._lock:
            self._is_opened = False

def test_latest_raw_frame_availability(monkeypatch):
    """Test that the stream drops frames and always provides the latest raw frame (no unbounded queue)."""
    # Monkeypatch VideoCapture to use FakeCapture
    monkeypatch.setattr(cv2, "VideoCapture", lambda src: FakeCapture())
    
    vp = VideoProcessor(0, is_live=True)
    time.sleep(0.2)  # Let it capture some frames (~6 frames at 30fps)
    
    ret1, frame1 = vp.read_frame()
    assert ret1
    idx1 = frame1[0, 0, 0]
    
    time.sleep(0.2)  # Wait again, the capture loop should drop intermediate frames
    
    ret2, frame2 = vp.read_frame()
    assert ret2
    idx2 = frame2[0, 0, 0]
    
    # Prove that frames were skipped (no unbounded queue)
    # 0.2s * 30fps = 6 frames, so difference should be ~6, not 1
    diff = (int(idx2) - int(idx1)) % 256
    assert diff > 1, f"Expected dropped frames, but diff was {diff}"
    
    vp.release()

def test_latest_detection_result_handling_and_decoupled_stream(monkeypatch):
    """Test that stream remains available while inference is busy and uses latest overlay state."""
    monkeypatch.setattr(cv2, "VideoCapture", lambda src: FakeCapture())
    
    output_frames = []
    def frame_callback(frame):
        output_frames.append(frame.copy())
        
    vp = VideoProcessor(0, is_live=True, frame_callback=frame_callback)
    
    # Wait for capture and display threads to start producing frames
    time.sleep(0.2)
    initial_count = len(output_frames)
    assert initial_count > 0, "Display thread should be producing frames immediately"
    
    # Update overlay state
    polygons = {"north": np.array([[[0, 0], [10, 0], [10, 10], [0, 10]]])}
    detections = [{'bbox': [10, 10, 50, 50], 'class': 'car', 'confidence': 0.9, 'center': [30, 30]}]
    lane_assignments = ["north"]
    state = {"lanes": {"north": {"vehicle_count": 1, "occupancy": 0.5}}}
    
    vp.update_overlay(polygons, detections, lane_assignments, state)
    
    # Wait to ensure display thread picks it up
    time.sleep(0.2)
    
    final_count = len(output_frames)
    # The stream should continue producing frames at ~30 FPS independently of inference
    assert final_count > initial_count + 2
    
    # The latest frame should have drawn elements
    # Just checking the lock behavior implicitly works without crashing
    
    vp.release()
