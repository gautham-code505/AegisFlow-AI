"""
Unit tests for modular safety rule evaluators.
"""

from models import TrafficState, SignalDecision, SignalState, Lane, SignalPhase, Priority, SignalColor
from controller.config import ControllerConfig
from safety.rules import (
    check_lane_validity,
    check_duration_bounds,
    check_traffic_data_freshness,
    check_decision_freshness,
    check_minimum_green_hold,
)


def test_lane_validity_rule():
    """Verify lane validity rule rejects None or invalid lane."""
    assert len(check_lane_validity(Lane.NORTH)) == 0
    assert len(check_lane_validity(None)) == 1


def test_duration_bounds_rule():
    """Verify duration bounds rule rejects duration <= 0 or > MAX_GREEN_SECONDS."""
    cfg = ControllerConfig(MAX_GREEN_SECONDS=60)
    assert len(check_duration_bounds(30, cfg)) == 0
    assert len(check_duration_bounds(0, cfg)) == 1
    assert len(check_duration_bounds(-5, cfg)) == 1
    assert len(check_duration_bounds(90, cfg)) == 1


def test_stale_traffic_data_rule():
    """Verify stale traffic data rule detects observations older than STALE_DATA_SECONDS."""
    cfg = ControllerConfig(STALE_DATA_SECONDS=5.0)
    now = 100.0

    fresh_ts = TrafficState(timestamp=98.0)
    assert len(check_traffic_data_freshness(fresh_ts, now, cfg)) == 0

    stale_ts = TrafficState(timestamp=90.0)
    assert len(check_traffic_data_freshness(stale_ts, now, cfg)) == 1


def test_stale_decision_rule():
    """Verify stale decision rule detects decisions older than DECISION_TIMEOUT_SECONDS."""
    cfg = ControllerConfig(DECISION_TIMEOUT_SECONDS=5.0)
    now = 100.0

    fresh_dec = SignalDecision(
        decision_id="d1", timestamp=97.0, selected_lane=Lane.NORTH, duration=20
    )
    assert len(check_decision_freshness(fresh_dec, now, cfg)) == 0

    stale_dec = SignalDecision(
        decision_id="d2", timestamp=80.0, selected_lane=Lane.NORTH, duration=20
    )
    assert len(check_decision_freshness(stale_dec, now, cfg)) == 1


def _mock_signal_state(lane: Lane, phase: SignalPhase = SignalPhase.GREEN) -> SignalState:
    return SignalState(
        timestamp=100.0,
        north=SignalColor.GREEN if lane == Lane.NORTH else SignalColor.RED,
        south=SignalColor.GREEN if lane == Lane.SOUTH else SignalColor.RED,
        east=SignalColor.GREEN if lane == Lane.EAST else SignalColor.RED,
        west=SignalColor.GREEN if lane == Lane.WEST else SignalColor.RED,
        active_lanes=[lane],
        active_lane=lane,
        phase=phase,
        remaining_seconds=20,
    )

def test_minimum_green_prevents_preemption_at_t0():
    """T1: At phase age 0, competing non-emergency decision is rejected."""
    cfg = ControllerConfig(MIN_GREEN_SECONDS=10)
    state = _mock_signal_state(Lane.NORTH)
    errors = check_minimum_green_hold(state, Lane.EAST, phase_elapsed_seconds=0.0, config=cfg)
    assert len(errors) == 1

def test_minimum_green_prevents_preemption_below_threshold():
    """T2: At MIN_GREEN - epsilon, competing decision is rejected."""
    cfg = ControllerConfig(MIN_GREEN_SECONDS=10)
    state = _mock_signal_state(Lane.NORTH)
    errors = check_minimum_green_hold(state, Lane.EAST, phase_elapsed_seconds=9.9, config=cfg)
    assert len(errors) == 1

def test_minimum_green_allows_preemption_at_exact_threshold():
    """T3: At exactly MIN_GREEN, competing decision is allowed to proceed."""
    cfg = ControllerConfig(MIN_GREEN_SECONDS=10)
    state = _mock_signal_state(Lane.NORTH)
    errors = check_minimum_green_hold(state, Lane.EAST, phase_elapsed_seconds=10.0, config=cfg)
    assert len(errors) == 0

def test_minimum_green_allows_preemption_above_threshold():
    """T4: Above MIN_GREEN, competing decision is allowed."""
    cfg = ControllerConfig(MIN_GREEN_SECONDS=10)
    state = _mock_signal_state(Lane.NORTH)
    errors = check_minimum_green_hold(state, Lane.EAST, phase_elapsed_seconds=15.0, config=cfg)
    assert len(errors) == 0

def test_minimum_green_same_phase_not_subject_to_rule():
    """T5: Same-phase re-decision is not treated as a minimum-green preemption."""
    cfg = ControllerConfig(MIN_GREEN_SECONDS=10)
    state = _mock_signal_state(Lane.NORTH)
    # Target is also NORTH, phase elapsed is 2.0 (below min green)
    errors = check_minimum_green_hold(state, Lane.NORTH, phase_elapsed_seconds=2.0, config=cfg)
    assert len(errors) == 0

def test_minimum_green_uses_phase_start_time_not_snapshot_timestamp():
    """T11: Minimum-green behavior uses actual elapsed phase age, not SignalState.timestamp."""
    cfg = ControllerConfig(MIN_GREEN_SECONDS=10)
    state = _mock_signal_state(Lane.NORTH)
    state.timestamp = 999.0 # Snapshot time
    # If phase_elapsed_seconds wasn't used, this test would fail if logic was broken.
    # The rule is solely based on phase_elapsed_seconds now.
    errors = check_minimum_green_hold(state, Lane.EAST, phase_elapsed_seconds=5.0, config=cfg)
    assert len(errors) == 1
