"""
Unit tests for modular safety rule evaluators.
"""

from models import TrafficState, SignalDecision, SignalState, Lane, SignalPhase, Priority
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
