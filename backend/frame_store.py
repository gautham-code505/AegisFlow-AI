import threading
import cv2
import numpy as np

class LatestFrameStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._latest_jpeg_bytes = None
        
    def update(self, frame: np.ndarray):
        """Encodes the OpenCV frame to JPEG and stores it thread-safely."""
        if frame is None:
            return
            
        ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
        if ret:
            with self._lock:
                self._latest_jpeg_bytes = buffer.tobytes()
                
    def get_latest(self) -> bytes:
        """Returns the latest JPEG bytes, or None if empty."""
        with self._lock:
            return self._latest_jpeg_bytes
            
    def clear(self):
        """Clears the stored frame."""
        with self._lock:
            self._latest_jpeg_bytes = None
            
    def is_available(self) -> bool:
        """Checks if a frame is currently available."""
        with self._lock:
            return self._latest_jpeg_bytes is not None
