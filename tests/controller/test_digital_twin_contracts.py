"""
AegisFlow AI - Digital Twin & Controller Visualization Contract Tests

Tests architectural invariants:
1. Controller state is determined from the authoritative wall clock when the controller's
   current state is evaluated. WebSocket client presence must never determine whether the
   controller can reach the correct state.
2. SignalState is the sole authoritative signal source (not SignalDecision or selected_lane).
3. target_lanes is controller-owned and tracks transition targets.
4. Emergency preemption follows the repository's actual transition pipeline.
5. remaining_seconds is mathematically derived from elapsed wall-clock time without accumulators.
"""

import pytest
import time
from models import (
    Lane,
    SignalColor,
    SignalPhase,
    SignalDecision,
    SignalState,
    TrafficState,
    LaneState,
    EmergencyState,
    Priority,
)
from controller import VirtualSignalController, ControllerConfig
from controller.state_machine import SignalStateMachine
from safety import SafetyValidator, ConflictMatrix, ValidationStatus
from backend.orchestrator import Orchestrator
from backend.state_store import StateStore
from backend.decision_adapter import DecisionEngineAdapter
from backend.websocket_manager import WebSocketManager
from decision_engine.engine import DecisionEngine
from decision_engine.config import DEFAULT_CONFIG


def test_controller_state_determined_from_wall_clock_independent_of_websocket_clients():
    """
    INVARIANT:
    Controller state is determined from the authoritative wall clock when the
    controller's current state is evaluated. WebSocket client presence must never
    determine whether the controller can reach the correct state.
    """
    config = ControllerConfig(
        MIN_GREEN_SECONDS=10,
        MAX_GREEN_SECONDS=60,
        YELLOW_SECONDS=3,
        ALL_RED_SECONDS=2,
    )
    vc = VirtualSignalController(config=config)
    t0 = 1000.0

    # 1. Controller is in NS GREEN
    vc.execute_decision(target_lane=[Lane.NORTH, Lane.SOUTH], duration=20, current_time=t0)
    s_green = vc.get_current_signal_state(t0)
    assert s_green.phase == SignalPhase.GREEN
    assert set(s_green.active_lanes) == {Lane.NORTH, Lane.SOUTH}

    # 2. Decision received to transition to EW -> initiates YELLOW clearance
    s_yellow = vc.execute_decision(target_lane=[Lane.EAST, Lane.WEST], duration=25, current_time=t0 + 10.0)
    assert s_yellow.phase == SignalPhase.YELLOW
    assert s_yellow.target_lanes == [Lane.EAST, Lane.WEST]
    assert s_yellow.remaining_seconds == 3

    # 3. Simulate passage of time with ZERO WebSocket clients connected.
    # No polling loop, no active connections.
    # When evaluated at t0 + 13.5s (3.5s after yellow began, 0.5s into 2s all-red):
    # Controller must reach ALL_RED clearance strictly derived from wall-clock time.
    s_all_red = vc.get_current_signal_state(t0 + 13.5)
    assert s_all_red.phase == SignalPhase.ALL_RED
    assert s_all_red.north == SignalColor.RED
    assert s_all_red.south == SignalColor.RED
    assert s_all_red.east == SignalColor.RED
    assert s_all_red.west == SignalColor.RED
    assert s_all_red.target_lanes == [Lane.EAST, Lane.WEST]
    assert s_all_red.remaining_seconds == 2  # 2 - int(13.5 - 13.0) = 2

    # 1.5s into all-red (t0 + 14.5s), remaining_seconds must be 1
    s_all_red_late = vc.get_current_signal_state(t0 + 14.5)
    assert s_all_red_late.remaining_seconds == 1

    # 4. When evaluated at t0 + 16.0s (6s after yellow began, 3s yellow + 2s red elapsed):
    # Controller must have autonomously reached target GREEN for [EAST, WEST].
    s_target_green = vc.get_current_signal_state(t0 + 16.0)
    assert s_target_green.phase == SignalPhase.GREEN
    assert set(s_target_green.active_lanes) == {Lane.EAST, Lane.WEST}
    assert s_target_green.east == SignalColor.GREEN
    assert s_target_green.west == SignalColor.GREEN
    assert s_target_green.north == SignalColor.RED
    assert s_target_green.south == SignalColor.RED
    assert s_target_green.target_lanes is None  # Transition complete


