import unittest
from roi import ROIManager
from occupancy import OccupancyCalculator
import json
import os

class TestPerception(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create a dummy config for testing
        cls.config_path = "test_config.json"
        config = {
            "camera_resolution": [640, 480],
            "lanes": {
                "north": {
                    "capacity": 10,
                    "polygon": [[0, 0], [100, 0], [100, 100], [0, 100]]
                }
            },
            "vehicle_weights": {
                "car": 1.0,
                "bus": 2.5
            }
        }
        with open(cls.config_path, "w") as f:
            json.dump(config, f)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.config_path):
            os.remove(cls.config_path)

    def test_roi_manager_inside(self):
        roi_mgr = ROIManager(self.config_path)
        lane = roi_mgr.get_lane_for_point(50, 50)
        self.assertEqual(lane, "north")

    def test_roi_manager_outside(self):
        roi_mgr = ROIManager(self.config_path)
        lane = roi_mgr.get_lane_for_point(150, 150)
        self.assertIsNone(lane)

    def test_occupancy_calculator(self):
        roi_mgr = ROIManager(self.config_path)
        calc = OccupancyCalculator(self.config_path, roi_mgr)
        
        vehicles = ["car", "bus"] # 1.0 + 2.5 = 3.5
        occ = calc.calculate_occupancy("north", vehicles)
        
        self.assertAlmostEqual(occ, 0.35)

    def test_occupancy_clamped(self):
        roi_mgr = ROIManager(self.config_path)
        calc = OccupancyCalculator(self.config_path, roi_mgr)
        
        vehicles = ["bus"] * 5 # 5 * 2.5 = 12.5 -> capacity is 10
        occ = calc.calculate_occupancy("north", vehicles)
        
        self.assertAlmostEqual(occ, 1.0) # Should be clamped to 1.0

if __name__ == '__main__':
    unittest.main()
