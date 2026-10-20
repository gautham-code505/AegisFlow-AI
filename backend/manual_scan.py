"""
AegisFlow AI - Four-Direction Manual Scan

One handheld camera is pointed at each approach in turn (NORTH, EAST, SOUTH, WEST).
For each approach the operator captures a still; YOLO runs on exactly that still and
the operator confirms it or retakes it. When all four are confirmed and recent enough,
a signal decision is proposed, and the operator may apply it as ONE bounded cycle.

Safety contract:
- Scan data never enters StateStore.traffic_state, so the continuous decision loop,
  the emergency simulation endpoints and the 1 Hz controller tick never see it.
- Scanning holds the camera exclusively and does not report vision as PROCESSING,
  so the orchestrator keeps the signals at ALL_RED while the phone is moving.
- Apply is only allowed for a complete scan whose OLDEST capture is younger than
  max_age_seconds, once per scan, while the signals are at ALL_RED. The cycle is a
  single GREEN for the proposed approach (bounded by controller min/max green),
  then YELLOW and ALL_RED. Capture timestamps are never re-stamped.
"""

import asyncio
import hashlib
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np

from models import Lane, LaneState, TrafficState
from decision_engine import DecisionEngine

logger = logging.getLogger(__name__)

SCAN_ORDER: List[Lane] = [Lane.NORTH, Lane.EAST, Lane.SOUTH, Lane.WEST]
NO_VEHICLES_REASON = "No vehicles counted in any direction. Check the detections or rescan"


@dataclass
class ScanSettings:
    """Tunable scan parameters (override with a "manual_scan" block in vision/config.json)."""
    conf: float = 0.25
    imgsz: int = 960
    # Oldest capture may be at most this old when the scan is applied
    max_age_seconds: float = 120.0
    # Only detections whose centre lies in this normalised box are counted (x1, y1, x2, y2)
    guide_box: Tuple[float, float, float, float] = (0.1, 0.1, 0.9, 0.9)
    preview_interval_seconds: float = 0.2

    @classmethod
    def from_config(cls, cfg: Dict[str, Any]) -> "ScanSettings":
        block = cfg.get("manual_scan", {}) if cfg else {}
        settings = cls()
        for key in ("conf", "imgsz", "max_age_seconds", "preview_interval_seconds"):
            if key in block:
                setattr(settings, key, type(getattr(settings, key))(block[key]))
        if "guide_box" in block and len(block["guide_box"]) == 4:
            settings.guide_box = tuple(float(v) for v in block["guide_box"])
        return settings


@dataclass
class ApproachObservation:
    """What one confirmed (or pending) capture of one approach contains."""
    approach: Lane
    attempt: int
    captured_at: float              # wall-clock time the frame was read from the camera
    frame_seq: int
    frame_size: Tuple[int, int]
    image_sha256: str
    raw_jpeg: bytes
    annotated_jpeg: bytes
    detections: List[Dict[str, Any]]
    vehicle_count: int
    heavy_vehicle_count: int
    pedestrian_count: int
    excluded_count: int             # detections outside the guide box (not counted)
    occupancy: float
    min_confidence: Optional[float]
    conf: float
    imgsz: int
    status: str = "PENDING"         # PENDING -> CONFIRMED
    confirmed_at: Optional[float] = None

    def summary(self, now: float) -> Dict[str, Any]:
        return {
            "approach": self.approach.value,
            "status": self.status,
            "attempt": self.attempt,
            "captured_at": self.captured_at,
            "confirmed_at": self.confirmed_at,
            "age_seconds": round(max(0.0, now - self.captured_at), 1),
            "vehicle_count": self.vehicle_count,
            "heavy_vehicle_count": self.heavy_vehicle_count,
            "pedestrian_count": self.pedestrian_count,
            "excluded_count": self.excluded_count,
            "occupancy": self.occupancy,
            "min_confidence": self.min_confidence,
            "frame_seq": self.frame_seq,
            "image_sha256": self.image_sha256,
            "detections": [
                {"class": d["class"], "confidence": round(d["confidence"], 3), "bbox": d["bbox"], "counted": d["counted"]}
                for d in self.detections
            ],
            "inference": {"conf": self.conf, "imgsz": self.imgsz},
        }


class ScanError(Exception):
    """Raised for operator actions that are not allowed in the current scan state."""


@dataclass
class _ScanSession:
    scan_id: str
    started_at: float
    observations: Dict[Lane, ApproachObservation] = field(default_factory=dict)
    attempts: Dict[Lane, int] = field(default_factory=dict)
    applied_at: Optional[float] = None


def _default_source_factory(source: Any):
    from vision.video_processor import VideoProcessor
    return VideoProcessor(source, is_live=True)


