from typing import Dict, Any, Tuple
from .models import TrafficState
from .config import DecisionEngineConfig

def calculate_lane_scores(
    state: TrafficState,
    waiting_times: Dict[str, float],
    consecutive_skips: Dict[str, int],
    config: DecisionEngineConfig
) -> Dict[str, Tuple[float, Dict[str, float]]]:
    """
    Calculates traffic scores for all lanes based on occupancy, vehicle counts,
    waiting times, pedestrian demand, and starvation factors.
    
    Returns a dictionary mapping lane name to a tuple of (total_score, score_breakdown).
    """
    scores: Dict[str, Tuple[float, Dict[str, float]]] = {}

    for lane_name, lane_state in state.lanes.items():
        # 1. Occupancy component
        occ = lane_state.occupancy
        
        # 2. Normalized vehicle count
        norm_veh = min(1.0, lane_state.vehicle_count / max(1, config.MAX_EXPECTED_VEHICLES))

        # 3. Normalized waiting time
        wait_time = waiting_times.get(lane_name, 0.0)
        norm_wait = min(1.0, wait_time / max(0.1, config.STARVATION_THRESHOLD))

        # 4. Pedestrian demand
        ped_count = 0
        if state.pedestrians is not None:
            ped_count = state.pedestrians.get(lane_name, 0)
        norm_ped = min(1.0, ped_count / max(1, config.MAX_EXPECTED_PEDESTRIANS))

        # 5. Starvation factor
        # Continuous representation: how close the lane is to starvation
        skips = consecutive_skips.get(lane_name, 0)
        starvation_factor = max(
            min(1.0, wait_time / max(0.1, config.STARVATION_THRESHOLD)),
            min(1.0, skips / max(1, config.MAX_CONSECUTIVE_SKIPS))
        )

        # Weighted calculation
        occ_component = config.OCCUPANCY_WEIGHT * occ
        veh_component = config.VEHICLE_WEIGHT * norm_veh
        wait_component = config.WAITING_WEIGHT * norm_wait
        ped_component = config.PEDESTRIAN_WEIGHT * norm_ped
        starv_component = config.STARVATION_WEIGHT * starvation_factor

        total_score = (
            occ_component +
            veh_component +
            wait_component +
            ped_component +
            starv_component
        )

        breakdown = {
            "occupancy_component": occ_component,
            "vehicle_component": veh_component,
            "waiting_component": wait_component,
            "pedestrian_component": ped_component,
            "starvation_component": starv_component,
            "raw_occupancy": occ,
            "raw_vehicle_count": lane_state.vehicle_count,
            "raw_waiting_time": wait_time,
            "raw_pedestrian_count": ped_count,
            "raw_skips": skips
        }

        scores[lane_name] = (total_score, breakdown)

    return scores