def test_signal_state_authoritative_source_independent_of_signal_decision():
    """
    INVARIANT:
    SignalState is the sole authoritative signal source for the Digital Twin.
    An AI decision recommendation does not alter the signal state until safety
    approves and the controller executes it.
    """
    config = ControllerConfig(MIN_GREEN_SECONDS=10, YELLOW_SECONDS=3, ALL_RED_SECONDS=2)
    vc = VirtualSignalController(config=config)
    now = 100.0

    # Current controller state is NORTH+SOUTH GREEN
    vc.execute_decision(target_lane=[Lane.NORTH, Lane.SOUTH], duration=30, current_time=now)
    current_state = vc.get_current_signal_state(now)
    assert current_state.phase == SignalPhase.GREEN
    assert set(current_state.active_lanes) == {Lane.NORTH, Lane.SOUTH}

    # Decision Engine proposes an invalid decision (duration exceeds MAX_GREEN_SECONDS and conflicting target_lanes)
    proposed_invalid_decision = SignalDecision(
        decision_id="dec-test-01",
        timestamp=now + 5.0,
        selected_lane=Lane.EAST,
        duration=120,  # Invalid: exceeds MAX_GREEN_SECONDS=60
        priority=Priority.NORMAL,
        reasons=["AI proposed duration too long"],
    )

    # State before execution MUST still be NORTH+SOUTH GREEN
    state_before = vc.get_current_signal_state(now + 5.0)
    assert state_before.phase == SignalPhase.GREEN
    assert set(state_before.active_lanes) == {Lane.NORTH, Lane.SOUTH}
    assert state_before.east == SignalColor.RED
    assert state_before.west == SignalColor.RED

    # SafetyValidator rejects the proposal due to duration bounds and conflicting lanes
    validator = SafetyValidator(config=config)
    val_result = validator.validate(
        current_signal_state=state_before,
        proposed_decision=proposed_invalid_decision,
        traffic_state=TrafficState(timestamp=now + 5.0),
        current_time=now + 5.0,
        target_lanes=[Lane.NORTH, Lane.EAST],  # Conflicting movements!
    )
    assert val_result.status == ValidationStatus.REJECTED
    assert val_result.approved is False

    # Since rejected, controller is NOT executed. Current state remains NORTH+SOUTH GREEN
    state_after_rejection = vc.get_current_signal_state(now + 5.0)
    assert state_after_rejection.phase == SignalPhase.GREEN
    assert set(state_after_rejection.active_lanes) == {Lane.NORTH, Lane.SOUTH}
    assert state_after_rejection.north == SignalColor.GREEN
    assert state_after_rejection.south == SignalColor.GREEN
    assert state_after_rejection.east == SignalColor.RED
    assert state_after_rejection.west == SignalColor.RED


