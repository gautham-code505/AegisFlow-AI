"""
Unit tests for FallbackController.
"""

from models import Lane, SignalColor, SignalPhase
from safety.fallback import FallbackController, FALLBACK_SEQUENCE
from safety.conflicts import ConflictMatrix


def test_fallback_cycle_sequence():
    """Verify fallback controller cycles deterministically through NORTH -> EAST -> SOUTH -> WEST."""
    fb = FallbackController()
    start = 100.0

    # 1. Initial trigger -> NORTH GREEN
    s1 = fb.get_fallback_signal_state(start)
    assert s1.active_lane == Lane.NORTH
    assert s1.phase == SignalPhase.GREEN
    assert s1.north == SignalColor.GREEN

    # 2. Advance time past green duration (15s) -> YELLOW clearance
    s2 = fb.get_fallback_signal_state(start + 16.0)
    assert s2.active_lane == Lane.NORTH
    assert s2.phase == SignalPhase.YELLOW
    assert s2.north == SignalColor.YELLOW

    # 3. Advance time past yellow duration (3s) -> ALL_RED clearance
    s3 = fb.get_fallback_signal_state(start + 19.9)
    assert s3.phase == SignalPhase.ALL_RED
    assert s3.north == SignalColor.RED

    # 4. Advance time past all-red duration (2s) -> EAST GREEN
    s4 = fb.get_fallback_signal_state(start + 23.0)
    assert s4.active_lane == Lane.EAST
    assert s4.phase == SignalPhase.GREEN
    assert s4.east == SignalColor.GREEN


def test_fallback_conflict_free():
    """Verify all fallback states satisfy single-active-green conflict invariant."""
    fb = FallbackController()
    t = 100.0
    for step in range(20):
        state = fb.get_fallback_signal_state(t)
        assert ConflictMatrix.is_safe_signal_state(state) is True
        t += 5.0
