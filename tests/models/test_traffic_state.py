"""
Unit tests for TrafficState, LaneState, and EmergencyState models.
"""

import pytest
from pydantic import ValidationError
from models import TrafficState, LaneState, EmergencyState, Lane


def test_valid_traffic_state():
    """1. Test creating a valid TrafficState with all 4 lanes."""
    ts = TrafficState(
        timestamp=10.5,
        frame_id=100,
        source="cam-01",
        lanes={
            Lane.NORTH: LaneState(vehicle_count=5, occupancy=0.4, pedestrian_count=2, heavy_vehicle_count=1),
            Lane.SOUTH: LaneState(vehicle_count=3, occupancy=0.2),
            Lane.EAST: LaneState(vehicle_count=0, occupancy=0.0),
            Lane.WEST: LaneState(vehicle_count=1, occupancy=0.05),
        },
        emergency=EmergencyState(detected=False),
    )
    assert ts.timestamp == 10.5
    assert ts.frame_id == 100
    assert ts.lanes[Lane.NORTH].vehicle_count == 5
    assert ts.lanes[Lane.NORTH].occupancy == 0.4
    assert ts.lanes[Lane.NORTH].pedestrian_count == 2
    assert ts.lanes[Lane.NORTH].heavy_vehicle_count == 1


def test_invalid_occupancy():
    """2. Test that occupancy > 1.0 or < 0.0 raises ValidationError."""
    with pytest.raises(ValidationError):
        LaneState(occupancy=1.5)

    with pytest.raises(ValidationError):
        LaneState(occupancy=-0.1)


def test_negative_vehicle_count():
    """3. Test that negative vehicle count raises ValidationError."""
    with pytest.raises(ValidationError):
        LaneState(vehicle_count=-1)

    with pytest.raises(ValidationError):
        LaneState(pedestrian_count=-5)

    with pytest.raises(ValidationError):
        LaneState(heavy_vehicle_count=-2)


def test_invalid_lane_name():
    """4. Test that invalid lane string raises ValidationError."""
    with pytest.raises(ValidationError):
        TrafficState(
            timestamp=1.0,
            lanes={
                "invalid_lane": LaneState(vehicle_count=1),
            },
        )


def test_emergency_state():
    """5. Test EmergencyState model initialization and lane binding."""
    em = EmergencyState(detected=True, lane=Lane.EAST, vehicle_type="AMBULANCE")
    assert em.detected is True
    assert em.lane == Lane.EAST
    assert em.vehicle_type == "AMBULANCE"
