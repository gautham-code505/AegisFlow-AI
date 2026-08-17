"""
Unit tests for SignalState contract model.
"""

import pytest
from pydantic import ValidationError
from models import SignalState, Lane, SignalColor, SignalPhase


def test_valid_signal_state():
    """Test creating a valid single-lane SignalState model."""
    sig_state = SignalState(
        timestamp=15.0,
        north=SignalColor.GREEN,
        south=SignalColor.RED,
        east=SignalColor.RED,
        west=SignalColor.RED,
        active_lane=Lane.NORTH,
        phase=SignalPhase.GREEN,
        remaining_seconds=20,
    )
    assert sig_state.timestamp == 15.0
    assert sig_state.north == SignalColor.GREEN
    assert sig_state.south == SignalColor.RED
    assert sig_state.active_lane == Lane.NORTH
    assert sig_state.active_lanes == [Lane.NORTH]
    assert sig_state.phase == SignalPhase.GREEN
    assert sig_state.remaining_seconds == 20


def test_valid_concurrent_signal_state():
    """Test creating a valid concurrent multi-lane SignalState model."""
    sig_state = SignalState(
        timestamp=20.0,
        north=SignalColor.GREEN,
        south=SignalColor.GREEN,
        east=SignalColor.RED,
        west=SignalColor.RED,
        active_lanes=[Lane.NORTH, Lane.SOUTH],
        phase=SignalPhase.GREEN,
        remaining_seconds=25,
    )
    assert sig_state.active_lanes == [Lane.NORTH, Lane.SOUTH]
    assert sig_state.active_lane == Lane.NORTH  # Backward compatibility
    assert sig_state.north == SignalColor.GREEN
    assert sig_state.south == SignalColor.GREEN


def test_invalid_signal_color():
    """Test that an invalid signal color string raises ValidationError."""
    with pytest.raises(ValidationError):
        SignalState(
            timestamp=1.0,
            north="PURPLE",  # Invalid SignalColor
        )

    with pytest.raises(ValidationError):
        SignalState(
            timestamp=1.0,
            remaining_seconds=-5,  # Invalid remaining_seconds (<0)
        )
