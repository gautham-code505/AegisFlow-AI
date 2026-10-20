"""
Tests for single-approach phasing: only one approach may be GREEN at a time.
"""
import time
import pytest

from models import Lane, SignalColor, SignalPhase, SignalDecision, Priority, TrafficState, LaneState, SourceType, VisionStatus
from controller import VirtualSignalController
from controller.config import ControllerConfig, DEFAULT_CONTROLLER_CONFIG
from safety import SafetyValidator, ValidationStatus, ConflictMatrix, get_compatible_phase_for_lane
from safety.phase_groups import PHASE_NORTH, PHASE_EAST, PHASE_NS


def test_single_approach_phasing_is_default():
    assert DEFAULT_CONTROLLER_CONFIG.SINGLE_APPROACH_PHASING is True


@pytest.mark.parametrize("lane", list(Lane))
def test_each_single_approach_is_permitted(lane):
    assert ConflictMatrix.check_target_lanes([lane]) == []


def test_all_red_is_permitted():
    assert ConflictMatrix.check_target_lanes([]) == []


@pytest.mark.parametrize("pair", [
    [Lane.NORTH, Lane.SOUTH],
    [Lane.EAST, Lane.WEST],
    [Lane.NORTH, Lane.EAST],
])
def test_any_two_approaches_are_rejected(pair):
    assert ConflictMatrix.check_target_lanes(pair) != []


def test_signal_state_with_two_greens_is_unsafe():
    colors = {Lane.NORTH: SignalColor.GREEN, Lane.SOUTH: SignalColor.GREEN,
              Lane.EAST: SignalColor.RED, Lane.WEST: SignalColor.RED}
    assert ConflictMatrix.check_conflict(colors) != []


def test_paired_mode_still_available_when_configured():
    paired = ControllerConfig(SINGLE_APPROACH_PHASING=False)
    assert ConflictMatrix.check_target_lanes([Lane.NORTH, Lane.SOUTH], paired) == []
    assert ConflictMatrix.check_target_lanes([Lane.NORTH, Lane.EAST], paired) != []


def test_lane_maps_to_its_own_phase():
    assert get_compatible_phase_for_lane(Lane.NORTH, single_approach=True) == PHASE_NORTH
    assert get_compatible_phase_for_lane(Lane.EAST, single_approach=True) == PHASE_EAST
    assert get_compatible_phase_for_lane(Lane.NORTH) == PHASE_NS


def test_validator_rejects_paired_target():
    now = 1000.0
    decision = SignalDecision(decision_id="d1", timestamp=now, selected_lane=Lane.NORTH,
                              duration=20, priority=Priority.NORMAL, reasons=["test"])
    result = SafetyValidator().validate(
        current_signal_state=None, proposed_decision=decision,
        traffic_state=TrafficState(timestamp=now), current_time=now,
        target_lanes=[Lane.NORTH, Lane.SOUTH],
    )
    assert result.status == ValidationStatus.REJECTED


def test_controller_refuses_paired_target_without_mutation():
    vc = VirtualSignalController()
    state = vc.execute_decision(target_lane=[Lane.NORTH], duration=20, current_time=100.0)
    assert state.active_lanes == [Lane.NORTH]

    state = vc.execute_decision(target_lane=[Lane.EAST, Lane.WEST], duration=20, current_time=105.0)
    assert state.phase == SignalPhase.GREEN
    assert state.active_lanes == [Lane.NORTH]


