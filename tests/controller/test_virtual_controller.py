"""
Unit tests for VirtualSignalController and SignalStateMachine.
"""

from models import Lane, SignalColor, SignalPhase
from controller import VirtualSignalController
from safety.conflicts import ConflictMatrix


def test_initial_state_is_all_red():
    """Verify virtual signal controller starts in safe ALL_RED state."""
    vc = VirtualSignalController()
    state = vc.get_current_signal_state()
    assert state.phase == SignalPhase.ALL_RED
    assert state.north == SignalColor.RED
    assert state.south == SignalColor.RED
    assert state.east == SignalColor.RED
    assert state.west == SignalColor.RED
    assert len(state.active_lanes) == 0


def test_execute_decision_concurrent_ns_transition():
    """Verify executing concurrent decision transitions controller from ALL_RED to target NS GREEN."""
    vc = VirtualSignalController()
    now = 100.0
    state = vc.execute_decision(target_lane=[Lane.NORTH, Lane.SOUTH], duration=20, current_time=now)

    assert set(state.active_lanes) == {Lane.NORTH, Lane.SOUTH}
    assert state.phase == SignalPhase.GREEN
    assert state.north == SignalColor.GREEN
    assert state.south == SignalColor.GREEN
    assert state.east == SignalColor.RED
    assert state.west == SignalColor.RED


def test_execute_decision_concurrent_ew_transition():
    """Verify executing concurrent decision transitions controller to EW GREEN."""
    vc = VirtualSignalController()
    now = 100.0
    state = vc.execute_decision(target_lane=[Lane.EAST, Lane.WEST], duration=20, current_time=now)

    assert set(state.active_lanes) == {Lane.EAST, Lane.WEST}
    assert state.phase == SignalPhase.GREEN
    assert state.north == SignalColor.RED
    assert state.south == SignalColor.RED
    assert state.east == SignalColor.GREEN
    assert state.west == SignalColor.GREEN


def test_execute_decision_switching_corridor_triggers_yellow_clearance():
    """Verify switching from NS GREEN to EW GREEN triggers concurrent YELLOW clearance on NS first."""
    vc = VirtualSignalController()
    start = 100.0

    # 1. Start NS GREEN
    vc.execute_decision(target_lane=[Lane.NORTH, Lane.SOUTH], duration=20, current_time=start)

    # 2. Decision to switch to EW -> initiates NS YELLOW clearance
    s_yellow = vc.execute_decision(target_lane=[Lane.EAST, Lane.WEST], duration=25, current_time=start + 12.0)
    assert set(s_yellow.active_lanes) == {Lane.NORTH, Lane.SOUTH}
    assert s_yellow.phase == SignalPhase.YELLOW
    assert s_yellow.north == SignalColor.YELLOW
    assert s_yellow.south == SignalColor.YELLOW
    assert s_yellow.east == SignalColor.RED
    assert s_yellow.west == SignalColor.RED

    # 3. Advance time -> transitions YELLOW -> ALL_RED -> EW GREEN
    s_all_red = vc.advance_time(start + 16.0)
    assert s_all_red.phase == SignalPhase.ALL_RED
    assert s_all_red.north == SignalColor.RED
    assert s_all_red.south == SignalColor.RED
    assert s_all_red.east == SignalColor.RED
    assert s_all_red.west == SignalColor.RED

    s_green = vc.advance_time(start + 19.0)
    assert set(s_green.active_lanes) == {Lane.EAST, Lane.WEST}
    assert s_green.phase == SignalPhase.GREEN
    assert s_green.east == SignalColor.GREEN
    assert s_green.west == SignalColor.GREEN


def test_duration_bounding():
    """Verify requested green durations are bounded between MIN_GREEN and MAX_GREEN config bounds."""
    vc = VirtualSignalController()
    now = 100.0

    # Duration below min -> bounded to MIN_GREEN_SECONDS (10s)
    s_min = vc.execute_decision(target_lane=Lane.SOUTH, duration=2, current_time=now)
    assert s_min.remaining_seconds == 10

    # Duration above max -> bounded to MAX_GREEN_SECONDS (60s)
    s_max = vc.execute_decision(target_lane=Lane.SOUTH, duration=120, current_time=now)
    assert s_max.remaining_seconds == 60


