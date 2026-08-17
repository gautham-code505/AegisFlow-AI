"""
Unit tests for SignalDecision contract model.
"""

import pytest
from pydantic import ValidationError
from models import SignalDecision, Lane, Priority


def test_valid_signal_decision():
    """6. Test creating a valid SignalDecision model."""
    decision = SignalDecision(
        decision_id="dec-001",
        timestamp=12.0,
        selected_lane=Lane.NORTH,
        duration=30,
        priority=Priority.NORMAL,
        reasons=["North has highest vehicle density"],
        score_breakdown={"north": 0.85, "south": 0.20},
    )
    assert decision.decision_id == "dec-001"
    assert decision.timestamp == 12.0
    assert decision.selected_lane == Lane.NORTH
    assert decision.duration == 30
    assert decision.priority == Priority.NORMAL
    assert len(decision.reasons) == 1
    assert decision.score_breakdown["north"] == 0.85


def test_invalid_duration():
    """7. Test that duration <= 0 raises ValidationError."""
    with pytest.raises(ValidationError):
        SignalDecision(
            decision_id="dec-002",
            timestamp=12.0,
            selected_lane=Lane.SOUTH,
            duration=0,
        )

    with pytest.raises(ValidationError):
        SignalDecision(
            decision_id="dec-003",
            timestamp=12.0,
            selected_lane=Lane.SOUTH,
            duration=-10,
        )
