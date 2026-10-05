import pytest
import time
from models import SignalPhase, SystemMode, SystemStatus, Status, SourceType, VisionStatus, TrafficState, SignalDecision, Priority, Lane
from backend.state_store import StateStore
from backend.orchestrator import Orchestrator
from controller.virtual_controller import VirtualSignalController
from backend.decision_adapter import DecisionEngineAdapter
from backend.websocket_manager import WebSocketManager

def test_screenshot_bug_no_camera_forces_all_red():
    """
    Simulates the 'Screenshot Bug':
    1. System is in GREEN phase.
    2. Camera stops/disconnects (NO_INPUT).
    3. Controller should be forced to transition safely to ALL_RED.
    """
    state_store = StateStore()
    virt_ctrl = VirtualSignalController()
    
    # Fake being in GREEN phase for NORTH
    now = time.time()
    virt_ctrl.state_machine.transition_to(
        new_phase=SignalPhase.GREEN,
        active_lanes=[Lane.NORTH],
        duration=10,
        timestamp=now - 5.0  # 5 seconds elapsed
    )
    
    orch = Orchestrator(
        state_store=state_store,
        decision_adapter=DecisionEngineAdapter(),
        websocket_manager=WebSocketManager(),
        virtual_controller=virt_ctrl
    )
    
    # 1. State Store reflects active camera
    status = state_store.get_system_status()
    status.camera = SourceType.LIVE_CAMERA
    status.vision = VisionStatus.PROCESSING
    state_store.set_system_status(status)
    
    # 2. Add a recent traffic state so it's not stale
    state_store.set_traffic_state(TrafficState(timestamp=now))
    
    # Verify we are in GREEN
    sig_state = orch.get_current_signal_state(now)
    assert sig_state.phase == SignalPhase.GREEN
    assert Lane.NORTH in sig_state.active_lanes
    
    # 3. Simulate camera stopping
    status.camera = SourceType.NO_INPUT
    status.vision = VisionStatus.STOPPED
    state_store.set_system_status(status)
    state_store.clear_traffic_state()
    
    # 4. Fetch state, should trigger force_all_red (YELLOW clearance first)
    now += 1.0
    sig_state_yellow = orch.get_current_signal_state(now)
    assert sig_state_yellow.phase == SignalPhase.YELLOW
    
    # 5. Advance time past yellow duration
    now += virt_ctrl.config.YELLOW_SECONDS + 1.0
    sig_state_red = orch.get_current_signal_state(now)
    assert sig_state_red.phase == SignalPhase.ALL_RED
    assert sig_state_red.active_lanes == []

def test_stale_perception_forces_all_red():
    """
    Tests that if the TrafficState is stale (>3.0s), the system transitions to ALL_RED.
    """
    state_store = StateStore()
    virt_ctrl = VirtualSignalController()
    
    now = time.time()
    virt_ctrl.state_machine.transition_to(
        new_phase=SignalPhase.GREEN,
        active_lanes=[Lane.EAST],
        duration=10,
        timestamp=now - 5.0
    )
    
    orch = Orchestrator(
        state_store=state_store,
        decision_adapter=DecisionEngineAdapter(),
        websocket_manager=WebSocketManager(),
        virtual_controller=virt_ctrl
    )
    
    status = state_store.get_system_status()
    status.camera = SourceType.LIVE_CAMERA
    status.vision = VisionStatus.PROCESSING
    state_store.set_system_status(status)
    
    # Add a stale traffic state
    state_store.set_traffic_state(TrafficState(timestamp=now - 10.0))
    
    # Fetch state, should trigger force_all_red (YELLOW clearance first)
    sig_state_yellow = orch.get_current_signal_state(now)
    assert sig_state_yellow.phase == SignalPhase.YELLOW