def test_virtual_controller_conflict_invariant_concurrent():
    """Verify all transitions executed by VirtualSignalController maintain conflict invariant."""
    vc = VirtualSignalController()
    now = 100.0

    s1 = vc.execute_decision([Lane.NORTH, Lane.SOUTH], 20, now)
    assert ConflictMatrix.is_safe_signal_state(s1) is True

    s2 = vc.execute_decision([Lane.EAST, Lane.WEST], 20, now + 10.0)
    assert ConflictMatrix.is_safe_signal_state(s2) is True

    s3 = vc.advance_time(now + 14.0)
    assert ConflictMatrix.is_safe_signal_state(s3) is True

    s4 = vc.advance_time(now + 17.0)
    assert ConflictMatrix.is_safe_signal_state(s4) is True

def test_dynamic_time_evaluation_and_countdown():
    """Verify get_current_signal_state evaluates countdown dynamically."""
    vc = VirtualSignalController()
    start = 100.0
    vc.execute_decision(target_lane=[Lane.NORTH], duration=20, current_time=start)
    
    state1 = vc.get_current_signal_state(start + 5.0)
    assert state1.phase == SignalPhase.GREEN
    assert state1.remaining_seconds == 15
    
    state2 = vc.get_current_signal_state(start + 10.0)
    assert state2.phase == SignalPhase.GREEN
    assert state2.remaining_seconds == 10

def test_dynamic_catchup_transitions():
    """Verify that get_current_signal_state automatically catches up to target green."""
    vc = VirtualSignalController()
    start = 100.0
    
    # Start NS GREEN
    vc.execute_decision(target_lane=[Lane.NORTH, Lane.SOUTH], duration=20, current_time=start)
    
    # Switch to EW -> initiates YELLOW clearance
    vc.execute_decision(target_lane=[Lane.EAST, Lane.WEST], duration=25, current_time=start + 10.0)
    
    # Jump time ahead by 10 seconds.
    # YELLOW takes 3s (ends at 113.0)
    # ALL RED takes 2s (ends at 115.0)
    # Target GREEN starts at 115.0
    state = vc.get_current_signal_state(start + 20.0) # t=120.0
    
    assert set(state.active_lanes) == {Lane.EAST, Lane.WEST}
    assert state.phase == SignalPhase.GREEN
    assert state.east == SignalColor.GREEN
    assert state.remaining_seconds == 20 # 25 - 5 elapsed in GREEN phase


def test_execute_decision_rejects_conflicting_lanes_without_mutation():
    """Verify executing conflicting target lanes rejects safely without mutating state."""
    vc = VirtualSignalController()
    start = 100.0
    
    # 1. Start valid NS GREEN
    state1 = vc.execute_decision(target_lane=[Lane.NORTH, Lane.SOUTH], duration=20, current_time=start)
    assert set(state1.active_lanes) == {Lane.NORTH, Lane.SOUTH}
    assert state1.phase == SignalPhase.GREEN
    
    # 2. Attempt invalid transition [NORTH, EAST]
    state2 = vc.execute_decision(target_lane=[Lane.NORTH, Lane.EAST], duration=25, current_time=start + 5.0)
    
    # 3. State should be un-mutated (still NS GREEN)
    assert set(state2.active_lanes) == {Lane.NORTH, Lane.SOUTH}
    assert state2.phase == SignalPhase.GREEN
    assert state2.remaining_seconds == 15


def test_emergency_maintains_clearance_transitions():
    """Verify emergency requests still follow safe clearance intervals."""
    vc = VirtualSignalController()
    start = 100.0
    
    # Start NS GREEN
    vc.execute_decision(target_lane=[Lane.NORTH, Lane.SOUTH], duration=20, current_time=start)
    
    # Emergency request for WEST
    s_yellow = vc.execute_decision(target_lane=[Lane.WEST], duration=20, current_time=start + 5.0)
    
    # Must immediately transition to YELLOW for current active
    assert set(s_yellow.active_lanes) == {Lane.NORTH, Lane.SOUTH}
    assert s_yellow.phase == SignalPhase.YELLOW
    
    # Then ALL_RED
    s_red = vc.advance_time(start + 8.0)
    assert s_red.phase == SignalPhase.ALL_RED
    
    # Then target GREEN
    s_green = vc.advance_time(start + 10.0)
    assert set(s_green.active_lanes) == {Lane.WEST}
    assert s_green.phase == SignalPhase.GREEN


def test_manual_control_single_lane_safe():
    """Verify single-lane manual requests are safe and accepted."""
    vc = VirtualSignalController()
    start = 100.0
    
    state = vc.execute_decision(target_lane=[Lane.EAST], duration=20, current_time=start)
    assert ConflictMatrix.is_safe_signal_state(state) is True
    assert set(state.active_lanes) == {Lane.EAST}
    assert state.phase == SignalPhase.GREEN
