"""
Unit tests for SafetyValidator service.
"""

from models import TrafficState, SignalDecision, Lane, Priority
from safety.validator import SafetyValidator
from safety.models import ValidationStatus


def test_validator_approved_valid_decision():
    """Verify SafetyValidator approves a valid SignalDecision."""
    validator = SafetyValidator()
    now = 100.0

    ts = TrafficState(timestamp=99.0)
    dec = SignalDecision(
        decision_id="dec-100",
        timestamp=99.0,
        selected_lane=Lane.NORTH,
        duration=25,
        priority=Priority.NORMAL,
    )

    res = validator.validate(
        current_signal_state=None,
        proposed_decision=dec,
        traffic_state=ts,
        current_time=now,
    )

    assert res.approved is True
    assert res.status == ValidationStatus.APPROVED
    assert res.proposed_lane == Lane.NORTH
    assert res.proposed_duration == 25


def test_validator_rejected_invalid_duration():
    """Verify SafetyValidator rejects decision with duration <= 0."""
    validator = SafetyValidator()
    now = 100.0

    ts = TrafficState(timestamp=99.0)
    dec = SignalDecision(
        decision_id="dec-bad",
        timestamp=99.0,
        selected_lane=Lane.EAST,
        duration=25,
    )
    # Mutate duration to invalid
    dec.duration = 0

    res = validator.validate(
        current_signal_state=None,
        proposed_decision=dec,
        traffic_state=ts,
        current_time=now,
    )

    assert res.approved is False
    assert res.status == ValidationStatus.REJECTED


def test_validator_fallback_stale_traffic_data():
    """Verify SafetyValidator returns FALLBACK when TrafficState is stale."""
    validator = SafetyValidator()
    now = 100.0

    stale_ts = TrafficState(timestamp=80.0)
    dec = SignalDecision(
        decision_id="dec-stale",
        timestamp=99.0,
        selected_lane=Lane.SOUTH,
        duration=20,
    )

    res = validator.validate(
        current_signal_state=None,
        proposed_decision=dec,
        traffic_state=stale_ts,
        current_time=now,
    )

    assert res.approved is False
    assert res.status == ValidationStatus.FALLBACK


def test_validator_approved_valid_target_lanes():
    """Verify SafetyValidator approves valid target lanes like [NORTH, SOUTH]."""
    validator = SafetyValidator()
    now = 100.0
    ts = TrafficState(timestamp=99.0)
    dec = SignalDecision(decision_id="dec", timestamp=99.0, selected_lane=Lane.NORTH, duration=25)
    
    res = validator.validate(
        current_signal_state=None,
        proposed_decision=dec,
        traffic_state=ts,
        current_time=now,
        target_lanes=[Lane.NORTH, Lane.SOUTH]
    )
    
    assert res.approved is True
    assert res.status == ValidationStatus.APPROVED


def test_validator_rejected_conflicting_target_lanes():
    """Verify SafetyValidator rejects conflicting target lanes like [NORTH, EAST]."""
    validator = SafetyValidator()
    now = 100.0
    ts = TrafficState(timestamp=99.0)
    dec = SignalDecision(decision_id="dec", timestamp=99.0, selected_lane=Lane.NORTH, duration=25)
    
    res = validator.validate(
        current_signal_state=None,
        proposed_decision=dec,
        traffic_state=ts,
        current_time=now,
        target_lanes=[Lane.NORTH, Lane.EAST]
    )
    
    assert res.approved is False
    assert res.status == ValidationStatus.REJECTED
    assert any("SAFETY CONFLICT VIOLATION" in reason for reason in res.reasons)

def test_phase_elapsed_accessible_to_safety_validation():
    """T12: The real validator call path receives and uses phase elapsed information."""
    from models import SignalState, SignalColor, SignalPhase
    from controller.config import ControllerConfig
    validator = SafetyValidator(config=ControllerConfig(MIN_GREEN_SECONDS=10))
    now = 100.0
    ts = TrafficState(timestamp=99.0)
    
    # Simulate a competing decision for EAST
    dec = SignalDecision(decision_id="dec", timestamp=99.0, selected_lane=Lane.EAST, duration=25)
    
    # Simulate current controller state is NORTH GREEN
    state = SignalState(
        timestamp=99.0,
        north=SignalColor.GREEN,
        south=SignalColor.RED,
        east=SignalColor.RED,
        west=SignalColor.RED,
        active_lanes=[Lane.NORTH],
        active_lane=Lane.NORTH,
        phase=SignalPhase.GREEN,
        remaining_seconds=20,
    )
    
    # 1. Provide phase_elapsed_seconds < MIN_GREEN_SECONDS
    res1 = validator.validate(
        current_signal_state=state,
        proposed_decision=dec,
        traffic_state=ts,
        current_time=now,
        target_lanes=[Lane.EAST],
        phase_elapsed_seconds=5.0 # < 10
    )
    assert res1.approved is False
    assert res1.status == ValidationStatus.REJECTED
    assert any("Minimum green hold restriction" in r for r in res1.reasons)
    
    # 2. Provide phase_elapsed_seconds >= MIN_GREEN_SECONDS
    res2 = validator.validate(
        current_signal_state=state,
        proposed_decision=dec,
        traffic_state=ts,
        current_time=now,
        target_lanes=[Lane.EAST],
        phase_elapsed_seconds=15.0 # >= 10
    )
    assert res2.approved is True
    assert res2.status == ValidationStatus.APPROVED
