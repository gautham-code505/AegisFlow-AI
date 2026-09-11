import pytest
import time
from models import TrafficState, LaneState, Lane, EmergencyState, SignalDecision, SignalPhase, Priority
from backend.state_store import StateStore
from backend.orchestrator import Orchestrator
from backend.decision_adapter import DecisionEngineAdapter
from backend.websocket_manager import WebSocketManager
from controller import VirtualSignalController
from safety import SafetyValidator, FallbackController

@pytest.fixture
def orchestrator():
    state_store = StateStore()
    decision_adapter = DecisionEngineAdapter()
    ws_manager = WebSocketManager()
    safety_validator = SafetyValidator()
    
    # Configure controller for fast testing
    from controller.config import ControllerConfig
    config = ControllerConfig(MIN_GREEN_SECONDS=5, MAX_GREEN_SECONDS=30, YELLOW_SECONDS=3, ALL_RED_SECONDS=2)
    virtual_controller = VirtualSignalController(config=config)
    fallback_controller = FallbackController()
    
    return Orchestrator(
        state_store=state_store,
        decision_adapter=decision_adapter,
        websocket_manager=ws_manager,
        safety_validator=safety_validator,
        virtual_controller=virtual_controller,
        fallback_controller=fallback_controller,
    )

def test_measurement_lifecycle(orchestrator):
    state_store = orchestrator.state_store
    
    # 1. Provide initial TrafficState with tracking
    ts = TrafficState(
        timestamp=100.0,
        has_tracking_data=True,
        lanes={
            Lane.NORTH: LaneState(queued_vehicle_count=5, observed_average_wait=10.0, observed_max_wait=15.0),
            Lane.SOUTH: LaneState(queued_vehicle_count=3, observed_average_wait=5.0, observed_max_wait=8.0),
            Lane.EAST: LaneState(),
            Lane.WEST: LaneState()
        },
        emergency=EmergencyState()
    )
    state_store.set_traffic_state(ts)
    
    # Mock a decision
    decision = SignalDecision(
        decision_id="test-dec",
        timestamp=101.0,
        selected_lane=Lane.NORTH,
        duration=15,
        priority=Priority.NORMAL,
        reasons=["Test reason"]
    )
    state_store.set_decision(decision)
    
    # Time 102.0: Advance controller to start GREEN for North+South
    # Assuming initial state is ALL_RED, we execute the decision
    signal_state = orchestrator.virtual_controller.execute_decision(
        target_lane=[Lane.NORTH, Lane.SOUTH],
        duration=15,
        current_time=102.0
    )
    orchestrator._update_signal_state(signal_state, 102.0)
    
    # Verification: GREEN START should have created an active measurement
    assert orchestrator._active_measurement is not None
    assert orchestrator._active_measurement.start_timestamp == 102.0
    assert orchestrator._active_measurement.has_tracking_data is True
    assert orchestrator._active_measurement.queue_before == 8  # 5 + 3
    assert orchestrator._active_measurement.wait_avg_before == 7.5 # (10 + 5) / 2
    assert orchestrator._active_measurement.wait_max_before == 15.0
    assert orchestrator._active_measurement.priority_type == Priority.NORMAL
    
    # Verify no completed measurements yet
    assert len(state_store.get_measurements()) == 0
    
    # 2. Advance time during GREEN phase (nothing should happen to measurement)
    signal_state = orchestrator.virtual_controller.advance_time(110.0)
    orchestrator._update_signal_state(signal_state, 110.0)
    assert orchestrator._active_measurement is not None
    assert len(state_store.get_measurements()) == 0
    
    # Provide new TrafficState (traffic decreased)
    ts2 = TrafficState(
        timestamp=115.0,
        has_tracking_data=True,
        lanes={
            Lane.NORTH: LaneState(queued_vehicle_count=1, observed_average_wait=2.0, observed_max_wait=2.0),
            Lane.SOUTH: LaneState(queued_vehicle_count=0, observed_average_wait=0.0, observed_max_wait=0.0),
            Lane.EAST: LaneState(),
            Lane.WEST: LaneState()
        },
        emergency=EmergencyState()
    )
    state_store.set_traffic_state(ts2)
    
    # Mock a new decision for different lanes to trigger YELLOW transition
    decision2 = SignalDecision(
        decision_id="test-dec-end",
        timestamp=116.0,
        selected_lane=Lane.EAST,
        duration=10,
        priority=Priority.NORMAL
    )
    state_store.set_decision(decision2)
    
    # 3. Time 117.0: Execute decision for EAST+WEST, triggering YELLOW for North+South
    signal_state = orchestrator.virtual_controller.execute_decision(
        target_lane=[Lane.EAST, Lane.WEST],
        duration=10,
        current_time=117.0
    )
    orchestrator._update_signal_state(signal_state, 117.0)
    
    # Verification: GREEN END should close the measurement
    assert orchestrator._active_measurement is None
    measurements = state_store.get_measurements()
    assert len(measurements) == 1
    
    m = measurements[0]
    assert m.end_timestamp == 117.0
    assert m.green_duration == 15.0
    assert m.queue_after == 1
    assert m.wait_avg_after == 1.0 # (2.0 + 0.0) / 2
    assert m.wait_max_after == 2.0

def test_measurement_without_tracking(orchestrator):
    state_store = orchestrator.state_store
    
    ts = TrafficState(
        timestamp=200.0,
        has_tracking_data=False,
        lanes={
            Lane.NORTH: LaneState(vehicle_count=10),
            Lane.SOUTH: LaneState(vehicle_count=5),
            Lane.EAST: LaneState(),
            Lane.WEST: LaneState()
        },
        emergency=EmergencyState()
    )
    state_store.set_traffic_state(ts)
    
    decision = SignalDecision(
        decision_id="test-dec-2",
        timestamp=201.0,
        selected_lane=Lane.NORTH,
        duration=10,
        priority=Priority.NORMAL
    )
    state_store.set_decision(decision)
    
    # Start GREEN
    signal_state = orchestrator.virtual_controller.execute_decision(
        target_lane=[Lane.NORTH, Lane.SOUTH],
        duration=10,
        current_time=202.0
    )
    orchestrator._update_signal_state(signal_state, 202.0)
    
    assert orchestrator._active_measurement is not None
    assert orchestrator._active_measurement.has_tracking_data is False
    assert orchestrator._active_measurement.queue_before is None
    assert orchestrator._active_measurement.wait_avg_before is None
    
    # Mock new decision to end GREEN
    decision3 = SignalDecision(
        decision_id="test-dec-3",
        timestamp=211.0,
        selected_lane=Lane.EAST,
        duration=10,
        priority=Priority.NORMAL
    )
    state_store.set_decision(decision3)
    
    # End GREEN
    signal_state = orchestrator.virtual_controller.execute_decision(
        target_lane=[Lane.EAST, Lane.WEST],
        duration=10,
        current_time=212.0
    )
    orchestrator._update_signal_state(signal_state, 212.0)
    
    m = state_store.get_measurements()[0]
    assert m.has_tracking_data is False
    assert m.queue_after is None
    assert m.wait_avg_after is None
    assert m.green_duration == 10.0
