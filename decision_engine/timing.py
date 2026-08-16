from .models import LaneState
from .config import DecisionConfig

def calculate_green_time(
    lane_state: LaneState,
    config: DecisionConfig
) -> int:
    """
    Dynamically calculates the green signal duration for a chosen lane.
    Uses the lane's occupancy and vehicle count to determine traffic demand,
    scaling duration between MIN_GREEN_TIME and MAX_GREEN_TIME.
    """
    # 1. Estimate lane demand metric on a scale of 0.0 to 1.0
    norm_vehicles = min(1.0, lane_state.vehicle_count / max(1, config.MAX_EXPECTED_VEHICLES))
    
    # We weight occupancy and normalized vehicles equally to represent demand
    demand_factor = (lane_state.occupancy + norm_vehicles) / 2.0
    
    # 2. Scale between MIN_GREEN_TIME and MAX_GREEN_TIME
    duration_float = config.MIN_GREEN_TIME + (config.MAX_GREEN_TIME - config.MIN_GREEN_TIME) * demand_factor
    duration = int(round(duration_float))
    
    # 3. Constrain to limits
    duration = max(config.MIN_GREEN_TIME, min(config.MAX_GREEN_TIME, duration))
    
    return duration
