import json

class OccupancyCalculator:
    def __init__(self, config_path: str, roi_manager):
        self.config_path = config_path
        self.roi_manager = roi_manager
        self.vehicle_weights = {}
        self.load_config()

    def load_config(self):
        with open(self.config_path, 'r') as f:
            config = json.load(f)
            self.vehicle_weights = config.get("vehicle_weights", {})
            
    def get_weight(self, vehicle_class: str) -> float:
        return self.vehicle_weights.get(vehicle_class, 1.0)
        
    def calculate_occupancy(self, lane_name: str, vehicles_in_lane: list) -> float:
        """
        vehicles_in_lane: list of strings (class names) currently in the lane ROI
        Returns occupancy as a float between 0.0 and 1.0 (clamped).
        """
        capacity = self.roi_manager.get_capacity(lane_name)
        if capacity <= 0:
            return 0.0
            
        total_weight = 0.0
        for v_class in vehicles_in_lane:
            total_weight += self.get_weight(v_class)
            
        occupancy = total_weight / capacity
        # Clamp to 1.0 maximum
        return min(1.0, occupancy)

if __name__ == "__main__":
    from roi import ROIManager
    roi_mgr = ROIManager("config.json")
    calc = OccupancyCalculator("config.json", roi_mgr)
    
    lane_vehicles = ["car", "car", "bus", "motorcycle"]
    occ = calc.calculate_occupancy("north", lane_vehicles)
    print(f"Occupancy for north: {occ}")
