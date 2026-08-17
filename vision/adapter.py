import json
import logging
import time
from typing import Generator, Dict, List
import cv2

from vision.roi import ROIManager
from vision.occupancy import OccupancyCalculator
from vision.detector import VehicleDetector
from vision.video_processor import VideoProcessor
from models import TrafficState, LaneState, Lane, EmergencyState

logger = logging.getLogger("aegisflow.vision.adapter")

class VisionAdapter:
    """
    Adapter bridging Harshadha's Vision Perception module to AegisFlow AI.
    Converts raw YOLO/OpenCV detections into canonical TrafficState snapshots.
    """
    
    # Map vision configuration lane strings to enum
    LANE_MAPPING = {
        "north": Lane.NORTH,
        "south": Lane.SOUTH,
        "east": Lane.EAST,
        "west": Lane.WEST
    }

    def __init__(self, config_path: str = "vision/config.json", model_path: str = "../yolov8n.pt"):
        self.config_path = config_path
        self.model_path = model_path
        self.roi_mgr = ROIManager(config_path)
        self.occ_calc = OccupancyCalculator(config_path, self.roi_mgr)
        
        # Load detector lazily to avoid heavy loading on import/startup if not needed immediately
        self.detector = None

    def _ensure_detector(self):
        if self.detector is None:
            logger.info(f"Loading YOLO model from {self.model_path}")
            self.detector = VehicleDetector(self.model_path, self.config_path)

    def process_video(self, input_video: str, output_video: str, process_every_n_frames: int = 5) -> Generator[TrafficState, None, None]:
        """
        Process a video file, yielding TrafficState snapshots for each processed frame, 
        and writing the annotated video to output_video.
        """
        self._ensure_detector()
        
        try:
            vid_proc = VideoProcessor(input_video, output_video)
        except ValueError as e:
            logger.error(f"Failed to open video {input_video}: {e}")
            raise

        frame_count = 0
        
        try:
            while True:
                ret, frame = vid_proc.read_frame()
                if not ret:
                    break
                    
                frame_count += 1
                
                # Frame rate control
                if frame_count % process_every_n_frames != 0:
                    vid_proc.write_frame(frame) # Write original frame to maintain FPS
                    continue
                    
                # 1. Detect
                detections = self.detector.detect(frame)
                
                # 2. Assign to ROIs
                lane_assignments = []
                vehicles_per_lane: Dict[str, List[str]] = {lane: [] for lane in self.roi_mgr.lanes.keys()}
                
                for det in detections:
                    cx, cy = det['center']
                    cls = det['class']
                    
                    lane = self.roi_mgr.get_lane_for_point(cx, cy)
                    lane_assignments.append(lane)
                    
                    if lane:
                        vehicles_per_lane[lane].append(cls)
                        
                # 3. Translate to Canonical TrafficState
                timestamp = round(frame_count / vid_proc.fps, 2)
                
                lane_states = {}
                for lane_str, lane_enum in self.LANE_MAPPING.items():
                    if lane_str not in vehicles_per_lane:
                        lane_states[lane_enum] = LaneState()
                        continue
                        
                    detected_classes = vehicles_per_lane[lane_str]
                    
                    veh_count = 0
                    heavy_count = 0
                    ped_count = 0
                    
                    for cls in detected_classes:
                        if cls == "person":
                            ped_count += 1
                        elif cls in ["bus", "truck"]:
                            veh_count += 1
                            heavy_count += 1
                        elif cls in ["car", "motorcycle", "bicycle"]:
                            veh_count += 1
                            
                    occupancy = self.occ_calc.calculate_occupancy(lane_str, detected_classes)
                    
                    lane_states[lane_enum] = LaneState(
                        vehicle_count=veh_count,
                        occupancy=round(occupancy, 3),
                        pedestrian_count=ped_count,
                        heavy_vehicle_count=heavy_count
                    )
                    
                state = TrafficState(
                    timestamp=timestamp,
                    frame_id=frame_count,
                    source="vision",
                    lanes=lane_states,
                    emergency=EmergencyState(detected=False, lane=None, vehicle_type=None)
                )
                
                # 4. Visualize
                # Construct state dict expected by Harshadha's drawing method
                vis_state = {
                    "lanes": {
                        lane_str: {
                            "vehicle_count": lane_states[lane_enum].vehicle_count,
                            "occupancy": lane_states[lane_enum].occupancy
                        } for lane_str, lane_enum in self.LANE_MAPPING.items()
                    }
                }
                
                vid_proc.draw_polygons(frame, self.roi_mgr.get_polygons())
                vid_proc.draw_detections(frame, detections, lane_assignments)
                vid_proc.draw_state(frame, vis_state)
                vid_proc.write_frame(frame)
                
                yield state
                
        except Exception as e:
            logger.error(f"Error during vision processing at frame {frame_count}: {e}")
            raise
        finally:
            vid_proc.release()
            logger.info(f"Video processing complete. Annotated output saved to {output_video}")
