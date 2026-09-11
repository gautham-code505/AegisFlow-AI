import json
import math
from typing import Dict, List, Optional
from collections import deque
from enum import Enum

class MovementState(str, Enum):
    APPROACHING = "APPROACHING"
    QUEUED = "QUEUED"
    MOVING = "MOVING"

class Track:
    def __init__(self, track_id: int, class_name: str, initial_approach: Optional[str], cx: float, cy: float, timestamp: float, frame_id: int, history_size: int):
        self.track_id = track_id
        self.class_name = class_name
        self.initial_approach = initial_approach
        self.current_approach = initial_approach
        self.candidate_approach = initial_approach
        self.candidate_approach_count = 0
        self.consecutive_stationary = 0
        self.consecutive_moving = 0
        self.movement_state = MovementState.APPROACHING
        self.first_seen_at = timestamp
        self.last_seen_at = timestamp
        self.queued_at: Optional[float] = None
        # deque of (cx, cy, timestamp, frame_id)
        self.position_history = deque(maxlen=history_size)
        self.position_history.append((cx, cy, timestamp, frame_id))

    def update(self, current_approach: Optional[str], cx: float, cy: float, timestamp: float, frame_id: int, 
               stationary_pixel_threshold: float, approach_debounce_frames: int, 
               stationary_debounce_frames: int, moving_debounce_frames: int):
        
        if current_approach == self.current_approach:
            self.candidate_approach_count = 0
        else:
            if current_approach == self.candidate_approach:
                self.candidate_approach_count += 1
            else:
                self.candidate_approach = current_approach
                self.candidate_approach_count = 1
                
            if self.candidate_approach_count >= approach_debounce_frames:
                self.current_approach = self.candidate_approach
                
        self.last_seen_at = timestamp
        self.position_history.append((cx, cy, timestamp, frame_id))
        
        # Calculate displacement if we have enough history
        if len(self.position_history) > 1:
            old_cx, old_cy, _, _ = self.position_history[0]
            displacement = math.hypot(cx - old_cx, cy - old_cy)
            
            if displacement < stationary_pixel_threshold:
                self.consecutive_stationary += 1
                self.consecutive_moving = 0
            else:
                self.consecutive_moving += 1
                self.consecutive_stationary = 0
                
            if self.movement_state == MovementState.APPROACHING:
                if displacement < stationary_pixel_threshold:
                    self.queued_at = timestamp
                    self.movement_state = MovementState.QUEUED
                else:
                    self.queued_at = None
                    self.movement_state = MovementState.MOVING
            elif self.movement_state == MovementState.MOVING:
                if self.consecutive_stationary >= stationary_debounce_frames:
                    self.queued_at = timestamp
                    self.movement_state = MovementState.QUEUED
            elif self.movement_state == MovementState.QUEUED:
                if self.consecutive_moving >= moving_debounce_frames:
                    self.queued_at = None
                    self.movement_state = MovementState.MOVING

class TrackManager:
    def __init__(self, config_path: str):
        self.tracks: Dict[int, Track] = {}
        self.timeout_seconds = 2.0
        self.stationary_pixel_threshold = 5.0
        self.history_window_frames = 30
        self.approach_debounce_frames = 3
        self.stationary_debounce_frames = 3
        self.moving_debounce_frames = 3
        self.load_config(config_path)

    def load_config(self, config_path: str):
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                tracking_config = config.get("tracking", {})
                self.timeout_seconds = tracking_config.get("timeout_seconds", 2.0)
                self.stationary_pixel_threshold = tracking_config.get("stationary_pixel_threshold", 5.0)
                self.history_window_frames = tracking_config.get("history_window_frames", 30)
                self.approach_debounce_frames = tracking_config.get("approach_debounce_frames", 3)
                self.stationary_debounce_frames = tracking_config.get("stationary_debounce_frames", 3)
                self.moving_debounce_frames = tracking_config.get("moving_debounce_frames", 3)
        except Exception:
            pass

    def update(self, detections: List[dict], lane_assignments: List[Optional[str]], timestamp: float, frame_id: int) -> List[Track]:
        """
        Updates the tracker with new detections.
        Ignores detections without a track_id.
        """
        for det, approach in zip(detections, lane_assignments):
            track_id = det.get("track_id")
            if track_id is None:
                continue
                
            cx, cy = det["center"]
            class_name = det["class"]
            
            if track_id not in self.tracks:
                self.tracks[track_id] = Track(
                    track_id=track_id, 
                    class_name=class_name, 
                    initial_approach=approach, 
                    cx=cx, cy=cy, 
                    timestamp=timestamp, 
                    frame_id=frame_id, 
                    history_size=self.history_window_frames
                )
            else:
                self.tracks[track_id].update(
                    current_approach=approach, 
                    cx=cx, cy=cy, 
                    timestamp=timestamp, 
                    frame_id=frame_id, 
                    stationary_pixel_threshold=self.stationary_pixel_threshold,
                    approach_debounce_frames=self.approach_debounce_frames,
                    stationary_debounce_frames=self.stationary_debounce_frames,
                    moving_debounce_frames=self.moving_debounce_frames
                )
                
        self._cleanup(timestamp)
        return list(self.tracks.values())
        
    def _cleanup(self, current_timestamp: float):
        """Removes tracks that haven't been seen for timeout_seconds."""
        expired_ids = [
            tid for tid, track in self.tracks.items()
            if current_timestamp - track.last_seen_at > self.timeout_seconds
        ]
        for tid in expired_ids:
            del self.tracks[tid]
