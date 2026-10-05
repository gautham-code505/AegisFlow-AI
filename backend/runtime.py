"""
AegisFlow AI - Runtime Managers and Schedulers
"""

import asyncio
import threading
import time
import contextlib
from typing import Any, Callable
from pydantic import BaseModel
import logging

from models import Status

DECISION_INTERVAL = 1.0

async def _decision_loop(state_store, orchestrator, decision_event: asyncio.Event, logger: logging.Logger):
    """
    Decoupled control decision scheduler.
    Periodically checks the StateStore for a new TrafficState and invokes the orchestrator.
    """
    _last_processed_version = -1
    while True:
        try:
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(decision_event.wait(), timeout=DECISION_INTERVAL)
            decision_event.clear()
            
            state, state_version = state_store.get_traffic_state_with_version()
            if state and state_version != _last_processed_version:
                await orchestrator.process_traffic_state(state)
                _last_processed_version = state_version
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error(f"Decision loop error: {exc}", exc_info=True)
            await asyncio.sleep(1.0) # Prevent tight loop on persistent failure

async def _telemetry_broadcast_loop(state_store, orchestrator, ws_manager, logger: logging.Logger):
    """
    Decoupled periodic telemetry publisher loop.
    Periodically evaluates time-derived controller state, updates StateStore,
    and broadcasts to connected WebSocket clients if present.
    """
    while True:
        try:
            await asyncio.sleep(1.0)
            now = time.time()
            current_signal = orchestrator.get_current_signal_state(now)
            state_store.set_signal_state(current_signal)
            if ws_manager.active_connections:
                await ws_manager.broadcast_snapshot(
                    traffic_state=state_store.get_traffic_state(),
                    signal_decision=state_store.get_decision(),
                    signal_state=current_signal,
                    system_status=state_store.get_system_status(),
                    events=state_store.get_events(),
                    measurements=state_store.get_measurements(),
                    approach_detections=state_store.get_approach_detections(),
                    approach_statuses=state_store.get_all_approach_statuses(),
                    safety_result=state_store.get_safety_result(),
                    analytics=state_store.get_analytics(),
                )
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.debug(f"Telemetry broadcast notice: {exc}")

class CameraStartRequest(BaseModel):
    source: Any = None  # Default is read from config if None

class CameraRuntimeManager:
    def __init__(self, state_store, vision_adapter, decision_event: asyncio.Event, get_simulated_emergency: Callable, logger: logging.Logger):
        self.state_store = state_store
        self.vision_adapter = vision_adapter
        self.decision_event = decision_event
        self.get_simulated_emergency = get_simulated_emergency
        self.logger = logger
        self._active_thread = None
        self._stop_event = threading.Event()
        self._lock = asyncio.Lock()
        self._legacy_active_count = 0
        
    def is_active(self) -> bool:
        """Returns True if the canonical one-camera runtime is currently executing."""
        return self._active_thread is not None and self._active_thread.is_alive()
        
    async def try_acquire_legacy(self) -> bool:
        """Atomically checks and claims the runtime for a legacy worker."""
        async with self._lock:
            if self.is_active():
                return False
            self._legacy_active_count += 1
            return True
            
    async def release_legacy(self):
        """Releases a legacy worker's claim on the runtime."""
        async with self._lock:
            if self._legacy_active_count > 0:
                self._legacy_active_count -= 1

    async def start(self, source_input, verify_res=None):
        async with self._lock:
            if self._legacy_active_count > 0:
                return False, "Cannot start canonical camera while legacy runtime is active"
            if self._active_thread and self._active_thread.is_alive():
                return False, "Canonical camera runtime already active"
            self._stop_event.clear()
            
            # Start synchronous worker thread
            loop = asyncio.get_running_loop()
            self._active_thread = threading.Thread(
                target=self._run_sync,
                args=(source_input, loop, verify_res),
                daemon=True,
                name="CameraRuntimeThread"
            )
            self._active_thread.start()
            return True, "Canonical camera runtime started"

    async def stop(self):
        async with self._lock:
            if not self._active_thread or not self._active_thread.is_alive():
                return False, "Runtime not active"
            self._stop_event.set()
            
            # Wait for graceful shutdown via executor to not block asyncio while joining
            await asyncio.to_thread(self._active_thread.join, 2.0)
            
            if self._active_thread.is_alive():
                self.logger.warning("CameraRuntimeThread did not terminate within timeout. Retaining ownership lock.")
                return False, "Runtime stop requested but thread is still busy"
                
            self._active_thread = None
            return True, "Canonical camera runtime stopped"
            
    async def shutdown(self):
        await self.stop()
        
    def _run_sync(self, source_input, loop, verify_res=None):
        """
        Executes entirely in a dedicated worker thread to prevent YOLO/OpenCV 
        from blocking the FastAPI asyncio event loop.
        """
        from models import SourceType, VisionStatus, Status
        from vision.video_processor import VideoProcessor
        from .core import frame_store
        
        def _frame_cb(frame):
            frame_store.update(frame)
                
        try:
            current_status = self.state_store.get_system_status()
            current_status.camera = SourceType.LIVE_CAMERA
            current_status.vision = VisionStatus.PROCESSING
            self.state_store.set_system_status(current_status)
            
            # Setup Source
            expected_w, expected_h = None, None
            if verify_res and len(verify_res) == 2:
                expected_w, expected_h = verify_res[0], verify_res[1]
                
            vid_proc = VideoProcessor(source_input, is_live=True, frame_callback=_frame_cb, expected_width=expected_w, expected_height=expected_h)
            
            # Process frames continuously
            generator = self.vision_adapter.process_source(vid_proc, visualizer=vid_proc, process_every_n_frames=1, use_tracking=True, imgsz=960)
            try:
                for state in generator:
                    if self._stop_event.is_set():
                        break
                        
                    sim_emg = self.get_simulated_emergency()
                    if sim_emg:
                        state.emergency = sim_emg
                        
                    # Push to thread-safe StateStore
                    self.state_store.set_traffic_state(state)
                    
                    if state.emergency and state.emergency.detected:
                        # Safely wake the asyncio _decision_loop
                        loop.call_soon_threadsafe(self.decision_event.set)
                        
                    # Yield slightly to prevent 100% CPU on fast sources
                    time.sleep(0.01)
            finally:
                generator.close()
                
        except Exception as exc:
            self.logger.error(f"Canonical camera runtime error: {exc}", exc_info=True)
            current_status = self.state_store.get_system_status()
            current_status.vision = VisionStatus.ERROR
            self.state_store.set_system_status(current_status)
        finally:
            current_status = self.state_store.get_system_status()
            current_status.camera = SourceType.NO_INPUT
            if current_status.vision != VisionStatus.ERROR:
                current_status.vision = VisionStatus.STOPPED
            self.state_store.set_system_status(current_status)
            self.state_store.clear_traffic_state()
