"""
Unit tests for canonical safe phase groups and compatibility checker.
"""

from models import Lane, TrafficState, LaneState
from safety.phase_groups import (
    PHASE_NS,
    PHASE_EW,
    PHASE_ALL_RED,
    is_compatible,
    get_phase_group,
    get_compatible_phase_for_lane,
    evaluate_phase_demand,
    get_safe_phases,
)


def test_safe_phase_definitions():
    """Verify canonical phase group green and red lane definitions."""
    assert PHASE_NS.name == "NORTH_SOUTH"
    assert PHASE_NS.green_lanes == {Lane.NORTH, Lane.SOUTH}
    assert PHASE_NS.red_lanes == {Lane.EAST, Lane.WEST}

    assert PHASE_EW.name == "EAST_WEST"
    assert PHASE_EW.green_lanes == {Lane.EAST, Lane.WEST}
    assert PHASE_EW.red_lanes == {Lane.NORTH, Lane.SOUTH}

    assert PHASE_ALL_RED.name == "ALL_RED"
    assert len(PHASE_ALL_RED.green_lanes) == 0
    assert len(PHASE_ALL_RED.red_lanes) == 4


def test_is_compatible_allowed_groups():
    """Verify is_compatible returns True for explicitly permitted safe phase groups."""
    # Dual approach corridors
    assert is_compatible({Lane.NORTH, Lane.SOUTH}) is True
    assert is_compatible({Lane.EAST, Lane.WEST}) is True

    # Single approach phases (emergency/special)
    assert is_compatible({Lane.NORTH}) is True
    assert is_compatible({Lane.SOUTH}) is True
    assert is_compatible({Lane.EAST}) is True
    assert is_compatible({Lane.WEST}) is True

    # All-red clearance
    assert is_compatible(set()) is True


def test_is_compatible_rejected_conflicting_combinations():
    """Verify is_compatible returns False for conflicting approach combinations."""
    # Conflicting perpendicular pairs
    assert is_compatible({Lane.NORTH, Lane.EAST}) is False
    assert is_compatible({Lane.NORTH, Lane.WEST}) is False
    assert is_compatible({Lane.SOUTH, Lane.EAST}) is False
    assert is_compatible({Lane.SOUTH, Lane.WEST}) is False

    # 3-lane combinations
    assert is_compatible({Lane.NORTH, Lane.SOUTH, Lane.EAST}) is False
    assert is_compatible({Lane.NORTH, Lane.EAST, Lane.WEST}) is False

    # 4-lane all-green combination
    assert is_compatible({Lane.NORTH, Lane.SOUTH, Lane.EAST, Lane.WEST}) is False


def test_get_compatible_phase_for_lane():
    """Verify lane to compatible corridor phase mapping."""
    assert get_compatible_phase_for_lane(Lane.NORTH) == PHASE_NS
    assert get_compatible_phase_for_lane(Lane.SOUTH) == PHASE_NS
    assert get_compatible_phase_for_lane(Lane.EAST) == PHASE_EW
    assert get_compatible_phase_for_lane(Lane.WEST) == PHASE_EW


def test_get_phase_group_by_name():
    """Verify retrieving phase groups by name."""
    assert get_phase_group("NORTH_SOUTH") == PHASE_NS
    assert get_phase_group("north-south") == PHASE_NS
    assert get_phase_group("EAST_WEST") == PHASE_EW
    assert get_phase_group("ALL_RED") == PHASE_ALL_RED
    assert get_phase_group("INVALID_PHASE") is None


def test_evaluate_phase_demand():
    """Verify calculating demand scores for NS and EW corridors."""
    ts = TrafficState(
        timestamp=10.0,
        lanes={
            Lane.NORTH: LaneState(vehicle_count=10, occupancy=0.5),
            Lane.SOUTH: LaneState(vehicle_count=8, occupancy=0.4),
            Lane.EAST: LaneState(vehicle_count=2, occupancy=0.1),
            Lane.WEST: LaneState(vehicle_count=1, occupancy=0.05),
        },
    )
    scores = evaluate_phase_demand(ts)
    assert scores["NORTH_SOUTH"] > scores["EAST_WEST"]
