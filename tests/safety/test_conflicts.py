"""
Unit tests for ConflictMatrix and safe compatible phase group invariants.
"""

from models import Lane, SignalColor, SignalPhase, SignalState
from safety.conflicts import ConflictMatrix


def test_conflict_matrix_single_green_pass():
    """Verify single green on North satisfies conflict matrix invariant."""
    colors = {
        Lane.NORTH: SignalColor.GREEN,
        Lane.SOUTH: SignalColor.RED,
        Lane.EAST: SignalColor.RED,
        Lane.WEST: SignalColor.RED,
    }
    conflicts = ConflictMatrix.check_conflict(colors)
    assert len(conflicts) == 0


def test_conflict_matrix_concurrent_ns_green_pass():
    """Verify concurrent green on North + South satisfies conflict matrix invariant."""
    colors = {
        Lane.NORTH: SignalColor.GREEN,
        Lane.SOUTH: SignalColor.GREEN,
        Lane.EAST: SignalColor.RED,
        Lane.WEST: SignalColor.RED,
    }
    conflicts = ConflictMatrix.check_conflict(colors)
    assert len(conflicts) == 0


def test_conflict_matrix_concurrent_ew_green_pass():
    """Verify concurrent green on East + West satisfies conflict matrix invariant."""
    colors = {
        Lane.NORTH: SignalColor.RED,
        Lane.SOUTH: SignalColor.RED,
        Lane.EAST: SignalColor.GREEN,
        Lane.WEST: SignalColor.GREEN,
    }
    conflicts = ConflictMatrix.check_conflict(colors)
    assert len(conflicts) == 0


def test_conflict_matrix_perpendicular_conflicts_rejected():
    """Verify perpendicular conflicting combinations are rejected by ConflictMatrix."""
    # North + East
    c1 = ConflictMatrix.check_conflict({
        Lane.NORTH: SignalColor.GREEN,
        Lane.SOUTH: SignalColor.RED,
        Lane.EAST: SignalColor.GREEN,
        Lane.WEST: SignalColor.RED,
    })
    assert len(c1) == 1
    assert "SAFETY CONFLICT VIOLATION" in c1[0]

    # South + West
    c2 = ConflictMatrix.check_conflict({
        Lane.NORTH: SignalColor.RED,
        Lane.SOUTH: SignalColor.GREEN,
        Lane.EAST: SignalColor.RED,
        Lane.WEST: SignalColor.GREEN,
    })
    assert len(c2) == 1

    # North + West
    c3 = ConflictMatrix.check_conflict({
        Lane.NORTH: SignalColor.GREEN,
        Lane.SOUTH: SignalColor.RED,
        Lane.EAST: SignalColor.RED,
        Lane.WEST: SignalColor.GREEN,
    })
    assert len(c3) == 1

    # South + East
    c4 = ConflictMatrix.check_conflict({
        Lane.NORTH: SignalColor.RED,
        Lane.SOUTH: SignalColor.GREEN,
        Lane.EAST: SignalColor.GREEN,
        Lane.WEST: SignalColor.RED,
    })
    assert len(c4) == 1


def test_conflict_matrix_arbitrary_multi_green_rejected():
    """Verify 3-lane and 4-lane green combinations are rejected."""
    c_3 = ConflictMatrix.check_conflict({
        Lane.NORTH: SignalColor.GREEN,
        Lane.SOUTH: SignalColor.GREEN,
        Lane.EAST: SignalColor.GREEN,
        Lane.WEST: SignalColor.RED,
    })
    assert len(c_3) == 1

    c_4 = ConflictMatrix.check_conflict({
        Lane.NORTH: SignalColor.GREEN,
        Lane.SOUTH: SignalColor.GREEN,
        Lane.EAST: SignalColor.GREEN,
        Lane.WEST: SignalColor.GREEN,
    })
    assert len(c_4) == 1


def test_is_safe_signal_state():
    """Verify is_safe_signal_state helper on canonical SignalState."""
    # Safe concurrent NS state
    safe_state = SignalState(
        timestamp=1.0,
        north=SignalColor.GREEN,
        south=SignalColor.GREEN,
        east=SignalColor.RED,
        west=SignalColor.RED,
        active_lanes=[Lane.NORTH, Lane.SOUTH],
        phase=SignalPhase.GREEN,
    )
    assert ConflictMatrix.is_safe_signal_state(safe_state) is True

    # Unsafe conflicting state
    unsafe_state = SignalState(
        timestamp=1.0,
        north=SignalColor.GREEN,
        south=SignalColor.RED,
        east=SignalColor.GREEN,
        west=SignalColor.RED,
        active_lanes=[Lane.NORTH, Lane.EAST],
        phase=SignalPhase.GREEN,
    )
    assert ConflictMatrix.is_safe_signal_state(unsafe_state) is False
