import logging
from typing import Any, List, Tuple
from models import TrafficState, LaneState, EmergencyState, Lane
from .config import DecisionEngineConfig

logger = logging.getLogger(__name__)

def validate_traffic_state(
    raw_data: Any,
    config: DecisionEngineConfig
) -> Tuple[TrafficState, List[str]]:
    """
    Validates and sanitizes traffic state input using the canonical Pydantic model.
    """
    warnings: List[str] = []

    # Safe fallback default construction
    def get_fallback_state() -> TrafficState:
        lanes = {
            Lane(lane): LaneState(vehicle_count=0, occupancy=0.0)
            for lane in config.VALID_LANES
        }
        emergency = EmergencyState(detected=False, lane=None)
        return TrafficState(timestamp=0.0, lanes=lanes, emergency=emergency)

    if raw_data is None:
        warnings.append("Input traffic state is None. Using fallback state.")
        return get_fallback_state(), warnings

    if isinstance(raw_data, TrafficState):
        state = raw_data
    elif isinstance(raw_data, dict):
        # Sanitize emergency lane string
        emer_data = raw_data.get("emergency")
        if isinstance(emer_data, dict):
            lane_val = emer_data.get("lane")
            if lane_val and lane_val not in config.VALID_LANES:
                warnings.append(f"Emergency detected in invalid lane '{lane_val}'. Disabling emergency override.")
                emer_data["lane"] = None
                emer_data["detected"] = False
        
        # Sanitize lanes keys
        lanes_data = raw_data.get("lanes")
        if isinstance(lanes_data, dict):
            valid_lanes_data = {}
            for k, v in lanes_data.items():
                if k in config.VALID_LANES:
                    valid_lanes_data[k] = v
                else:
                    warnings.append(f"Ignored unknown lane '{k}' in traffic state input.")
            raw_data["lanes"] = valid_lanes_data

        try:
            state = TrafficState(**raw_data)
        except Exception as e:
            warnings.append(f"Pydantic validation failed: {str(e)}. Using fallback state.")
            return get_fallback_state(), warnings
    else:
        warnings.append(f"Input traffic state must be a dict or TrafficState, got {type(raw_data)}. Using fallback state.")
        return get_fallback_state(), warnings

    # Ensure all configured lanes exist in the state, if not, add default
    for lane_str in config.VALID_LANES:
        try:
            lane_enum = Lane(lane_str)
            if lane_enum not in state.lanes:
                warnings.append(f"Lane '{lane_str}' missing from traffic state, adding default.")
                state.lanes[lane_enum] = LaneState()
        except ValueError:
            warnings.append(f"Configured lane '{lane_str}' is not a valid Lane enum.")

    return state, warnings

