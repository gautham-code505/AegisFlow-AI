import pytest
import time
from models import TrafficState, EmergencyState, LaneState, Lane, SystemStatus
from backend.state_store import StateStore

@pytest.fixture
def state_store():
    store = StateStore()
    return store

def create_mock_traffic_state(emergency_detected=False, timestamp=None):
    if timestamp is None:
        timestamp = time.time()
    return TrafficState(
        timestamp=timestamp,
        frame_id=1,
        source="test",
        has_tracking_data=False,
        lanes={
            Lane.NORTH: LaneState(),
            Lane.SOUTH: LaneState(),
            Lane.EAST: LaneState(),
            Lane.WEST: LaneState(),
        },
        emergency=EmergencyState(
            detected=emergency_detected,
            lane=Lane.NORTH if emergency_detected else None,
            vehicle_type="AMBULANCE" if emergency_detected else None,
            confidence=0.9 if emergency_detected else None
        )
    )

def test_single_frame_emergency_triggers_active_latch(state_store):
    state1 = create_mock_traffic_state(emergency_detected=True)
    state_store.set_traffic_state(state1)
    
    active_emg = state_store.get_active_emergency()
    assert active_emg is not None
    assert active_emg.detected is True

def test_overwriting_normal_frame_does_not_clear_active_emergency(state_store):
    # 1. Vision confirms emergency
    emg_state = create_mock_traffic_state(emergency_detected=True)
    state_store.set_traffic_state(emg_state)
    
    assert state_store.get_active_emergency() is not None
    
    # 2. Vision sends normal frame next
    normal_state = create_mock_traffic_state(emergency_detected=False)
    state_store.set_traffic_state(normal_state)
    
    # 3. Latch should still be active
    assert state_store.get_active_emergency() is not None
    
    # 4. State returned to scheduler should STILL have emergency woven in
    retrieved_state = state_store.get_traffic_state()
    assert retrieved_state.emergency.detected is True
    assert retrieved_state.emergency.lane == Lane.NORTH

def test_emergency_naturally_expires_after_timeout(state_store):
    emg_state = create_mock_traffic_state(emergency_detected=True)
    
    # Manually set a very short timeout
    state_store.set_active_emergency(emg_state.emergency, duration_seconds=0.1)
    
    assert state_store.get_active_emergency() is not None
    
    # Wait for expiration
    time.sleep(0.15)
    
    assert state_store.get_active_emergency() is None
    
    # Check that TrafficState no longer weaves it in
    normal_state = create_mock_traffic_state(emergency_detected=False)
    state_store.set_traffic_state(normal_state)
    retrieved_state = state_store.get_traffic_state()
    assert retrieved_state.emergency.detected is False
    assert retrieved_state.emergency.detected is False

def test_explicit_clear_removes_emergency(state_store):
    emg_state = create_mock_traffic_state(emergency_detected=True)
    state_store.set_traffic_state(emg_state)
    
    assert state_store.get_active_emergency() is not None
    
    state_store.clear_active_emergency()
    assert state_store.get_active_emergency() is None
    
    
    normal_state = create_mock_traffic_state(emergency_detected=False)
    state_store.set_traffic_state(normal_state)
    
    retrieved_state = state_store.get_traffic_state()
    assert retrieved_state.emergency.detected is False

def test_emergency_priority_flow():
    from decision_engine.engine import DecisionEngine
    from models import Priority, Lane, SignalDecision
    engine = DecisionEngine()
    
    # 1. State with emergency
    emg_state = create_mock_traffic_state(emergency_detected=True)
    
    # 2. Feed to decision engine
    decision = engine.decide(emg_state)
    
    # 3. Assert priority and lane mapping
    assert decision.priority == Priority.EMERGENCY
    assert decision.selected_lane == Lane.NORTH
    
    # 4. Assert that this is strictly a decision proposal, not a direct controller mutation
    assert isinstance(decision, SignalDecision)

@pytest.mark.asyncio
async def test_emergency_safety_path():
    from backend.decision_adapter import DecisionEngineAdapter
    from backend.websocket_manager import WebSocketManager
    from safety import SafetyValidator
    from controller import VirtualSignalController
    from backend.orchestrator import Orchestrator
    
    class MockSafetyValidator(SafetyValidator):
        def __init__(self):
            super().__init__()
            self.was_called = False
            self.last_decision = None
            
        def validate(self, current_signal_state, proposed_decision, *args, **kwargs):
            self.was_called = True
            self.last_decision = proposed_decision
            return super().validate(current_signal_state, proposed_decision, *args, **kwargs)

    class MockController(VirtualSignalController):
        def __init__(self):
            super().__init__()
            self.execute_called = False
            
        def execute_decision(self, *args, **kwargs):
            self.execute_called = True
            return super().execute_decision(*args, **kwargs)

    store = StateStore()
    adapter = DecisionEngineAdapter()
    ws = WebSocketManager()
    safety = MockSafetyValidator()
    controller = MockController()
    
    orch = Orchestrator(store, adapter, ws, safety, controller)
    
    emg_state = create_mock_traffic_state(emergency_detected=True)
    
    # Process through orchestrator
    await orch.process_traffic_state(emg_state)
    
    # 1. Produces Priority.EMERGENCY
    from models import Priority
    assert safety.last_decision.priority == Priority.EMERGENCY
    
    # 2. Passed through SafetyValidator
    assert safety.was_called
    
    # 3. VirtualController execute decision was only called because safety validator passed it (or rejected it),
    # meaning the architecture enforces clearance logic.
    assert controller.execute_called

