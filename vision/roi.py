import json
import cv2
import numpy as np
import logging

logger = logging.getLogger(__name__)

class ROIManager:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.lanes = {}
        self.capacities = {}
        self._logged_ar_mismatch = False
        self.load_config()

    def load_config(self):
        with open(self.config_path, 'r') as f:
            config = json.load(f)
            
        self.camera_resolution = config.get("camera_resolution", [640, 480])
        self.calib_ar = config.get("calibration_aspect_ratio", self.camera_resolution[0] / float(self.camera_resolution[1]))
        self.coordinate_system = config.get("coordinate_system", "pixel")
        
        base_w, base_h = self.camera_resolution[0], self.camera_resolution[1]
            
        for lane_name, lane_data in config.get("lanes", {}).items():
            pts = np.array(lane_data["polygon"], np.float32)
            pts = pts.reshape((-1, 1, 2))
            
            if self.coordinate_system == "pixel" and np.max(pts) > 1.0:
                pts[:, :, 0] /= base_w
                pts[:, :, 1] /= base_h
                
            self.lanes[lane_name] = pts
            self.capacities[lane_name] = lane_data.get("capacity", 10)

    def get_lane_for_point(self, x: float, y: float, frame_width: float = 640.0, frame_height: float = 480.0) -> str:
        """
        Returns the name of the lane the point (x, y) belongs to.
        Enforces the Same-Aspect-Ratio policy: rejects frames that do not match the calibration aspect ratio.
        """
        current_ar = frame_width / float(frame_height)
        if abs(current_ar - self.calib_ar) > 0.05:
            if not self._logged_ar_mismatch:
                logger.warning(f"Aspect ratio mismatch! Calibrated for {self.calib_ar:.2f}, got {current_ar:.2f}. Rejecting uncalibrated physical geometries.")
                self._logged_ar_mismatch = True
            return None
            
        x_norm = float(x) / float(frame_width)
        y_norm = float(y) / float(frame_height)
        point = (x_norm, y_norm)
        
        for lane_name, polygon in self.lanes.items():
            # cv2.pointPolygonTest returns >0 if inside, 0 if on boundary, <0 if outside
            if cv2.pointPolygonTest(polygon, point, False) >= 0:
                return lane_name
        return None

    def get_polygons(self, frame_width: int = 640, frame_height: int = 480):
        """
        Returns a dict of lane_name: polygon_points for visualization,
        scaled up from normalized geometry to the target frame resolution.
        Returns empty dict if aspect ratio mismatches to prevent misleading visuals.
        """
        current_ar = frame_width / float(frame_height)
        if abs(current_ar - self.calib_ar) > 0.05:
            return {}
            
        scaled_lanes = {}
        for lane_name, poly in self.lanes.items():
            scaled_poly = poly.copy()
            scaled_poly[:, :, 0] *= frame_width
            scaled_poly[:, :, 1] *= frame_height
            scaled_lanes[lane_name] = scaled_poly.astype(np.int32)
        return scaled_lanes

    def get_capacity(self, lane_name: str) -> int:
        return self.capacities.get(lane_name, 1)

if __name__ == "__main__":
    roi_mgr = ROIManager("config.json")
    print("Loaded lanes:", list(roi_mgr.lanes.keys()))
    print("Point (300, 100) is in:", roi_mgr.get_lane_for_point(300, 100))
