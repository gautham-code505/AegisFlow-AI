import json
import cv2
import numpy as np
from pathlib import Path

class ROIManager:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.lanes = {}
        self.capacities = {}
        self.crosswalks = {}
        self.load_config()

    def load_config(self):
        with open(self.config_path, 'r') as f:
            config = json.load(f)
            
        for lane_name, lane_data in config.get("lanes", {}).items():
            pts = np.array(lane_data["polygon"], np.int32)
            pts = pts.reshape((-1, 1, 2))
            self.lanes[lane_name] = pts
            self.capacities[lane_name] = lane_data.get("capacity", 10)
            
        for cw_name, cw_data in config.get("crosswalks", {}).items():
            pts = np.array(cw_data["polygon"], np.int32)
            pts = pts.reshape((-1, 1, 2))
            self.crosswalks[cw_name] = pts

    def get_lane_for_point(self, x: int, y: int) -> str:
        """
        Returns the name of the lane the point (x, y) belongs to, 
        or None if it doesn't belong to any ROI.
        """
        point = (float(x), float(y))
        for lane_name, polygon in self.lanes.items():
            # cv2.pointPolygonTest returns >0 if inside, 0 if on boundary, <0 if outside
            if cv2.pointPolygonTest(polygon, point, False) >= 0:
                return lane_name
        return None
        
    def get_crosswalk_for_point(self, x: int, y: int) -> str:
        """
        Returns the name of the crosswalk the point (x, y) belongs to, 
        or None if it doesn't belong to any crosswalk ROI.
        """
        point = (float(x), float(y))
        for cw_name, polygon in self.crosswalks.items():
            if cv2.pointPolygonTest(polygon, point, False) >= 0:
                return cw_name
        return None

    def get_polygons(self):
        """Returns a dict of lane_name: polygon_points for visualization."""
        return self.lanes
        
    def get_crosswalk_polygons(self):
        """Returns a dict of crosswalk_name: polygon_points for visualization."""
        return self.crosswalks

    def get_capacity(self, lane_name: str) -> int:
        return self.capacities.get(lane_name, 1)

if __name__ == "__main__":
    roi_mgr = ROIManager("config.json")
    print("Loaded lanes:", list(roi_mgr.lanes.keys()))
    print("Loaded crosswalks:", list(roi_mgr.crosswalks.keys()))
    print("Point (300, 100) is in lane:", roi_mgr.get_lane_for_point(300, 100))
