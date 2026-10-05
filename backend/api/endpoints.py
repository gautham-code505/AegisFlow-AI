"""
AegisFlow AI - Canonical API Endpoints
"""
import uuid
import time
import os
import asyncio
from typing import List, Callable
from fastapi import APIRouter, HTTPException, status, UploadFile, File, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import logging

from models import (
    TrafficState, SignalDecision, SignalState, SystemStatus, Event,
    Status, Lane, EmergencyState, EventSeverity, EventCategory, Priority, ServiceMeasurement,
    SourceType, VisionStatus
)
from ..runtime import CameraStartRequest

class OverrideRequest(BaseModel):
    selected_lane: str
    duration: int

def create_endpoints_router(
    state_store, 
    orchestrator, 
    camera_manager, 
    vision_adapter,
    get_simulated_emergency: Callable[[], EmergencyState],
    set_simulated_emergency: Callable[[EmergencyState], None],
    decision_event: asyncio.Event,
    logger: logging.Logger
):
    router = APIRouter()

    @router.get("/api/v1/status", response_model=SystemStatus)
    def get_system_status():
        """Returns canonical SystemStatus telemetry."""
        return state_store.get_system_status()

    @router.get("/api/v1/traffic-state", response_model=TrafficState)
    def get_traffic_state():
        """Returns the latest canonical TrafficState snapshot."""
        state = state_store.get_traffic_state()
        if not state:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No traffic state observation currently available",
            )
        return state

    @router.get("/api/v1/decision", response_model=SignalDecision)
    def get_signal_decision():
        """Returns the latest canonical SignalDecision recommendation."""
        decision = state_store.get_decision()
        if not decision:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No signal decision recommendation currently available",
            )
        return decision

    @router.get("/api/v1/signal-state", response_model=SignalState)
    def get_signal_state():
        """Returns the current canonical SignalState execution snapshot."""
        return orchestrator.get_current_signal_state()

    @router.get("/api/v1/snapshot")
    def get_snapshot():
        """Returns a unified snapshot of the system state."""
        current_signal = orchestrator.get_current_signal_state()
        return {
            "trafficState": state_store.get_traffic_state().model_dump() if state_store.get_traffic_state() else None,
            "signalDecision": state_store.get_decision().model_dump() if state_store.get_decision() else None,
            "signalState": current_signal.model_dump(),
            "systemStatus": state_store.get_system_status().model_dump(),
            "events": [e.model_dump() for e in state_store.get_events()],
            "measurements": [m.model_dump() for m in state_store.get_measurements()],
            "approachDetections": state_store.get_approach_detections(),
            "approachStatuses": state_store.get_all_approach_statuses(),
            "safetyResult": state_store.get_safety_result(),
            "analytics": state_store.get_analytics(),
        }

    @router.post("/api/v1/overrides", response_model=dict)
    def post_override(req: OverrideRequest):
        """Activates a manual override decision."""
        try:
            lane_enum = Lane(req.selected_lane.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid lane '{req.selected_lane}'"
            )
        now = time.time()
        orchestrator.active_override = SignalDecision(
            decision_id=f"dec-ovr-{uuid.uuid4().hex[:8]}",
            timestamp=now,
            selected_lane=lane_enum,
            duration=req.duration,
            priority=Priority.MANUAL,
            reason=["Manual override active"]
        )
        
        event = Event(
            event_id=f"ev-ovr-{uuid.uuid4().hex[:8]}",
            timestamp=now,
            type="OPERATOR_OVERRIDE",
            category=EventCategory.DECISION,
            severity=EventSeverity.WARNING,
            message=f"Manual override activated for {lane_enum.value.upper()} ({req.duration}s)",
            source="Operator",
            target_lanes=[lane_enum]
        )
        state_store.add_event(event)
        return {"status": "ok", "message": f"Manual override set to {lane_enum.value.upper()}"}

    @router.delete("/api/v1/overrides/current", response_model=dict)
    def delete_override():
        """Clears any active manual override."""
        if getattr(orchestrator, 'active_override', None):
            orchestrator.active_override = None
            now = time.time()
            event = Event(
                event_id=f"ev-ovr-clr-{uuid.uuid4().hex[:8]}",
                timestamp=now,
                type="OPERATOR_OVERRIDE_CLEARED",
                category=EventCategory.SYSTEM,
                severity=EventSeverity.INFO,
                message="Manual override cleared. Returning to adaptive control.",
                source="Operator"
            )
            state_store.add_event(event)
        return {"status": "ok", "message": "Manual override cleared"}

    @router.get("/api/v1/events", response_model=List[Event])
    def get_events():
        """Returns recent system audit log events."""
        return state_store.get_events()

    @router.get("/api/v1/measurements", response_model=List[ServiceMeasurement])
    def get_measurements():
        """Returns recently completed closed-loop service interval measurements."""
        return state_store.get_measurements()

    @router.post("/api/v1/demo/traffic", response_model=SignalDecision)
    async def post_demo_traffic(traffic_state: TrafficState):
        """
        Submits a canonical TrafficState payload into the orchestration pipeline.
        """
        try:
            sim_emg = get_simulated_emergency()
            if sim_emg:
                traffic_state.emergency = sim_emg
            decision = await orchestrator.process_traffic_state(traffic_state)
            return decision
        except Exception as exc:
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing traffic state: {str(exc)}",
            )

    @router.post("/api/v1/demo/{scenario}", response_model=SignalDecision)
    async def post_demo_scenario(scenario: str):
        """
        Triggers a deterministic synthetic demo scenario.
        """
        from ..demo_data import get_demo_scenarios
        scenarios = get_demo_scenarios()
        normalized_key = scenario.lower().strip()

        if normalized_key not in scenarios:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown demo scenario '{scenario}'. Available scenarios: {list(scenarios.keys())}",
            )

        synthetic_state = scenarios[normalized_key]
        decision = await orchestrator.process_traffic_state(synthetic_state)
        return decision

    @router.post("/api/v1/demo/emergency/clear", response_model=dict)
    async def post_demo_emergency_clear():
        """Clears any active simulated emergency event."""
        sim_emg = get_simulated_emergency()
        if sim_emg is not None:
            lane = sim_emg.lane.value.upper()
            set_simulated_emergency(None)
            
            now = time.time()
            clear_event = Event(
                event_id=f"ev-emg-clr-{uuid.uuid4().hex[:8]}",
                timestamp=now,
                type="EMERGENCY_CLEARED",
                category=EventCategory.EMERGENCY,
                severity=EventSeverity.INFO,
                message=f"Simulated emergency vehicle cleared from {lane} approach. Returning to normal adaptive control.",
                source="Simulation"
            )
            state_store.add_event(clear_event)

            cur_traffic = state_store.get_traffic_state()
            if cur_traffic:
                cur_traffic.emergency = EmergencyState()
                cur_traffic.timestamp = now
                await orchestrator.process_traffic_state(cur_traffic)
            
        return {"status": "ok", "message": "Emergency cleared"}

    @router.post("/api/v1/demo/emergency/{lane}", response_model=dict)
    async def post_demo_emergency(lane: str):
        """
        Simulates an emergency vehicle detection on a given lane.
        """
        try:
            lane_enum = Lane(lane.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid lane '{lane}'. Valid lanes are: {[l.value for l in Lane]}"
            )
            
        new_emg = EmergencyState(
            detected=True,
            lane=lane_enum,
            vehicle_type="ambulance"
        )
        set_simulated_emergency(new_emg)
        
        now = time.time()
        det_event = Event(
            event_id=f"ev-emg-det-{uuid.uuid4().hex[:8]}",
            timestamp=now,
            type="EMERGENCY_DETECTED",
            category=EventCategory.EMERGENCY,
            severity=EventSeverity.WARNING,
            message=f"Simulated emergency vehicle detected on {lane_enum.value.upper()} approach",
            source="Simulation",
            target_lanes=[lane_enum]
        )
        state_store.add_event(det_event)

        cur_traffic = state_store.get_traffic_state()
        if cur_traffic:
            cur_traffic.emergency = new_emg
            cur_traffic.timestamp = now
            await orchestrator.process_traffic_state(cur_traffic)
        else:
            new_traffic = TrafficState(
                timestamp=now,
                emergency=new_emg
            )
            await orchestrator.process_traffic_state(new_traffic)
        
        return {"status": "ok", "message": f"Simulated emergency activated on {lane_enum.value.upper()}"}

    @router.post("/api/v1/camera/start")
    async def start_camera(req: CameraStartRequest):
        from ..core import cfg
        source = req.source if req.source is not None else cfg.get("camera_source", 0)
        verify_res = cfg.get("camera_verify_resolution", None)
        success, msg = await camera_manager.start(source, verify_res=verify_res)
        if not success:
            raise HTTPException(status_code=400, detail=msg)
        return {"status": "started", "message": msg}

    @router.post("/api/v1/camera/stop")
    async def stop_camera():
        success, msg = await camera_manager.stop()
        if not success:
            raise HTTPException(status_code=400, detail=msg)
        return {"status": "stopped", "message": msg}

    async def process_video_background(input_path: str, output_path: str):
        from ..core import frame_store
        try:
            current_status = state_store.get_system_status()
            current_status.camera = SourceType.RECORDED_VIDEO
            current_status.vision = VisionStatus.PROCESSING
            state_store.set_system_status(current_status)
            
            def frame_cb(frame):
                frame_store.update(frame)
            
            for state in vision_adapter.process_video(input_path, output_path, process_every_n_frames=5, use_tracking=True, frame_callback=frame_cb, conf=0.15, imgsz=1280):
                sim_emg = get_simulated_emergency()
                if sim_emg:
                    state.emergency = sim_emg
                    
                state_store.set_traffic_state(state)
                if state.emergency and state.emergency.detected:
                    decision_event.set()
                    
                await asyncio.sleep(0.01)
                
            current_status = state_store.get_system_status()
            current_status.camera = SourceType.NO_INPUT
            current_status.vision = VisionStatus.STOPPED
            state_store.set_system_status(current_status)
            state_store.clear_traffic_state()
            
        except Exception as exc:
            logger.error(f"Background video processing failed: {exc}", exc_info=True)
            current_status = state_store.get_system_status()
            current_status.camera = SourceType.NO_INPUT
            current_status.vision = VisionStatus.ERROR
            state_store.set_system_status(current_status)
            state_store.clear_traffic_state()
        finally:
            from ..core import frame_store
            frame_store.clear()

    @router.get("/api/v1/video/stream")
    async def video_stream():
        from ..core import frame_store
        async def frame_generator():
            while True:
                if not frame_store.is_available():
                    # Stream ended or not active, wait a bit
                    await asyncio.sleep(0.5)
                    continue
                frame_bytes = frame_store.get_latest()
                if frame_bytes:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                await asyncio.sleep(0.05)
                
        return StreamingResponse(frame_generator(), media_type="multipart/x-mixed-replace; boundary=frame")

    @router.post("/api/v1/video/upload")
    async def upload_video(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
        os.makedirs("data/videos", exist_ok=True)
        input_path = os.path.join("data/videos", f"temp_{file.filename}")
        output_path = os.path.join("data/videos", f"output_{file.filename}")
        
        with open(input_path, "wb") as buffer:
            buffer.write(await file.read())
            
        background_tasks.add_task(process_video_background, input_path, output_path)
        
        return {"status": "processing", "message": f"Video {file.filename} uploaded and processing started in background."}

    async def process_image_background(input_path: str, output_path: str):
        from ..core import frame_store
        try:
            current_status = state_store.get_system_status()
            current_status.camera = SourceType.IMAGE
            current_status.vision = VisionStatus.PROCESSING
            state_store.set_system_status(current_status)
            
            def frame_cb(frame):
                frame_store.update(frame)
                
            state = vision_adapter.process_image(input_path, output_path, frame_callback=frame_cb)
            sim_emg = get_simulated_emergency()
            if sim_emg:
                state.emergency = sim_emg
            await orchestrator.process_traffic_state(state)
            # DO NOT STOP THE PIPELINE FOR IMAGES!
            # The dashboard needs `vision == PROCESSING` and `camera == IMAGE`
            # to render the processed frame and telemetry continuously.
            # The user can manually click STOP or upload another source.
            
        except Exception as exc:
            logger.error(f"Background image processing failed: {exc}", exc_info=True)
            current_status = state_store.get_system_status()
            current_status.camera = SourceType.NO_INPUT
            current_status.vision = VisionStatus.ERROR
            state_store.set_system_status(current_status)

    @router.post("/api/v1/image/upload")
    async def upload_image(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
        os.makedirs("data/images", exist_ok=True)
        input_path = os.path.join("data/images", f"temp_{file.filename}")
        output_path = os.path.join("data/images", f"output_{file.filename}")
        
        with open(input_path, "wb") as buffer:
            buffer.write(await file.read())
            
        background_tasks.add_task(process_image_background, input_path, output_path)
        
        return {"status": "processing", "message": f"Image {file.filename} uploaded and processing started in background."}

    return router
