"""
AegisFlow AI - Safety Rules Evaluator

Modular safety rule functions validating proposed signal decisions and system state.
"""

from typing import List, Optional
from models import TrafficState, SignalDecision, SignalState, Lane, SignalPhase
from controller.config import ControllerConfig, DEFAULT_CONTROLLER_CONFIG
from .conflicts import ConflictMatrix


def check_lane_validity(selected_lane: Optional[Lane]) -> List[str]:
    """Rule 9: Validates lane selection enum."""
    errors: List[str] = []
    if selected_lane is None or selected_lane not in Lane:
        errors.append("Invalid or missing lane selection in signal decision.")
    return errors


def check_duration_bounds(
    duration: int,
    config: ControllerConfig = DEFAULT_CONTROLLER_CONFIG
) -> List[str]:
    """Rule 10: Validates green duration bounds."""
    errors: List[str] = []
    if duration <= 0:
        errors.append(f"Invalid duration ({duration}s). Green duration must be strictly positive.")
    elif duration > config.MAX_GREEN_SECONDS:
        errors.append(f"Duration ({duration}s) exceeds maximum allowed green limit ({config.MAX_GREEN_SECONDS}s).")
    return errors


def check_traffic_data_freshness(
    traffic_state: Optional[TrafficState],
    current_time: float,
    config: ControllerConfig = DEFAULT_CONTROLLER_CONFIG,
) -> List[str]:
    """Rule 7: Validates TrafficState observation age."""
    errors: List[str] = []
    if not traffic_state:
        errors.append("Missing TrafficState observation.")
        return errors

    age = current_time - traffic_state.timestamp
    if age > config.STALE_DATA_SECONDS:
        errors.append(f"Stale TrafficState detected (age={age:.1f}s > threshold={config.STALE_DATA_SECONDS}s).")
    elif age < -5.0:  # Clock skew check
        errors.append(f"Invalid future TrafficState timestamp detected (age={age:.1f}s).")
    return errors


def check_decision_freshness(
    decision: Optional[SignalDecision],
    current_time: float,
    config: ControllerConfig = DEFAULT_CONTROLLER_CONFIG,
) -> List[str]:
    """Rule 8: Validates SignalDecision timestamp age."""
    errors: List[str] = []
    if not decision:
        errors.append("Missing SignalDecision recommendation.")
        return errors

    age = current_time - decision.timestamp
    if age > config.DECISION_TIMEOUT_SECONDS:
        errors.append(f"Stale SignalDecision detected (age={age:.1f}s > threshold={config.DECISION_TIMEOUT_SECONDS}s).")
    return errors


def check_minimum_green_hold(
    current_signal_state: SignalState,
    proposed_lane: Lane,
    phase_elapsed_seconds: Optional[float] = None,
    config: ControllerConfig = DEFAULT_CONTROLLER_CONFIG,
) -> List[str]:
    """Rule 4: Ensures active GREEN phase is held for at least MIN_GREEN_SECONDS."""
    errors: List[str] = []
    if (
        current_signal_state.phase == SignalPhase.GREEN
        and current_signal_state.active_lane is not None
        and current_signal_state.active_lane != proposed_lane
        and phase_elapsed_seconds is not None
    ):
        if phase_elapsed_seconds < config.MIN_GREEN_SECONDS:
            errors.append(
                f"Minimum green hold restriction active for approach '{current_signal_state.active_lane.value.upper()}'. "
                f"Cannot preempt before minimum green duration ({config.MIN_GREEN_SECONDS}s) completes "
                f"(current elapsed: {phase_elapsed_seconds:.1f}s)."
            )
    return errors
