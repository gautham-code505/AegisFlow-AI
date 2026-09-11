import cv2
import numpy as np
import threading
import time
import logging

logger = logging.getLogger(__name__)

class VideoProcessor:
    def __init__(self, input_path, output_path: str = None, is_live: bool = False):
        self.input_path = input_path
        self.output_path = output_path
        
        # Determine source type
        self.is_live = is_live
        if isinstance(input_path, int):
            self.is_live = True
            input_source = input_path
        elif isinstance(input_path, str):
            if input_path.isdigit():
                self.is_live = True
                input_source = int(input_path)
            else:
                lower_path = input_path.lower()
                if lower_path.startswith(('rtsp://', 'http://', 'https://', 'udp://', 'rtmp://')):
                    self.is_live = True
                input_source = input_path
        else:
            input_source = input_path
            
        self.cap = cv2.VideoCapture(input_source)
        
        if not self.cap.isOpened():
            raise ValueError(f"Could not open video file/stream {input_path}")
            
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        if self.fps <= 0:
            self.fps = 30.0
            
        # Initialize video writer
        self.writer = None
        if output_path is not None:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            self.writer = cv2.VideoWriter(output_path, fourcc, self.fps, (self.width, self.height))
        
        # Live Stream Synchronization Primitives
        self._stop_event = threading.Event()
        self._frame_lock = threading.Lock()
        self._latest_frame = None
        self._has_new_frame = False
        self._frame_ready = threading.Event()
        self._stream_ended = False
        self._capture_thread = None
        
        if self.is_live:
            self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True, name="LiveCaptureThread")
            self._capture_thread.start()
            
    def _capture_loop(self):
        while not self._stop_event.is_set():
            ret, frame = self.cap.read()
            if not ret:
                # Frame acquisition failed, either temp or permanent end
                with self._frame_lock:
                    self._stream_ended = True
                self._frame_ready.set()
                break
                
            with self._frame_lock:
                self._latest_frame = (ret, frame)
                self._has_new_frame = True
            self._frame_ready.set()
            
    def read_frame(self):
        if self.is_live:
            while not self._stop_event.is_set():
                with self._frame_lock:
                    if self._has_new_frame:
                        ret, frame = self._latest_frame
                        self._has_new_frame = False
                        self._frame_ready.clear()
                        return ret, frame
                        
                # Wait out of lock
                self._frame_ready.wait(timeout=0.1)
                
                if self._stream_ended:
                    with self._frame_lock:
                        if not self._has_new_frame:
                            return False, None
            return False, None
        else:
            return self.cap.read()
            
    def release(self):
        self._stop_event.set()
        self._frame_ready.set()  # Wake up consumer if waiting
        if self._capture_thread and self._capture_thread.is_alive():
            self._capture_thread.join(timeout=2.0)
            
        self.cap.release()
        if self.writer is not None:
            self.writer.release()
        cv2.destroyAllWindows()
        
    def draw_polygons(self, frame, polygons_dict):
        """Draws the ROI polygons on the frame."""
        for name, polygon in polygons_dict.items():
            cv2.polylines(frame, [polygon], isClosed=True, color=(0, 255, 255), thickness=2)
            # Put label
            pos = tuple(polygon[0][0])
            cv2.putText(frame, name, pos, cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            
    def draw_detections(self, frame, detections, lane_assignments):
        """
        Draws bounding boxes, classes, and assigned lanes.
        lane_assignments: list of same length as detections with lane names (or None)
        """
        for i, det in enumerate(detections):
            x1, y1, x2, y2 = det['bbox']
            cls = det['class']
            conf = det['confidence']
            lane = lane_assignments[i]
            
            # Color: Green if assigned to a lane, Red if outside any lane
            color = (0, 255, 0) if lane else (0, 0, 255)
            
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            
            label = f"{cls} {conf:.2f}"
            if lane:
                label += f" ({lane})"
                
            cv2.putText(frame, label, (x1, max(y1 - 5, 0)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
            
            # Draw bottom-center point
            cx, cy = det['center']
            cv2.circle(frame, (cx, cy), 3, (255, 0, 0), -1)
            
    def draw_state(self, frame, state):
        """Draws the overall traffic state text on the top-left of the frame."""
        y_offset = 30
        cv2.putText(frame, "Traffic State:", (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        y_offset += 25
        
        for lane_name, data in state.get('lanes', {}).items():
            count = data.get('vehicle_count', 0)
            occ = data.get('occupancy', 0.0)
            text = f"{lane_name.capitalize()}: {count} veh, Occ: {occ*100:.1f}%"
            cv2.putText(frame, text, (20, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
            y_offset += 25
            
    def write_frame(self, frame):
        if self.writer is not None:
            self.writer.write(frame)
