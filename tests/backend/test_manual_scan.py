"""
Four-direction manual scan: one handheld camera, one approach at a time.
"""
import hashlib
import threading
import time

import numpy as np
import pytest

from models import Lane, SignalColor, SignalPhase, SourceType, VisionStatus
from backend.frame_store import LatestFrameStore
from backend.manual_scan import ManualScanManager, ScanError, ScanSettings, SCAN_ORDER
from backend.state_store import StateStore
from backend.decision_adapter import DecisionEngineAdapter
from backend.websocket_manager import WebSocketManager
from backend.orchestrator import Orchestrator
from vision.adapter import VisionAdapter


class FakeSource:
    """Live camera stand-in: every frame is filled with its sequence number."""

    def __init__(self):
        self.seq = 0
        self.released = False
        self.fail = threading.Event()

    def read_frame(self):
        time.sleep(0.005)
        if self.fail.is_set():
            return False, None
        self.seq += 1
        return True, np.full((72, 128, 3), self.seq % 250, dtype=np.uint8)

    def release(self):
        self.released = True


class FakeDetector:
    """YOLO stand-in returning a configurable list of boxes (normalised to a 128x72 frame)."""

    def __init__(self):
        self.boxes = []
        self.last_frame = None

    def detect(self, frame, use_tracking=False, conf=None, imgsz=None):
        self.last_frame = frame.copy()
        return [
            {"class": cls, "confidence": c, "bbox": list(bbox), "center": (0, 0), "is_emergency": False, "track_id": None}
            for cls, c, bbox in self.boxes
        ]


def cars(n, x=60, y=30):
    return [("car", 0.6, (x, y, x + 8, y + 6)) for _ in range(n)]


class FakeCameraManager:
    def __init__(self):
        self.claimed = 0
        self.live_running = False

    async def try_acquire_legacy(self):
        if self.live_running:
            return False
        self.claimed += 1
        return True

    async def release_legacy(self):
        self.claimed -= 1


class SpyAdapter:
    status = "CONNECTED"

    def __init__(self):
        self.sent = []

    def update_signal_state(self, state):
        self.sent.append(state)


class Clock:
    def __init__(self):
        self.now = 1_000_000.0

    def __call__(self):
        return self.now


@pytest.fixture
def rig():
    clock = Clock()
    store = StateStore()
    spy = SpyAdapter()
    orch = Orchestrator(store, DecisionEngineAdapter(), WebSocketManager(), physical_adapter=spy)
    adapter = VisionAdapter()
    detector = FakeDetector()
    adapter.detector = detector
    source = FakeSource()
    camera = FakeCameraManager()
    manager = ManualScanManager(
        orchestrator=orch,
        camera_manager=camera,
        vision_adapter=adapter,
        frame_store=LatestFrameStore(),
        settings=ScanSettings(max_age_seconds=120.0, preview_interval_seconds=0.01),
        source_factory=lambda _src: source,
        clock=clock,
    )
    rig = type("Rig", (), {})()
    rig.clock, rig.store, rig.spy, rig.orch = clock, store, spy, orch
    rig.detector, rig.source, rig.camera, rig.manager = detector, source, camera, manager
    yield rig
    manager._stop_event.set()


async def start_and_wait(rig):
    await rig.manager.start(0)
    for _ in range(200):
        if rig.manager.status()["camera"]["state"] == "LIVE" and rig.manager._latest_frame is not None:
            return
        time.sleep(0.01)
    raise AssertionError("fake camera never went live")


async def scan_all(rig, counts):
    for lane in SCAN_ORDER:
        rig.detector.boxes = cars(counts[lane])
        rig.manager.capture(lane)
        rig.manager.confirm(lane)
        rig.clock.now += 5.0


def non_red(state):
    return [c for c in (state.north, state.south, state.east, state.west) if c != SignalColor.RED]


