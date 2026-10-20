"""
Stale or missing perception must clear towards ALL_RED and never turn a GREEN on.
"""
import pytest

from models import TrafficState, LaneState, Lane, SignalColor, SignalPhase, SourceType, VisionStatus
from backend.state_store import StateStore
from backend.decision_adapter import DecisionEngineAdapter
from backend.websocket_manager import WebSocketManager
from backend.orchestrator import Orchestrator
from controller.config import DEFAULT_CONTROLLER_CONFIG


class SpyAdapter:
    status = "CONNECTED"

    def __init__(self):
        self.sent = []

    def update_signal_state(self, state):
        self.sent.append(state)


def make_orchestrator(live=True):
    store = StateStore()
    spy = SpyAdapter()
    orch = Orchestrator(store, DecisionEngineAdapter(), WebSocketManager(), physical_adapter=spy)
    if live:
        status = store.get_system_status()
        status.camera = SourceType.LIVE_CAMERA
        status.vision = VisionStatus.PROCESSING
        store.set_system_status(status)
    return orch, store, spy


def greens(state):
    return [c for c in (state.north, state.south, state.east, state.west) if c == SignalColor.GREEN]


def test_single_staleness_threshold_is_three_seconds():
    assert DEFAULT_CONTROLLER_CONFIG.STALE_DATA_SECONDS == 3.0


@pytest.mark.anyio
async def test_stale_traffic_state_never_sends_green():
    """Regression: a stale TrafficState used to start the round-robin fallback (NORTH GREEN)."""
    import time
    orch, _, spy = make_orchestrator()
    await orch.process_traffic_state(TrafficState(timestamp=time.time() - 12.0))
    orch.get_current_signal_state(time.time() + 1.0)

    assert spy.sent
    assert all(not greens(s) for s in spy.sent)


@pytest.mark.anyio
async def test_stale_input_clears_green_through_yellow():
    import time
    orch, store, spy = make_orchestrator()
    now = time.time()
    lanes = {Lane.NORTH: LaneState(vehicle_count=9)}
    await orch.process_traffic_state(TrafficState(timestamp=now, lanes=lanes))
    assert spy.sent[-1].phase == SignalPhase.GREEN

    # Same old state seen 4 s later (camera frozen): must go YELLOW, not straight to RED
    state = orch.get_current_signal_state(now + 4.0)
    assert state.phase == SignalPhase.YELLOW

    state = orch.get_current_signal_state(now + 8.0)
    assert state.phase == SignalPhase.ALL_RED


def test_running_camera_without_traffic_state_is_all_red():
    import time
    orch, store, spy = make_orchestrator()
    orch.virtual_controller.execute_decision(target_lane=[Lane.NORTH], duration=20, current_time=time.time())
    store.clear_traffic_state()

    state = orch.get_current_signal_state(time.time())
    assert state.phase in (SignalPhase.YELLOW, SignalPhase.ALL_RED)
    assert not greens(state)
