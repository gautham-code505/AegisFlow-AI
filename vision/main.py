import json
import time
import argparse
from roi import ROIManager
from occupancy import OccupancyCalculator
from detector import VehicleDetector
from video_processor import VideoProcessor

def process_video(config_path, model_path, input_video, output_video, max_frames=None):
    print("Initializing AegisFlow AI Vision Module...")
    
    roi_mgr = ROIManager(config_path)
    occ_calc = OccupancyCalculator(config_path, roi_mgr)
    detector = VehicleDetector(model_path, config_path)
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
        vehicles_per_lane = {lane: [] for lane in roi_mgr.lanes.keys()}
        
        for det in detections:
            cx, cy = det['center']
            cls = det['class']
            
            lane = roi_mgr.get_lane_for_point(cx, cy)
            lane_assignments.append(lane)
            
            if lane:
                vehicles_per_lane[lane].append(cls)
                
        # 3. Calculate state
        state = {
            "timestamp": round(frame_count / vid_proc.fps, 2),
            "lanes": {},
            "emergency": {
                "detected": False,
                "lane": None
            }
        }
        
        for lane in roi_mgr.lanes.keys():
            count = len(vehicles_per_lane[lane])
            occupancy = occ_calc.calculate_occupancy(lane, vehicles_per_lane[lane])
            state["lanes"][lane] = {
                "vehicle_count": count,
                "occupancy": round(occupancy, 2)
            }
            
        # 4. Print / Log state periodically
        if frame_count % int(vid_proc.fps) == 0:
            print(f"\n--- Frame {frame_count} ---")
            print(json.dumps(state, indent=2))
            
        # 5. Visualize
        vid_proc.draw_polygons(frame, roi_mgr.get_polygons())
        vid_proc.draw_detections(frame, detections, lane_assignments)
        vid_proc.draw_state(frame, state)
        vid_proc.write_frame(frame)
        
    vid_proc.release()
    print("\nProcessing complete. Output saved to", output_video)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AegisFlow AI Vision Module")
    parser.add_argument("--config", type=str, default="config.json")
    parser.add_argument("--model", type=str, default="../yolov8n.pt")
    parser.add_argument("--input", type=str, required=True, help="Path to input video")
    parser.add_argument("--output", type=str, default="output.mp4", help="Path to output video")
    parser.add_argument("--max-frames", type=int, default=None, help="Max frames to process")
    
    args = parser.parse_args()
    process_video(args.config, args.model, args.input, args.output, args.max_frames)
