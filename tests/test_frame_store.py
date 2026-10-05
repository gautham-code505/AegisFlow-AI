import pytest
import numpy as np
import threading
from backend.frame_store import LatestFrameStore
import cv2

def test_frame_store_empty():
    store = LatestFrameStore()
    assert not store.is_available()
    assert store.get_latest() is None

def test_frame_store_update_clear():
    store = LatestFrameStore()
    
    # Create a dummy frame (e.g. 10x10 black image)
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    store.update(frame)
    
    assert store.is_available()
    frame_bytes = store.get_latest()
    assert frame_bytes is not None
    assert isinstance(frame_bytes, bytes)
    
    # Clear
    store.clear()
    assert not store.is_available()
    assert store.get_latest() is None

def test_frame_store_thread_safety():
    store = LatestFrameStore()
    
    def writer_thread():
        frame = np.zeros((10, 10, 3), dtype=np.uint8)
        for _ in range(100):
            store.update(frame)
            
    def reader_thread():
        for _ in range(100):
            _ = store.get_latest()
            
    t1 = threading.Thread(target=writer_thread)
    t2 = threading.Thread(target=reader_thread)
    
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    
    # Should end up with a frame available
    assert store.is_available()
