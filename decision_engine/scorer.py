from typing import Dict, Any, Tuple
from models import TrafficState
from .config import DecisionEngineConfig

def calculate_lane_scores(
    state: TrafficState,
    waiting_times: Dict[str, float],
    consecutive_skips: Dict[str, int],
    config: DecisionEngineConfig
) -> Dict[str, Tuple[float, Dict[str, Any]]]:
    """
    Calculates traffic scores for all lanes based on traffic demand intelligence.
    
    When tracking is available, relies exclusively on queued vehicle counts
    and observed average waiting times. When unavailable, falls back to
    occupancy and raw vehicle counts.
    
    Returns a dictionary mapping lane name to a tuple of (total_score, score_breakdown).
    """
    scores: Dict[str, Tuple[float, Dict[str, Any]]] = {}

    for lane_enum, lane_state in state.lanes.items():
        lane_name = lane_enum.value
        
        occ_component = 0.0
        queue_component = 0.0
        delay_component = 0.0
        veh_component = 0.0
        
        if getattr(state, "has_tracking_data", False):
            # 1. Tracking Available: Use strict queued and delay demand
            # Normalize queue against max expected queue
            norm_queue = min(1.0, getattr(lane_state, "queued_vehicle_count", 0) / max(1, config.MAX_EXPECTED_QUEUED))
            queue_component = config.TRACKING_QUEUE_WEIGHT * norm_queue
            
            # Normalize delay against max expected observed wait
            norm_delay = min(1.0, getattr(lane_state, "observed_average_wait", 0.0) / max(0.1, config.MAX_EXPECTED_OBSERVED_WAIT))
            delay_component = config.TRACKING_DELAY_WEIGHT * norm_delay
            
            used_tracking = True
            total_score = queue_component + delay_component
        else:
            # 2. Tracking Unavailable: Fallback to occupancy and raw vehicles
            # Normalize raw vehicle count
            norm_veh = min(1.0, lane_state.vehicle_count / max(1, config.MAX_EXPECTED_VEHICLES))
            veh_component = config.FALLBACK_VEHICLE_WEIGHT * norm_veh
            
            # Occupancy is inherently 0-1
            occ_component = config.FALLBACK_OCCUPANCY_WEIGHT * lane_state.occupancy
            
            used_tracking = False
            total_score = occ_component + veh_component

        breakdown = {
            "queue_component": queue_component,
            "delay_component": delay_component,
            "occupancy_component": occ_component,
            "vehicle_component": veh_component,
            "raw_occupancy": lane_state.occupancy,
            "raw_vehicle_count": lane_state.vehicle_count,
            "raw_queued_vehicle_count": getattr(lane_state, "queued_vehicle_count", 0),
            "raw_observed_wait": getattr(lane_state, "observed_average_wait", 0.0),
            "used_tracking": used_tracking
        }

        scores[lane_name] = (total_score, breakdown)

    return scores
