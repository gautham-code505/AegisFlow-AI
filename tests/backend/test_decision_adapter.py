"""
Direct integration tests for DecisionEngineAdapter using Jayasuriya's actual DecisionEngine.
"""

from models import TrafficState, LaneState, EmergencyState, Lane, Priority
from backend.decision_adapter import DecisionEngineAdapter
from decision_engine import DecisionEngine


def test_decision_adapter_real_engine_normal():
    """Verify adapter translates TrafficState and invokes real Jayasuriya engine for normal occupancy."""
    real_engine = DecisionEngine()
    adapter = DecisionEngineAdapter(real_engine)

    state = TrafficState(
        timestamp=30.0,
        lanes={
            Lane.NORTH: LaneState(vehicle_count=20, occupancy=0.88),
            Lane.SOUTH: LaneState(vehicle_count=4, occupancy=0.15),
            Lane.EAST: LaneState(vehicle_count=2, occupancy=0.10),
            Lane.WEST: LaneState(vehicle_count=1, occupancy=0.05),
        },
    )

    decision = adapter.decide(state)

    assert decision.selected_lane == Lane.NORTH
    assert decision.duration > 0
    assert decision.priority == Priority.NORMAL
    assert len(decision.reasons) > 0
    assert decision.decision_id.startswith("dec-")


def test_decision_adapter_real_engine_emergency():
    """Verify adapter translates TrafficState and handles emergency override in real engine."""
    real_engine = DecisionEngine()
    adapter = DecisionEngineAdapter(real_engine)

    state = TrafficState(
        timestamp=60.0,
        lanes={
            Lane.NORTH: LaneState(vehicle_count=20, occupancy=0.88),
            Lane.SOUTH: LaneState(vehicle_count=4, occupancy=0.15),
            Lane.EAST: LaneState(vehicle_count=2, occupancy=0.10),
            Lane.WEST: LaneState(vehicle_count=1, occupancy=0.05),
        },
        emergency=EmergencyState(detected=True, lane=Lane.WEST),
    )

    decision = adapter.decide(state)

    assert decision.selected_lane == Lane.WEST
    assert decision.priority == Priority.EMERGENCY