@pytest.mark.anyio
async def test_scan_starts_one_direction_at_a_time_with_signals_all_red(rig):
    await start_and_wait(rig)
    status = rig.manager.status()
    assert status["active"] is True
    assert status["scan"]["next_approach"] == "north"
    assert status["scan"]["validity"] == "INCOMPLETE"
    assert status["scan"]["proposal"] is None
    assert rig.camera.claimed == 1

    state = rig.orch.get_current_signal_state(rig.clock.now)
    assert state.phase == SignalPhase.ALL_RED

    rig.detector.boxes = cars(3)
    rig.manager.capture(Lane.NORTH)
    rig.manager.confirm(Lane.NORTH)
    assert rig.manager.status()["scan"]["next_approach"] == "east"
    await rig.manager.stop()
    assert rig.camera.claimed == 0
    assert rig.source.released


@pytest.mark.anyio
async def test_capture_runs_yolo_on_exactly_the_captured_frame(rig):
    await start_and_wait(rig)
    rig.detector.boxes = cars(2)
    obs = rig.manager.capture(Lane.NORTH)
    analysed = rig.detector.last_frame
    assert obs["image_sha256"] == hashlib.sha256(analysed.tobytes()).hexdigest()
    assert obs["status"] == "PENDING"
    assert obs["vehicle_count"] == 2
    assert rig.manager.get_image(Lane.NORTH) is not None
    await rig.manager.stop()


@pytest.mark.anyio
async def test_only_detections_inside_guide_box_are_counted(rig):
    await start_and_wait(rig)
    rig.detector.boxes = cars(2) + [("car", 0.7, (0, 0, 6, 4))]  # last one in the corner
    obs = rig.manager.capture(Lane.EAST)
    assert obs["vehicle_count"] == 2
    assert obs["excluded_count"] == 1
    await rig.manager.stop()


@pytest.mark.anyio
async def test_retake_replaces_the_observation(rig):
    await start_and_wait(rig)
    rig.detector.boxes = cars(1)
    rig.manager.capture(Lane.SOUTH)
    rig.manager.retake(Lane.SOUTH)
    assert rig.manager.status()["scan"]["observations"]["south"] is None
    rig.detector.boxes = cars(4)
    obs = rig.manager.capture(Lane.SOUTH)
    assert obs["attempt"] == 2 and obs["vehicle_count"] == 4
    await rig.manager.stop()


@pytest.mark.anyio
async def test_complete_scan_proposes_busiest_approach_without_touching_live_state(rig):
    await start_and_wait(rig)
    await scan_all(rig, {Lane.NORTH: 2, Lane.EAST: 7, Lane.SOUTH: 1, Lane.WEST: 3})

    scan = rig.manager.status()["scan"]
    assert scan["validity"] == "VALID"
    assert scan["proposal"]["selected_lane"] == "east"
    assert scan["actuation_permitted"] is True
    # Scan data never enters the live pipeline or the live decision engine
    assert rig.store.get_traffic_state() is None
    assert rig.orch.decision_adapter.engine.last_timestamp is None
    await rig.manager.stop()


@pytest.mark.anyio
async def test_incomplete_scan_cannot_be_applied(rig):
    await start_and_wait(rig)
    rig.detector.boxes = cars(5)
    for lane in (Lane.NORTH, Lane.EAST, Lane.SOUTH):
        rig.manager.capture(lane)
        rig.manager.confirm(lane)
    rig.manager.capture(Lane.WEST)  # captured but not confirmed

    scan = rig.manager.status()["scan"]
    assert scan["validity"] == "INCOMPLETE" and scan["missing"] == ["west"]
    assert scan["proposal"] is None
    with pytest.raises(ScanError):
        await rig.manager.apply()
    assert all(not non_red(s) for s in rig.spy.sent)
    await rig.manager.stop()