def test_target_lanes_controller_lifecycle():
    """
    Verify target_lanes is controller-owned:
    - None during steady-state GREEN
    - Populated with target approaches during YELLOW and ALL_RED
    - Cleared to None upon reaching target GREEN
    """
    config = ControllerConfig(YELLOW_SECONDS=4, ALL_RED_SECONDS=2)
    sm = SignalStateMachine(config=config)
    t = 500.0

    # Steady-state GREEN
    sm.transition_to(SignalPhase.GREEN, active_lanes=[Lane.NORTH, Lane.SOUTH], duration=30, timestamp=t)
    state = sm.get_signal_state(t)
    assert state.target_lanes is None

    # Begin transition to EW -> YELLOW
    sm.transition_to(
        SignalPhase.YELLOW,
        active_lanes=[Lane.NORTH, Lane.SOUTH],
        duration=4,
        timestamp=t + 10.0,
        target_lanes=[Lane.EAST, Lane.WEST],
    )
    state = sm.get_signal_state(t + 10.0)
    assert state.phase == SignalPhase.YELLOW
    assert state.target_lanes == [Lane.EAST, Lane.WEST]

    # ALL_RED clearance
    sm.transition_to(
        SignalPhase.ALL_RED,
        active_lanes=[],
        duration=2,
        timestamp=t + 14.0,
        target_lanes=[Lane.EAST, Lane.WEST],
    )
    state = sm.get_signal_state(t + 14.0)
    assert state.phase == SignalPhase.ALL_RED
    assert state.target_lanes == [Lane.EAST, Lane.WEST]

    # Activate target GREEN
    sm.transition_to(
        SignalPhase.GREEN,
        active_lanes=[Lane.EAST, Lane.WEST],
        duration=25,
        timestamp=t + 16.0,
        target_lanes=None,
    )
    state = sm.get_signal_state(t + 16.0)
    assert state.phase == SignalPhase.GREEN
    assert state.target_lanes is None


def test_signal_colors_and_phases_exhaustive():
    """
    Verify signal light colors across all phases and corridors.
    """
    sm = SignalStateMachine()
    t = 100.0

    # ALL_RED
    sm.initialize(t)
    s = sm.get_signal_state(t)
    assert s.phase == SignalPhase.ALL_RED
    assert all(color == SignalColor.RED for color in [s.north, s.south, s.east, s.west])

    # NS GREEN
    sm.transition_to(SignalPhase.GREEN, active_lanes=[Lane.NORTH, Lane.SOUTH], duration=20, timestamp=t)
    s = sm.get_signal_state(t)
    assert s.north == SignalColor.GREEN
    assert s.south == SignalColor.GREEN
    assert s.east == SignalColor.RED
    assert s.west == SignalColor.RED

    # NS YELLOW
    sm.transition_to(SignalPhase.YELLOW, active_lanes=[Lane.NORTH, Lane.SOUTH], duration=3, timestamp=t + 20)
    s = sm.get_signal_state(t + 20)
    assert s.north == SignalColor.YELLOW
    assert s.south == SignalColor.YELLOW
    assert s.east == SignalColor.RED
    assert s.west == SignalColor.RED

    # EW GREEN
    sm.transition_to(SignalPhase.GREEN, active_lanes=[Lane.EAST, Lane.WEST], duration=20, timestamp=t + 25)
    s = sm.get_signal_state(t + 25)
    assert s.north == SignalColor.RED
    assert s.south == SignalColor.RED
    assert s.east == SignalColor.GREEN
    assert s.west == SignalColor.GREEN

    # Single Approach (e.g. Emergency East)
    sm.transition_to(SignalPhase.GREEN, active_lanes=[Lane.EAST], duration=15, timestamp=t + 50)
    s = sm.get_signal_state(t + 50)
    assert s.east == SignalColor.GREEN
    assert s.north == SignalColor.RED
    assert s.south == SignalColor.RED
    assert s.west == SignalColor.RED


