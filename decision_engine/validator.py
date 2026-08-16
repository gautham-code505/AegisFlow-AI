import logging
from typing import Any, Dict, List, Tuple, Union
from .models import TrafficState, LaneState, EmergencyState
from .config import DecisionConfig

logger = logging.getLogger(__name__)

def parse_boolean(val: Any) -> bool:
    """
    Parses a boolean value safely.
    Allows standard booleans and the strings 'true', 'false', 'True', 'False'.
    Raises ValueError on other types or invalid strings.
    """
    if val is None:
        raise ValueError("Boolean value cannot be None")
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        val_lower = val.strip().lower()
        if val_lower == "true":
            return True
        elif val_lower == "false":
            return False
        else:
            raise ValueError(f"Invalid boolean string: '{val}'")
    raise ValueError(f"Invalid boolean type: {type(val)}")

def validate_traffic_state(
    raw_data: Any,
    config: DecisionConfig
) -> Tuple[TrafficState, List[str]]:
    """
    Validates and sanitizes traffic state input.
    Ensures that the returned TrafficState is structurally correct and safe to process.
    If the data is completely corrupted or missing, returns a default fallback state.
    
    Returns:
        (TrafficState, list of warning/error messages)
    """
    warnings: List[str] = []

    # Safe fallback default construction
    def get_fallback_state() -> TrafficState:
        lanes = {
            lane: LaneState(vehicle_count=0, occupancy=0.0)
            for lane in config.VALID_LANES
        }
        emergency = EmergencyState(detected=False, lane=None)
        pedestrians = {lane: 0 for lane in config.VALID_LANES}
        return TrafficState(timestamp=0.0, lanes=lanes, emergency=emergency, pedestrians=pedestrians)

    if raw_data is None:
        warnings.append("Input traffic state is None. Using fallback state.")
        return get_fallback_state(), warnings

    # If raw_data is already a TrafficState, validate its components
    if isinstance(raw_data, TrafficState):
        data_dict = {
            "timestamp": raw_data.timestamp,
            "lanes": {
                lane: {"vehicle_count": state.vehicle_count, "occupancy": state.occupancy}
                for lane, state in raw_data.lanes.items()
            },
            "emergency": {
                "detected": raw_data.emergency.detected,
                "lane": raw_data.emergency.lane
            },
            "pedestrians": raw_data.pedestrians
        }
    elif isinstance(raw_data, dict):
        data_dict = raw_data
    else:
        warnings.append(f"Input traffic state must be a dict or TrafficState, got {type(raw_data)}. Using fallback state.")
        return get_fallback_state(), warnings

    # 1. Validate Timestamp
    timestamp = 0.0
    if "timestamp" in data_dict:
        try:
            timestamp = float(data_dict["timestamp"])
            if timestamp < 0:
                warnings.append(f"Negative timestamp {timestamp} detected, using 0.0.")
                timestamp = 0.0
        except (ValueError, TypeError):
            warnings.append(f"Invalid timestamp type {data_dict['timestamp']}, defaulting to 0.0.")
    else:
        warnings.append("Timestamp missing from traffic state, defaulting to 0.0.")

    # 2. Validate Lanes
    lanes_input = data_dict.get("lanes")
    validated_lanes: Dict[str, LaneState] = {}
    
    if not isinstance(lanes_input, dict):
        warnings.append("Lanes data is missing or is not a dictionary. Initializing all lanes with zeros.")
        lanes_input = {}

    for lane_name in config.VALID_LANES:
        lane_data = lanes_input.get(lane_name)
        
        # Default lane values if lane is missing or invalid type
        v_count = 0
        occupancy = 0.0

        if lane_data is None:
            warnings.append(f"Lane '{lane_name}' data missing, defaulting to zeros.")
        elif not isinstance(lane_data, dict):
            warnings.append(f"Lane '{lane_name}' data must be a dict, defaulting to zeros.")
        else:
            # Validate vehicle count
            raw_v_count = lane_data.get("vehicle_count")
            if raw_v_count is None:
                warnings.append(f"Lane '{lane_name}' vehicle_count missing, defaulting to 0.")
            else:
                try:
                    v_count_val = int(float(raw_v_count))
                    if v_count_val < 0:
                        warnings.append(f"Lane '{lane_name}' vehicle_count negative ({v_count_val}), clipping to 0.")
                        v_count = 0
                    else:
                        v_count = v_count_val
                except (ValueError, TypeError):
                    warnings.append(f"Lane '{lane_name}' vehicle_count invalid ({raw_v_count}), defaulting to 0.")
            
            # Validate occupancy
            raw_occupancy = lane_data.get("occupancy")
            if raw_occupancy is None:
                warnings.append(f"Lane '{lane_name}' occupancy missing, defaulting to 0.0.")
            else:
                try:
                    occ_val = float(raw_occupancy)
                    if occ_val < 0.0 or occ_val > 1.0:
                        clipped_occ = max(0.0, min(1.0, occ_val))
                        warnings.append(f"Lane '{lane_name}' occupancy {occ_val} out of range [0, 1], clipping to {clipped_occ}.")
                        occupancy = clipped_occ
                    else:
                        occupancy = occ_val
                except (ValueError, TypeError):
                    warnings.append(f"Lane '{lane_name}' occupancy invalid ({raw_occupancy}), defaulting to 0.0.")
        
        validated_lanes[lane_name] = LaneState(vehicle_count=v_count, occupancy=occupancy)

    # Warn about extra invalid lanes in input
    if isinstance(lanes_input, dict):
        for lane_name in lanes_input:
            if lane_name not in config.VALID_LANES:
                warnings.append(f"Ignored unknown lane '{lane_name}' in traffic state input.")

    # 3. Validate Emergency
    emergency_input = data_dict.get("emergency")
    detected = False
    emergency_lane = None

    if not isinstance(emergency_input, dict):
        warnings.append("Emergency data is missing or is not a dictionary. Defaulting to no emergency.")
    else:
        # Validate emergency detection flag with parse_boolean
        raw_detected = emergency_input.get("detected")
        try:
            detected = parse_boolean(raw_detected)
        except ValueError as e:
            warnings.append(f"Invalid boolean value for emergency detected: {raw_detected}. Defaulting to False. Error: {str(e)}")
            detected = False

        # Validate emergency lane
        raw_lane = emergency_input.get("lane")
        if detected:
            if raw_lane is None:
                warnings.append("Emergency detected but no lane specified. Disabling emergency override.")
                detected = False
            elif raw_lane not in config.VALID_LANES:
                warnings.append(f"Emergency detected in invalid lane '{raw_lane}'. Disabling emergency override.")
                detected = False
                emergency_lane = None
            else:
                emergency_lane = raw_lane
        else:
            # Even if not detected, we can validate or store None
            emergency_lane = raw_lane if raw_lane in config.VALID_LANES else None

    validated_emergency = EmergencyState(detected=detected, lane=emergency_lane)

    # 4. Validate Pedestrians
    pedestrians_input = data_dict.get("pedestrians")
    validated_pedestrians: Dict[str, int] = {}

    if pedestrians_input is not None:
        if not isinstance(pedestrians_input, dict):
            warnings.append("Pedestrians data provided but is not a dictionary. Treating all pedestrian demands as 0.")
            for lane in config.VALID_LANES:
                validated_pedestrians[lane] = 0
        else:
            for lane_name in config.VALID_LANES:
                p_count = 0
                raw_p_count = pedestrians_input.get(lane_name)
                if raw_p_count is not None:
                    try:
                        p_count_val = int(float(raw_p_count))
                        if p_count_val < 0:
                            warnings.append(f"Pedestrian count for lane '{lane_name}' negative ({p_count_val}), clipping to 0.")
                            p_count = 0
                        else:
                            p_count = p_count_val
                    except (ValueError, TypeError):
                        warnings.append(f"Pedestrian count for lane '{lane_name}' invalid ({raw_p_count}), defaulting to 0.")
                validated_pedestrians[lane_name] = p_count
    else:
        for lane in config.VALID_LANES:
            validated_pedestrians[lane] = 0

    return TrafficState(
        timestamp=timestamp,
        lanes=validated_lanes,
        emergency=validated_emergency,
        pedestrians=validated_pedestrians
    ), warnings
