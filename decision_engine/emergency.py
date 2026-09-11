from typing import Optional, Tuple, List, Dict
from models import TrafficState

def check_emergency(state: TrafficState, scores: Optional[Dict[str, Tuple[float, Dict[str, float]]]] = None) -> Optional[Tuple[str, str, List[str]]]:
    """
    Checks if there is a valid active emergency vehicle detected in a lane.
    If so, returns a tuple: (emergency_lane_str, priority_level, reason_list)
    Otherwise returns None.
    """
    if state.emergency.detected and state.emergency.lane is not None:
        lane_str = state.emergency.lane.value
        
        # Build base reasons
        reasons = [
            f"Emergency vehicle ({state.emergency.vehicle_type or 'AMBULANCE'}) detected on {lane_str.capitalize()} approach",
            "Emergency priority overrides normal traffic demand",
            f"{lane_str.capitalize()} was selected for emergency preemption"
        ]
        
        if state.emergency.confidence:
            reasons[0] += f" (Confidence: {state.emergency.confidence * 100:.1f}%)"
            
        # Add score context if available
        if scores:
            lane_score = scores.get(lane_str, (0.0,))[0]
            # Find the lane that WOULD have won
            highest_lane = max(scores.keys(), key=lambda l: scores[l][0])
            highest_score = scores[highest_lane][0]
            
            if highest_lane != lane_str and highest_score > lane_score:
                reasons.append(
                    f"Highest demand was {highest_lane.capitalize()} ({highest_score:.2f}) vs {lane_str.capitalize()} ({lane_score:.2f}), but emergency takes absolute priority"
                )
            
        return lane_str, "EMERGENCY", reasons
    return None