@pytest.mark.anyio
async def test_orchestrator_serves_one_approach_at_a_time(monkeypatch):
    """Drive the real orchestrator with a fake clock; at most one approach is ever non-RED."""
    from backend.state_store import StateStore
    from backend.decision_adapter import DecisionEngineAdapter
    from backend.websocket_manager import WebSocketManager
    from backend.orchestrator import Orchestrator

    clock = [1_000_000.0]
    monkeypatch.setattr(time, "time", lambda: clock[0])

    sent = []

    class SpyAdapter:
        status = "CONNECTED"

        def update_signal_state(self, s):
            sent.append((s.north, s.east, s.south, s.west))

    store = StateStore()
    orch = Orchestrator(store, DecisionEngineAdapter(), WebSocketManager(), physical_adapter=SpyAdapter())
    status = store.get_system_status()
    status.camera = SourceType.LIVE_CAMERA
    status.vision = VisionStatus.PROCESSING
    store.set_system_status(status)

    counts = {Lane.NORTH: 8, Lane.EAST: 5, Lane.SOUTH: 6, Lane.WEST: 4}
    for _ in range(240):
        state = TrafficState(timestamp=clock[0],
                             lanes={lane: LaneState(vehicle_count=n) for lane, n in counts.items()})
        await orch.process_traffic_state(state)
        orch.get_current_signal_state(clock[0])
        clock[0] += 1.0

    assert sent
    served = set()
    previous = None
    for colors in sent:
        non_red = [c for c in colors if c != SignalColor.RED]
        assert len(non_red) <= 1, f"more than one approach active: {colors}"
        for i, color in enumerate(colors):
            if color == SignalColor.GREEN:
                served.add(i)
            if previous is not None and previous[i] == SignalColor.GREEN:
                assert color in (SignalColor.GREEN, SignalColor.YELLOW), "GREEN must clear through YELLOW"
            if previous is not None and previous[i] == SignalColor.RED and color == SignalColor.GREEN:
                assert all(c == SignalColor.RED for c in previous), "GREEN must start from ALL_RED"
        previous = colors
    assert served == {0, 1, 2, 3}, f"every approach with traffic must be served within four minutes, got {served}"


def test_committed_clearance_target_is_not_redirected():
    """A normal decision during YELLOW must not redirect the committed target; emergency may."""
    vc = VirtualSignalController()
    vc.execute_decision(target_lane=[Lane.NORTH], duration=20, current_time=100.0)
    state = vc.execute_decision(target_lane=[Lane.EAST], duration=15, current_time=111.0)
    assert state.phase == SignalPhase.YELLOW and state.target_lanes == [Lane.EAST]

    state = vc.execute_decision(target_lane=[Lane.NORTH], duration=15, current_time=112.0)
    assert state.target_lanes == [Lane.EAST]

    state = vc.execute_decision(target_lane=[Lane.WEST], duration=15, current_time=113.0, preempt_target=True)
    assert state.target_lanes == [Lane.WEST]


def test_committed_target_served_when_all_red_completes():
    vc = VirtualSignalController()
    vc.execute_decision(target_lane=[Lane.NORTH], duration=20, current_time=100.0)
    vc.execute_decision(target_lane=[Lane.SOUTH], duration=15, current_time=111.0)  # YELLOW -> SOUTH
    # Clearance ends at 116.0; a later decision for NORTH must not jump the queue
    state = vc.execute_decision(target_lane=[Lane.NORTH], duration=15, current_time=116.5)
    assert state.phase == SignalPhase.GREEN
    assert state.active_lanes == [Lane.SOUTH]


def test_adapter_discard_restores_engine_bookkeeping():
    from backend.decision_adapter import DecisionEngineAdapter
    adapter = DecisionEngineAdapter()
    lanes = {Lane.NORTH: LaneState(vehicle_count=9), Lane.EAST: LaneState(vehicle_count=1),
             Lane.SOUTH: LaneState(vehicle_count=0), Lane.WEST: LaneState(vehicle_count=0)}
    adapter.decide(TrafficState(timestamp=100.0, lanes=lanes))
    before = (dict(adapter.engine.waiting_times), dict(adapter.engine.consecutive_skips),
              adapter.engine.last_active_lane, adapter.engine.last_timestamp)

    adapter.decide(TrafficState(timestamp=101.0, lanes=lanes))
    adapter.discard_last_decision()

    after = (dict(adapter.engine.waiting_times), dict(adapter.engine.consecutive_skips),
             adapter.engine.last_active_lane, adapter.engine.last_timestamp)
    assert after == before
