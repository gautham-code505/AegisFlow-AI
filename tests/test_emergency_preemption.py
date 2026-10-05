import pytest
import time
from models import TrafficState, LaneState, Lane, EmergencyState, Priority
from backend.decision_adapter import DecisionEngineAdapter
from decision_engine.engine import DecisionEngine
from decision_engine.config import DEFAULT_CONFIG

@pytest.fixture
def engine():
    base_engine = DecisionEngine(DEFAULT_CONFIG)
    return DecisionEngineAdapter(base_engine)

def test_normal_traffic_highest_demand(engine):
    state = TrafficState(
        timestamp=time.time(),
        lanes={
            Lane.NORTH: LaneState(occupancy=0.9, vehicle_count=10),
            Lane.SOUTH: LaneState(occupancy=0.5, vehicle_count=5),
            Lane.EAST: LaneState(occupancy=0.2, vehicle_count=2),
            Lane.WEST: LaneState(occupancy=0.1, vehicle_count=1)
        }
    )
    decision = engine.decide(state)
    assert decision.selected_lane == Lane.NORTH
    assert decision.priority == Priority.NORMAL

def test_emergency_north_wins(engine):
    state = TrafficState(
        timestamp=time.time(),
        lanes={
            Lane.NORTH: LaneState(occupancy=0.1, vehicle_count=1),
            Lane.SOUTH: LaneState(occupancy=0.9, vehicle_count=15),
            Lane.EAST: LaneState(occupancy=0.8, vehicle_count=12),
            Lane.WEST: LaneState(occupancy=0.7, vehicle_count=10)
        },
        emergency=EmergencyState(detected=True, lane=Lane.NORTH, vehicle_type="AMBULANCE")
    )
    decision = engine.decide(state)
    assert decision.selected_lane == Lane.NORTH
    assert decision.priority == Priority.EMERGENCY
    assert "Emergency priority overrides normal traffic demand" in decision.reasons[1]
    
def test_emergency_south_wins(engine):
    state = TrafficState(
        timestamp=time.time(),
        lanes={
            Lane.NORTH: LaneState(occupancy=0.9, vehicle_count=15),
            Lane.SOUTH: LaneState(occupancy=0.1, vehicle_count=1),
            Lane.EAST: LaneState(occupancy=0.8, vehicle_count=12),
            Lane.WEST: LaneState(occupancy=0.7, vehicle_count=10)
        },
        emergency=EmergencyState(detected=True, lane=Lane.SOUTH, vehicle_type="AMBULANCE")
    )
    decision = engine.decide(state)
    assert decision.selected_lane == Lane.SOUTH
    assert decision.priority == Priority.EMERGENCY

def test_emergency_east_wins(engine):
    state = TrafficState(
        timestamp=time.time(),
        lanes={
            Lane.NORTH: LaneState(occupancy=0.9, vehicle_count=15),
            Lane.SOUTH: LaneState(occupancy=0.8, vehicle_count=12),
            Lane.EAST: LaneState(occupancy=0.1, vehicle_count=1),
            Lane.WEST: LaneState(occupancy=0.7, vehicle_count=10)
        },
        emergency=EmergencyState(detected=True, lane=Lane.EAST, vehicle_type="AMBULANCE")
    )
    decision = engine.decide(state)
    assert decision.selected_lane == Lane.EAST
    assert decision.priority == Priority.EMERGENCY

def test_emergency_west_wins(engine):
    state = TrafficState(
        timestamp=time.time(),
        lanes={
            Lane.NORTH: LaneState(occupancy=0.9, vehicle_count=15),
            Lane.SOUTH: LaneState(occupancy=0.8, vehicle_count=12),
            Lane.EAST: LaneState(occupancy=0.7, vehicle_count=10),
            Lane.WEST: LaneState(occupancy=0.1, vehicle_count=1)
        },
        emergency=EmergencyState(detected=True, lane=Lane.WEST, vehicle_type="AMBULANCE")
    )
    decision = engine.decide(state)
    assert decision.selected_lane == Lane.WEST
    assert decision.priority == Priority.EMERGENCY

def test_emergency_clear_resumes_normal_control(engine):
    # Setup Emergency
    state_emg = TrafficState(
        timestamp=time.time(),
        lanes={
            Lane.NORTH: LaneState(occupancy=0.9, vehicle_count=15),
            Lane.EAST: LaneState(occupancy=0.1, vehicle_count=1),
            Lane.SOUTH: LaneState(occupancy=0.0, vehicle_count=0),
            Lane.WEST: LaneState(occupancy=0.0, vehicle_count=0)
        },
        emergency=EmergencyState(detected=True, lane=Lane.EAST, vehicle_type="AMBULANCE")
    )
    dec1 = engine.decide(state_emg)
    assert dec1.selected_lane == Lane.EAST
    
    # Emergency Cleared -> Normal Traffic rules apply
    state_norm = TrafficState(
        timestamp=time.time() + 10,
        lanes={
            Lane.NORTH: LaneState(occupancy=0.9, vehicle_count=15),
            Lane.EAST: LaneState(occupancy=0.1, vehicle_count=1),
            Lane.SOUTH: LaneState(occupancy=0.0, vehicle_count=0),
            Lane.WEST: LaneState(occupancy=0.0, vehicle_count=0)
        },
        emergency=EmergencyState(detected=False)
    )
    dec2 = engine.decide(state_norm)
    assert dec2.selected_lane == Lane.NORTH
    assert dec2.priority == Priority.NORMAL