@pytest.mark.anyio
async def test_emergency_preemption_actual_controller_sequence():
    """
    Verify the actual repository emergency preemption sequence:
    1. System is in NS GREEN.
    2. Emergency vehicle detected on EAST approach.
    3. DecisionEngine produces EMERGENCY decision for EAST.
    4. SafetyValidator validates and approves emergency preemption.
    5. VirtualSignalController transitions active NS through YELLOW clearance -> ALL_RED -> target GREEN.
    """
    from unittest.mock import patch

    state_store = StateStore()
    engine_adapter = DecisionEngineAdapter(DecisionEngine(DEFAULT_CONFIG))
    ws_manager = WebSocketManager()
    safety_val = SafetyValidator()
    vc = VirtualSignalController()

    orch = Orchestrator(
        state_store=state_store,
        decision_adapter=engine_adapter,
        websocket_manager=ws_manager,
        safety_validator=safety_val,
        virtual_controller=vc,
    )

    current_mock_time = 1000.0
    with patch("time.time", side_effect=lambda: current_mock_time):
        t0 = 1000.0
        # Setup initial NS green
        init_traffic = TrafficState(
            timestamp=t0,
            lanes={
                Lane.NORTH: LaneState(vehicle_count=10, occupancy=0.5),
                Lane.SOUTH: LaneState(vehicle_count=8, occupancy=0.4),
                Lane.EAST: LaneState(vehicle_count=2, occupancy=0.1),
                Lane.WEST: LaneState(vehicle_count=1, occupancy=0.05),
            },
        )
        await orch.process_traffic_state(init_traffic)
        s0 = orch.get_current_signal_state(t0)
        assert s0.phase == SignalPhase.GREEN
        assert set(s0.active_lanes) == {Lane.NORTH, Lane.SOUTH}

        # Emergency on East arrives at t0 + 15.0s
        t_emg = t0 + 15.0
        current_mock_time = t_emg
        emg_traffic = TrafficState(
            timestamp=t_emg,
            lanes={
                Lane.NORTH: LaneState(vehicle_count=10, occupancy=0.5),
                Lane.SOUTH: LaneState(vehicle_count=8, occupancy=0.4),
                Lane.EAST: LaneState(vehicle_count=2, occupancy=0.1),
                Lane.WEST: LaneState(vehicle_count=1, occupancy=0.05),
            },
            emergency=EmergencyState(detected=True, lane=Lane.EAST, vehicle_type="AMBULANCE"),
        )

        dec = await orch.process_traffic_state(emg_traffic)
        assert dec.selected_lane == Lane.EAST
        assert dec.priority == Priority.EMERGENCY

        # Controller initiates YELLOW clearance for currently active NS corridor
        s_yellow = orch.get_current_signal_state(t_emg)
        assert s_yellow.phase == SignalPhase.YELLOW
        assert set(s_yellow.active_lanes) == {Lane.NORTH, Lane.SOUTH}
        assert s_yellow.target_lanes == [Lane.EAST]

        # Advance to ALL_RED clearance (after 3s yellow)
        current_mock_time = t_emg + 3.5
        s_all_red = orch.get_current_signal_state(t_emg + 3.5)
        assert s_all_red.phase == SignalPhase.ALL_RED
        assert s_all_red.target_lanes == [Lane.EAST]

        # Advance to Emergency target GREEN (after 2s all-red)
        current_mock_time = t_emg + 5.5
        s_emg_green = orch.get_current_signal_state(t_emg + 5.5)
        assert s_emg_green.phase == SignalPhase.GREEN
        assert s_emg_green.active_lanes == [Lane.EAST]
        assert s_emg_green.east == SignalColor.GREEN
        assert s_emg_green.north == SignalColor.RED
        assert s_emg_green.south == SignalColor.RED
        assert s_emg_green.west == SignalColor.RED


def test_remaining_seconds_mathematical_derivation():
    """
    Verify remaining_seconds is calculated directly from system time without accumulators.
    """
    sm = SignalStateMachine(config=ControllerConfig(ALL_RED_SECONDS=5))
    t0 = 1000.0

    sm.transition_to(SignalPhase.ALL_RED, active_lanes=[], duration=5, timestamp=t0)
    assert sm.get_remaining_seconds(t0) == 5
    assert sm.get_remaining_seconds(t0 + 2.3) == 3
    assert sm.get_remaining_seconds(t0 + 4.9) == 1
    assert sm.get_remaining_seconds(t0 + 5.0) == 0
    assert sm.get_remaining_seconds(t0 + 10.0) == 0
