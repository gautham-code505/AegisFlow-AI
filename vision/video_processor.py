import cv2
import numpy as np

class VideoProcessor:
    def __init__(self, input_path: str, output_path: str):
        self.input_path = input_path
        self.output_path = output_path
        self.cap = cv2.VideoCapture(input_path)
        
        if not self.cap.isOpened():
            raise ValueError(f"Could not open video file {input_path}")
            
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        
        # Initialize video writer
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        self.writer = cv2.VideoWriter(output_path, fourcc, self.fps, (self.width, self.height))
        
    def read_frame(self):
        ret, frame = self.cap.read()
        return ret, frame
        
    def release(self):
        self.cap.release()
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
        self.writer.write(frame)
