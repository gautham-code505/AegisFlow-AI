from typing import Optional, Tuple, List
from .models import TrafficState

def check_emergency(state: TrafficState) -> Optional[Tuple[str, str, List[str]]]:
    """
    Checks if there is a valid active emergency vehicle detected in a lane.
    If so, returns a tuple: (emergency_lane, priority_level, reason_list)
    Otherwise returns None.
    """
    if state.emergency.detected and state.emergency.lane is not None:
        lane = state.emergency.lane
        reasons = [
            f"Emergency vehicle detected on {lane.capitalize()} approach",
            "Emergency priority activated"
        ]
        return lane, "emergency", reasons
    return None