class ManualScanManager:
    """Owns the four-direction scan: camera preview, captures, proposal and guarded apply."""

    def __init__(
        self,
        orchestrator,
        camera_manager,
        vision_adapter,
        frame_store,
        settings: Optional[ScanSettings] = None,
        source_factory: Callable[[Any], Any] = _default_source_factory,
        clock: Callable[[], float] = time.time,
    ):
        self.orchestrator = orchestrator
        self.camera_manager = camera_manager
        self.vision_adapter = vision_adapter
        self.frame_store = frame_store
        self.settings = settings or ScanSettings()
        self.source_factory = source_factory
        self.clock = clock

        self._lock = threading.Lock()            # scan session + latest frame
        self._detector_lock = threading.Lock()   # one YOLO call at a time
        self._session: Optional[_ScanSession] = None
        self._camera_claimed = False
        self._camera_state = "OFF"               # OFF, STARTING, LIVE, ERROR
        self._camera_error: Optional[str] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._latest_frame: Optional[np.ndarray] = None
        self._latest_frame_time: float = 0.0
        self._frame_seq = 0

    # ------------------------------------------------------------------
    # Camera lifecycle
    # ------------------------------------------------------------------

    @property
    def is_active(self) -> bool:
        return self._camera_claimed

    async def start(self, source: Any) -> str:
        """Claims the camera, starts the preview and begins a new scan."""
        if self._camera_claimed:
            raise ScanError("Scan mode is already running")
        if not await self.camera_manager.try_acquire_legacy():
            raise ScanError("Stop the live camera before starting a four-direction scan")
        self._camera_claimed = True
        self.new_scan()
        self._stop_event.clear()
        self._camera_state = "STARTING"
        self._camera_error = None
        self._thread = threading.Thread(target=self._preview_loop, args=(source,), daemon=True, name="ManualScanPreview")
        self._thread.start()
        return self._session.scan_id

    async def stop(self) -> None:
        """Stops the preview, releases the camera and ends any running scan cycle."""
        self.orchestrator.cancel_scan_cycle(self.clock())
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            await asyncio.to_thread(self._thread.join, 3.0)
        self._thread = None
        if self._camera_claimed:
            self._camera_claimed = False
            await self.camera_manager.release_legacy()
        self._camera_state = "OFF"
        with self._lock:
            self._latest_frame = None
            self._session = None

    def new_scan(self) -> str:
        """Discards all captures and starts a fresh scan (camera keeps running)."""
        with self._lock:
            self._session = _ScanSession(scan_id=f"scan-{uuid.uuid4().hex[:8]}", started_at=self.clock())
            return self._session.scan_id

    def _preview_loop(self, source: Any) -> None:
        src = None
        try:
            src = self.source_factory(source)
            self._camera_state = "LIVE"
            last_preview = 0.0
            while not self._stop_event.is_set():
                ret, frame = src.read_frame()
                if not ret or frame is None:
                    raise RuntimeError("Camera stopped delivering frames")
                with self._lock:
                    self._frame_seq += 1
                    self._latest_frame = frame
                    self._latest_frame_time = self.clock()
                now = time.monotonic()
                if now - last_preview >= self.settings.preview_interval_seconds:
                    last_preview = now
                    detections = self._detect(frame)
                    self.frame_store.update(self._annotate(frame, detections))
        except Exception as exc:
            logger.error(f"Manual scan camera error: {exc}")
            self._camera_state = "ERROR"
            self._camera_error = str(exc)
        finally:
            if src is not None:
                try:
                    src.release()
                except Exception:
                    pass
            self.frame_store.clear()
            with self._lock:
                self._latest_frame = None
            if self._camera_state != "ERROR":
                self._camera_state = "OFF"

    # ------------------------------------------------------------------
    # Detection helpers
    # ------------------------------------------------------------------

    def _detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        self.vision_adapter._ensure_detector()
        with self._detector_lock:
            detections = self.vision_adapter.detector.detect(
                frame, use_tracking=False, conf=self.settings.conf, imgsz=self.settings.imgsz
            )
        h, w = frame.shape[:2]
        gx1, gy1, gx2, gy2 = self.settings.guide_box
        for det in detections:
            x1, y1, x2, y2 = det["bbox"]
            cx, cy = (x1 + x2) / 2.0 / w, (y1 + y2) / 2.0 / h
            det["counted"] = gx1 <= cx <= gx2 and gy1 <= cy <= gy2
        return detections

    def _annotate(self, frame: np.ndarray, detections: List[Dict[str, Any]]) -> np.ndarray:
        out = frame.copy()
        h, w = out.shape[:2]
        gx1, gy1, gx2, gy2 = self.settings.guide_box
        cv2.rectangle(out, (int(gx1 * w), int(gy1 * h)), (int(gx2 * w), int(gy2 * h)), (255, 255, 255), 2)
        for det in detections:
            x1, y1, x2, y2 = det["bbox"]
            color = (0, 200, 0) if det.get("counted") else (120, 120, 120)
            cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
            label = f"{det['class']} {det['confidence']:.2f}"
            cv2.putText(out, label, (x1, max(12, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
        vehicles, _, _ = self.vision_adapter._classify_detections([d["class"] for d in detections if d.get("counted")])
        cv2.putText(out, f"Vehicles in box: {vehicles}", (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
        return out

    @staticmethod
    def _jpeg(frame: np.ndarray) -> bytes:
        ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        if not ok:
            raise ScanError("Could not encode captured image")
        return buf.tobytes()

    # ------------------------------------------------------------------
    # Operator actions
    # ------------------------------------------------------------------

    def _require_session(self) -> _ScanSession:
        if self._session is None:
            raise ScanError("No scan in progress. Start scan mode first")
        return self._session

    def capture(self, approach: Lane) -> Dict[str, Any]:
        """Freezes the latest camera frame for this approach and runs YOLO on exactly that frame."""
        with self._lock:
            session = self._require_session()
            if session.applied_at is not None:
                raise ScanError("This scan was already applied. Start a new scan")
            if self._latest_frame is None:
                raise ScanError("No camera frame available yet")
            frame = self._latest_frame.copy()
            captured_at = self._latest_frame_time
            frame_seq = self._frame_seq

        detections = self._detect(frame)
        counted = [d for d in detections if d["counted"]]
        classes = [d["class"] for d in counted]
        vehicles, heavy, pedestrians = self.vision_adapter._classify_detections(classes)
        occupancy = self.vision_adapter.occ_calc.calculate_occupancy(approach.value, classes)

        with self._lock:
            session = self._require_session()
            attempt = session.attempts.get(approach, 0) + 1
            session.attempts[approach] = attempt
            observation = ApproachObservation(
                approach=approach,
                attempt=attempt,
                captured_at=captured_at,
                frame_seq=frame_seq,
                frame_size=(frame.shape[1], frame.shape[0]),
                image_sha256=hashlib.sha256(frame.tobytes()).hexdigest(),
                raw_jpeg=self._jpeg(frame),
                annotated_jpeg=self._jpeg(self._annotate(frame, detections)),
                detections=detections,
                vehicle_count=vehicles,
                heavy_vehicle_count=heavy,
                pedestrian_count=pedestrians,
                excluded_count=len(detections) - len(counted),
                occupancy=round(occupancy, 3),
                min_confidence=round(min(d["confidence"] for d in counted), 3) if counted else None,
                conf=self.settings.conf,
                imgsz=self.settings.imgsz,
            )
            session.observations[approach] = observation
            return observation.summary(self.clock())

    def confirm(self, approach: Lane) -> Dict[str, Any]:
        with self._lock:
            session = self._require_session()
            observation = session.observations.get(approach)
            if observation is None:
                raise ScanError(f"Capture {approach.value.upper()} before confirming it")
            if observation.status != "CONFIRMED":
                observation.status = "CONFIRMED"
                observation.confirmed_at = self.clock()
            return observation.summary(self.clock())

    def retake(self, approach: Lane) -> None:
        with self._lock:
            session = self._require_session()
            if session.applied_at is not None:
                raise ScanError("This scan was already applied. Start a new scan")
            session.observations.pop(approach, None)

    def get_image(self, approach: Lane, annotated: bool = True) -> Optional[bytes]:
        with self._lock:
            if self._session is None:
                return None
            observation = self._session.observations.get(approach)
            if observation is None:
                return None
            return observation.annotated_jpeg if annotated else observation.raw_jpeg

    # ------------------------------------------------------------------
    # Scan evaluation
    # ------------------------------------------------------------------

    def _evaluate(self, session: _ScanSession, now: float) -> Dict[str, Any]:
        confirmed = [session.observations[l] for l in SCAN_ORDER
                     if l in session.observations and session.observations[l].status == "CONFIRMED"]
        missing = [l.value for l in SCAN_ORDER
                   if l not in session.observations or session.observations[l].status != "CONFIRMED"]
        oldest_age = round(now - min(o.captured_at for o in confirmed), 1) if confirmed else None
        span = round(max(o.captured_at for o in confirmed) - min(o.captured_at for o in confirmed), 1) if confirmed else None

        if session.applied_at is not None:
            validity, reason = "APPLIED", "This scan was already applied to the signals. Start a new scan"
        elif missing:
            validity, reason = "INCOMPLETE", f"Still to confirm: {', '.join(m.upper() for m in missing)}"
        elif oldest_age > self.settings.max_age_seconds:
            validity, reason = "EXPIRED", (
                f"Oldest capture is {oldest_age:.0f}s old (limit {self.settings.max_age_seconds:.0f}s). Rescan required"
            )
        else:
            validity, reason = "VALID", "All four approaches confirmed and recent"

        return {"validity": validity, "reason": reason, "missing": missing,
                "oldest_age_seconds": oldest_age, "span_seconds": span}

    def _build_traffic_state(self, session: _ScanSession) -> TrafficState:
        observations = [session.observations[l] for l in SCAN_ORDER]
        lanes = {
            o.approach: LaneState(
                vehicle_count=o.vehicle_count,
                occupancy=o.occupancy,
                pedestrian_count=o.pedestrian_count,
                heavy_vehicle_count=o.heavy_vehicle_count,
                has_media=True,
                status="ACTIVE",
            )
            for o in observations
        }
        return TrafficState(
            # Conservative and honest: the scan is as old as its oldest capture
            timestamp=min(o.captured_at for o in observations),
            source=f"manual_scan:{session.scan_id}",
            has_tracking_data=False,
            total_vehicles=sum(o.vehicle_count for o in observations),
            lanes=lanes,
        )

    @staticmethod
    def _no_vehicles(session: _ScanSession) -> bool:
        # A green for an empty junction serves no one, and on the tabletop an all-zero
        # scan usually means the detector missed the vehicles.
        return sum(o.vehicle_count for o in session.observations.values()) == 0

    def _propose(self, session: _ScanSession):
        # Fresh engine every time: the live engine keeps waiting/starvation state
        # that a preview must not disturb.
        return DecisionEngine().decide(self._build_traffic_state(session))

    def status(self) -> Dict[str, Any]:
        now = self.clock()
        with self._lock:
            session = self._session
            base = {
                "active": self._camera_claimed,
                "camera": {"state": self._camera_state, "error": self._camera_error},
                "order": [l.value for l in SCAN_ORDER],
                "settings": {"max_age_seconds": self.settings.max_age_seconds, "guide_box": list(self.settings.guide_box),
                             "conf": self.settings.conf, "imgsz": self.settings.imgsz},
                "cycle": self.orchestrator.scan_cycle_status(now),
            }
            if session is None:
                return {**base, "scan": None}

            evaluation = self._evaluate(session, now)
            next_lane = next((l.value for l in SCAN_ORDER if l.value in evaluation["missing"]), None)
            if evaluation["validity"] != "VALID":
                actuation_ok, blocked_reason = False, evaluation["reason"]
            elif self._no_vehicles(session):
                actuation_ok, blocked_reason = False, NO_VEHICLES_REASON
            else:
                actuation_ok, blocked_reason = self.orchestrator.can_start_scan_cycle(now)
            proposal = None
            if evaluation["validity"] in ("VALID", "APPLIED"):
                decision = self._propose(session)
                proposal = {
                    "selected_lane": decision.selected_lane.value,
                    "duration": decision.duration,
                    "priority": decision.priority.value,
                    "reasons": decision.reasons,
                }
            return {
                **base,
                "scan": {
                    "scan_id": session.scan_id,
                    "started_at": session.started_at,
                    "applied_at": session.applied_at,
                    "next_approach": next_lane,
                    "observations": {l.value: (session.observations[l].summary(now) if l in session.observations else None)
                                     for l in SCAN_ORDER},
                    **evaluation,
                    "proposal": proposal,
                    "actuation_permitted": actuation_ok,
                    "actuation_blocked_reason": None if actuation_ok else blocked_reason,
                },
            }

    async def apply(self) -> Dict[str, Any]:
        """Runs the proposed decision as ONE bounded signal cycle (see module safety contract)."""
        now = self.clock()
        with self._lock:
            session = self._require_session()
            evaluation = self._evaluate(session, now)
            if evaluation["validity"] != "VALID":
                raise ScanError(evaluation["reason"])
            if self._no_vehicles(session):
                raise ScanError(NO_VEHICLES_REASON)
            decision = self._propose(session)
            oldest_age = evaluation["oldest_age_seconds"]

        ok, reason = self.orchestrator.can_start_scan_cycle(now)
        if not ok:
            raise ScanError(reason)
        try:
            signal_state = self.orchestrator.start_scan_cycle(
                lane=decision.selected_lane,
                duration=decision.duration,
                reasons=decision.reasons,
                scan_id=session.scan_id,
                scan_age_seconds=oldest_age,
                max_age_seconds=self.settings.max_age_seconds,
                current_time=now,
            )
        except ValueError as exc:
            raise ScanError(str(exc)) from exc
        with self._lock:
            session.applied_at = now
        return {"status": "applied", "lane": decision.selected_lane.value, "signal_state": signal_state.model_dump()}
