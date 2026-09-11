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
