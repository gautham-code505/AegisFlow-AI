import json
import time
import argparse
from roi import ROIManager
from occupancy import OccupancyCalculator
from detector import VehicleDetector
from video_processor import VideoProcessor

from typing import Dict, TypedDict, Optional, Any, Iterator

class LaneState(TypedDict):
    vehicle_count: int
    pedestrian_count: int
    occupancy: float

class EmergencyState(TypedDict):
    detected: bool
    lane: Optional[str]
    manual_override: bool

class CrosswalkState(TypedDict):
    pedestrian_count: int

class TrafficState(TypedDict):
    timestamp: float
    lanes: Dict[str, LaneState]
    crosswalks: Dict[str, CrosswalkState]
    emergency: EmergencyState

def process_video(config_path, model_path, input_video, output_video, max_frames=None, conf_threshold=0.25, demo_emergency=None) -> Iterator[TrafficState]:
    print("Initializing AegisFlow AI Vision Module...")
    
    roi_mgr = ROIManager(config_path)
    occ_calc = OccupancyCalculator(config_path, roi_mgr)
    detector = VehicleDetector(model_path, config_path, conf_threshold=conf_threshold)
    vid_proc = VideoProcessor(input_video, output_video)
    
    frame_count = 0
    
    while True:
        ret, frame = vid_proc.read_frame()
        if not ret:
            break
            
        frame_count += 1
        if max_frames and frame_count > max_frames:
            break
            
        # 1. Detect vehicles
        detections = detector.detect(frame)
        
        # 2. Assign to ROIs
        lane_assignments = []
        cw_assignments = []
        vehicles_per_lane = {lane: [] for lane in roi_mgr.lanes.keys()}
        pedestrians_per_lane = {lane: [] for lane in roi_mgr.lanes.keys()}
        pedestrians_per_cw = {cw: [] for cw in roi_mgr.crosswalks.keys()}
        
        for det in detections:
            cx, cy = det['center']
            cls = det['class']
            
            lane = roi_mgr.get_lane_for_point(cx, cy)
            cw = roi_mgr.get_crosswalk_for_point(cx, cy)
            lane_assignments.append(lane)
            cw_assignments.append(cw)
            
            if cls == 'person':
                if cw:
                    pedestrians_per_cw[cw].append(cls)
                elif lane:
                    pedestrians_per_lane[lane].append(cls)
            else:
                if lane:
                    vehicles_per_lane[lane].append(cls)
                
        # 3. Calculate state
        state: TrafficState = {
            "timestamp": round(frame_count / vid_proc.fps, 2),
            "lanes": {},
            "crosswalks": {},
            "emergency": {
                "detected": False,
                "lane": None,
                "manual_override": False
            }
        }
        
        if demo_emergency and demo_emergency in roi_mgr.lanes:
            state["emergency"]["detected"] = True
            state["emergency"]["lane"] = demo_emergency
            state["emergency"]["manual_override"] = True
        
        for lane in roi_mgr.lanes.keys():
            v_count = len(vehicles_per_lane[lane])
            p_count = len(pedestrians_per_lane[lane])
            occupancy = occ_calc.calculate_occupancy(lane, vehicles_per_lane[lane])
            state["lanes"][lane] = {
                "vehicle_count": v_count,
                "pedestrian_count": p_count,
                "occupancy": round(occupancy, 2)
            }
            
        for cw in roi_mgr.crosswalks.keys():
            state["crosswalks"][cw] = {
                "pedestrian_count": len(pedestrians_per_cw[cw])
            }
            
        # 4. Visualize
        vid_proc.draw_polygons(frame, roi_mgr.get_polygons())
        vid_proc.draw_crosswalks(frame, roi_mgr.get_crosswalk_polygons())
        vid_proc.draw_detections(frame, detections, lane_assignments, cw_assignments)
        vid_proc.draw_state(frame, state)
        vid_proc.write_frame(frame)
        
        yield state
        
    vid_proc.release()
    print("\nProcessing complete. Output saved to", output_video)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AegisFlow AI Vision Module")
    parser.add_argument("--config", type=str, default="config.json")
    parser.add_argument("--model", type=str, default="../yolov8n.pt")
    parser.add_argument("--input", type=str, required=True, help="Path to input video")
    parser.add_argument("--output", type=str, default="output.mp4", help="Path to output video")
    parser.add_argument("--max-frames", type=int, default=None, help="Max frames to process")
    parser.add_argument("--conf-threshold", type=float, default=0.25, help="Confidence threshold for detections")
    parser.add_argument("--demo-emergency", type=str, default=None, help="Demo emergency by specifying a lane name (e.g. 'north')")
    
    args = parser.parse_args()
    
    frame_count = 0
    fps = 30 # Default assumption if we want to print periodically, though vid_proc knows real FPS.
    
    for state in process_video(
        config_path=args.config,
        model_path=args.model,
        input_video=args.input,
        output_video=args.output,
        max_frames=args.max_frames,
        conf_threshold=args.conf_threshold,
        demo_emergency=args.demo_emergency
    ):
        frame_count += 1
        # Print / Log state periodically
        # Assuming 30 fps for printing just to match previous behavior 
        # (could get fps from processor but it's internal to the generator now)
        if frame_count % 30 == 0:
            print(f"\n--- Frame {frame_count} ---")
            print(json.dumps(state, indent=2))
