"""
AegisFlow AI - Synthetic Demo Scenarios

Provides deterministic canonical TrafficState scenario payloads for local dev & testing.
"""

import time
from typing import Dict
from models import TrafficState, LaneState, EmergencyState, Lane


def get_demo_scenarios() -> Dict[str, TrafficState]:
    """Returns dictionary of predefined synthetic TrafficState scenarios."""
    now = time.time()

    return {
        "balanced": TrafficState(
            timestamp=now,
            frame_id=1001,
            source="DEMO / BALANCED TRAFFIC",
            total_vehicles=18,
            total_classes={"car": 17, "truck": 1},
            lanes={
                Lane.NORTH: LaneState(vehicle_count=5, occupancy=0.25, pedestrian_count=1, heavy_vehicle_count=0),
                Lane.SOUTH: LaneState(vehicle_count=4, occupancy=0.20, pedestrian_count=0, heavy_vehicle_count=0),
                Lane.EAST: LaneState(vehicle_count=6, occupancy=0.30, pedestrian_count=2, heavy_vehicle_count=1),
                Lane.WEST: LaneState(vehicle_count=3, occupancy=0.15, pedestrian_count=0, heavy_vehicle_count=0),
            },
            emergency=EmergencyState(detected=False),
        ),
        "heavy-north": TrafficState(
            timestamp=now,
            frame_id=1002,
            source="DEMO / HEAVY NORTH CORRIDOR",
            total_vehicles=31,
            total_classes={"car": 27, "truck": 4},
            lanes={
                Lane.NORTH: LaneState(vehicle_count=18, occupancy=0.85, pedestrian_count=3, heavy_vehicle_count=3),
                Lane.SOUTH: LaneState(vehicle_count=4, occupancy=0.20, pedestrian_count=1, heavy_vehicle_count=0),
                Lane.EAST: LaneState(vehicle_count=7, occupancy=0.35, pedestrian_count=0, heavy_vehicle_count=1),
                Lane.WEST: LaneState(vehicle_count=2, occupancy=0.10, pedestrian_count=0, heavy_vehicle_count=0),
            },
            emergency=EmergencyState(detected=False),
        ),
        "heavy-east": TrafficState(
            timestamp=now,
            frame_id=1003,
            source="DEMO / HEAVY EAST APPROACH",
            total_vehicles=28,
            total_classes={"car": 26, "truck": 2},
            lanes={
                Lane.NORTH: LaneState(vehicle_count=4, occupancy=0.20, pedestrian_count=0, heavy_vehicle_count=0),
                Lane.SOUTH: LaneState(vehicle_count=5, occupancy=0.25, pedestrian_count=1, heavy_vehicle_count=0),
                Lane.EAST: LaneState(vehicle_count=16, occupancy=0.80, pedestrian_count=4, heavy_vehicle_count=2),
                Lane.WEST: LaneState(vehicle_count=3, occupancy=0.15, pedestrian_count=0, heavy_vehicle_count=0),
            },
            emergency=EmergencyState(detected=False),
        ),
        "emergency-east": TrafficState(
            timestamp=now,
            frame_id=1004,
            source="DEMO / SIMULATED EMERGENCY",
            total_vehicles=22,
            total_classes={"car": 20, "truck": 1, "ambulance": 1},
            lanes={
                Lane.NORTH: LaneState(vehicle_count=8, occupancy=0.40, pedestrian_count=1, heavy_vehicle_count=0),
                Lane.SOUTH: LaneState(vehicle_count=6, occupancy=0.30, pedestrian_count=0, heavy_vehicle_count=0),
                Lane.EAST: LaneState(vehicle_count=5, occupancy=0.70, pedestrian_count=0, heavy_vehicle_count=1),
                Lane.WEST: LaneState(vehicle_count=3, occupancy=0.15, pedestrian_count=0, heavy_vehicle_count=0),
            },
            emergency=EmergencyState(detected=True, lane=Lane.EAST, vehicle_type="AMBULANCE"),
        ),
    }