@pytest.mark.anyio
async def test_expired_scan_cannot_be_applied(rig):
    await start_and_wait(rig)
    await scan_all(rig, {Lane.NORTH: 2, Lane.EAST: 2, Lane.SOUTH: 2, Lane.WEST: 2})
    rig.clock.now += 121.0
    scan = rig.manager.status()["scan"]
    assert scan["validity"] == "EXPIRED"
    with pytest.raises(ScanError):
        await rig.manager.apply()
    await rig.manager.stop()


@pytest.mark.anyio
async def test_apply_runs_one_green_then_clears_to_all_red(rig):
    await start_and_wait(rig)
    await scan_all(rig, {Lane.NORTH: 6, Lane.EAST: 1, Lane.SOUTH: 0, Lane.WEST: 2})

    result = await rig.manager.apply()
    assert result["lane"] == "north"
    t = rig.clock.now
    state = rig.orch.get_current_signal_state(t)
    assert state.phase == SignalPhase.GREEN and state.active_lanes == [Lane.NORTH]

    phases = []
    for step in range(120):
        state = rig.orch.get_current_signal_state(t + step)
        assert len(non_red(state)) <= 1
        if not phases or phases[-1] != state.phase:
            phases.append(state.phase)
    assert phases == [SignalPhase.GREEN, SignalPhase.YELLOW, SignalPhase.ALL_RED]
    assert rig.orch.scan_cycle_status(t + 120) is None

    # One cycle per scan
    with pytest.raises(ScanError):
        await rig.manager.apply()
    await rig.manager.stop()


@pytest.mark.anyio
async def test_apply_blocked_while_live_perception_runs(rig):
    await start_and_wait(rig)
    await scan_all(rig, {Lane.NORTH: 3, Lane.EAST: 1, Lane.SOUTH: 1, Lane.WEST: 1})
    status = rig.store.get_system_status()
    status.camera = SourceType.LIVE_CAMERA
    status.vision = VisionStatus.PROCESSING
    rig.store.set_system_status(status)

    assert rig.manager.status()["scan"]["actuation_permitted"] is False
    with pytest.raises(ScanError):
        await rig.manager.apply()
    await rig.manager.stop()


@pytest.mark.anyio
async def test_stopping_scan_during_cycle_clears_through_yellow(rig):
    await start_and_wait(rig)
    await scan_all(rig, {Lane.NORTH: 1, Lane.EAST: 1, Lane.SOUTH: 9, Lane.WEST: 1})
    await rig.manager.apply()
    t = rig.clock.now
    assert rig.orch.get_current_signal_state(t + 1).phase == SignalPhase.GREEN

    rig.clock.now = t + 2
    await rig.manager.stop()
    assert rig.orch.get_current_signal_state(t + 2).phase == SignalPhase.YELLOW
    assert rig.orch.get_current_signal_state(t + 10).phase == SignalPhase.ALL_RED


@pytest.mark.anyio
async def test_scan_refused_while_live_camera_runs(rig):
    rig.camera.live_running = True
    with pytest.raises(ScanError):
        await rig.manager.start(0)
    assert rig.manager.status()["active"] is False


@pytest.mark.anyio
async def test_camera_failure_is_reported_and_capture_refused(rig):
    await start_and_wait(rig)
    rig.source.fail.set()
    for _ in range(200):
        if rig.manager.status()["camera"]["state"] == "ERROR":
            break
        time.sleep(0.01)
    assert rig.manager.status()["camera"]["state"] == "ERROR"
    with pytest.raises(ScanError):
        rig.manager.capture(Lane.NORTH)
    await rig.manager.stop()


def test_scan_api_rejects_actions_without_a_running_scan():
    from fastapi.testclient import TestClient
    from backend.app import app

    with TestClient(app) as client:
        assert client.get("/api/v1/scan").json()["active"] is False
        assert client.post("/api/v1/scan/north/capture").status_code == 409
        assert client.post("/api/v1/scan/north/confirm").status_code == 409
        assert client.post("/api/v1/scan/apply").status_code == 409
        assert client.post("/api/v1/scan/upwards/capture").status_code == 400
        assert client.get("/api/v1/scan/north/image").status_code == 404
