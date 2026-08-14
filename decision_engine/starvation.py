from typing import Dict, List, Tuple
from .config import DecisionEngineConfig

def check_starvation(
    waiting_times: Dict[str, float],
    consecutive_skips: Dict[str, int],
    config: DecisionEngineConfig
) -> List[str]:
    """
    Identifies lanes that are starving based on waiting threshold or maximum consecutive skips.
    Returns a list of starving lane names.
    """
    starved_lanes = []
    # Check all configured lanes to ensure we validate starvation correctly
    for lane in config.VALID_LANES:
        wait_time = waiting_times.get(lane, 0.0)
        skips = consecutive_skips.get(lane, 0)
        
        is_starved = (
            wait_time >= config.STARVATION_THRESHOLD or
            skips >= config.MAX_CONSECUTIVE_SKIPS
        )
        if is_starved:
            starved_lanes.append(lane)
            
    return starved_lanes

def update_starvation_state(
    waiting_times: Dict[str, float],
    consecutive_skips: Dict[str, int],
    active_lane: str,
    elapsed_time: float,
    config: DecisionEngineConfig
) -> Tuple[Dict[str, float], Dict[str, int]]:
    """
    Updates internal waiting times and skips.
    - Resets active lane metrics to zero.
    - Increments wait times and skips for all other lanes.
    """
    new_waiting_times = dict(waiting_times)
    new_consecutive_skips = dict(consecutive_skips)

    for lane in config.VALID_LANES:
        if lane == active_lane:
            new_waiting_times[lane] = 0.0
            new_consecutive_skips[lane] = 0
        else:
            new_waiting_times[lane] = new_waiting_times.get(lane, 0.0) + elapsed_time
            new_consecutive_skips[lane] = new_consecutive_skips.get(lane, 0) + 1

    return new_waiting_times, new_consecutive_skips
