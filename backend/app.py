"""
AegisFlow AI - FastAPI Backend & Orchestration Application

Offline-first intelligent intersection backend service exposing REST APIs and WebSocket stream.
"""

import logging
from typing import List
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import os
import asyncio
import time
import uuid

from pydantic import BaseModel
from models import TrafficState, SignalDecision, SignalState, SystemStatus, Event, Status, Lane, EmergencyState, EventSeverity, EventCategory, Priority, ServiceMeasurement
from safety import SafetyValidator, FallbackController
from controller import VirtualSignalController
from vision.adapter import VisionAdapter
from .state_store import StateStore
from .decision_adapter import DecisionEngineAdapter
from .websocket_manager import WebSocketManager
from .orchestrator import Orchestrator
from .demo_data import get_demo_scenarios

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aegisflow.backend")

_telemetry_task = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _telemetry_task
    _telemetry_task = asyncio.create_task(_telemetry_broadcast_loop())
    yield
    if _telemetry_task:
        _telemetry_task.cancel()
        try:
            await _telemetry_task
        except asyncio.CancelledError:
            pass

app = FastAPI(
    title="AegisFlow AI Backend OS",
    description="Offline Intelligent Intersection Operating System Backend Service",
    version="0.3.0",
    lifespan=lifespan,
)

# Enable CORS for local dev environment
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instantiate core singleton services
state_store = StateStore()
decision_adapter = DecisionEngineAdapter()
ws_manager = WebSocketManager()
safety_validator = SafetyValidator()
virtual_controller = VirtualSignalController()
fallback_controller = FallbackController()

orchestrator = Orchestrator(
    state_store=state_store,
    decision_adapter=decision_adapter,
    websocket_manager=ws_manager,
    safety_validator=safety_validator,
    virtual_controller=virtual_controller,
    fallback_controller=fallback_controller,
)



vision_adapter = VisionAdapter()

# Simulated Emergency State for MVP demonstration
simulated_emergency = None

_telemetry_task = None

async def _telemetry_broadcast_loop():
    """
    Decoupled periodic telemetry publisher loop.
    Periodically evaluates time-derived controller state, updates StateStore,
    and broadcasts to connected WebSocket clients if present.
    Does NOT govern or pace controller time; controller state is determined
    from the authoritative wall clock (time.time()) whenever evaluated.
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

class OverrideRequest(BaseModel):
    selected_lane: str
    duration: int


@app.get("/")
def read_root():
    """Health check root endpoint."""
    return {"status": "ok", "service": "AegisFlow AI Backend OS", "mode": "LOCAL"}


@app.get("/api/v1/status", response_model=SystemStatus)
def get_system_status():
    """Returns canonical SystemStatus telemetry."""
    return state_store.get_system_status()


@app.get("/api/v1/traffic-state", response_model=TrafficState)
def get_traffic_state():
    """Returns the latest canonical TrafficState snapshot."""
    state = state_store.get_traffic_state()
    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No traffic state observation currently available",
        )
    return state


@app.get("/api/v1/decision", response_model=SignalDecision)
def get_signal_decision():
    """Returns the latest canonical SignalDecision recommendation."""
    decision = state_store.get_decision()
    if not decision:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No signal decision recommendation currently available",
        )
    return decision


@app.get("/api/v1/signal-state", response_model=SignalState)
def get_signal_state():
    """Returns the current canonical SignalState execution snapshot."""
    return orchestrator.get_current_signal_state()


@app.get("/api/v1/snapshot")
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


@app.post("/api/v1/overrides", response_model=dict)
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


@app.delete("/api/v1/overrides/current", response_model=dict)
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


@app.get("/api/v1/events", response_model=List[Event])
def get_events():
    """Returns recent system audit log events."""
    return state_store.get_events()


@app.get("/api/v1/measurements", response_model=List[ServiceMeasurement])
def get_measurements():
    """Returns recently completed closed-loop service interval measurements."""
    return state_store.get_measurements()


@app.post("/api/v1/demo/traffic", response_model=SignalDecision)
async def post_demo_traffic(traffic_state: TrafficState):
    """
    Submits a canonical TrafficState payload into the orchestration pipeline.
    Invokes Decision Engine, validates safety, executes virtual controller, updates state store, and returns SignalDecision.
    """
    try:
        if simulated_emergency:
            traffic_state.emergency = simulated_emergency
        decision = await orchestrator.process_traffic_state(traffic_state)
        return decision
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing traffic state: {str(exc)}",
        )


@app.post("/api/v1/demo/{scenario}", response_model=SignalDecision)
async def post_demo_scenario(scenario: str):
    """
    Triggers a deterministic synthetic demo scenario:
    - balanced
    - heavy-north
    - heavy-east
    - emergency-east
    """
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


async def process_video_background(input_path: str, output_path: str):
    """Background task to process the uploaded video through the vision adapter."""
    try:
        # Update status to processing
        current_status = state_store.get_system_status()
        current_status.vision = Status.ONLINE
        state_store.set_system_status(current_status)
        
        # Process frames
        for state in vision_adapter.process_video(input_path, output_path, process_every_n_frames=5):
            if simulated_emergency:
                state.emergency = simulated_emergency
            await orchestrator.process_traffic_state(state)
            # Sleep slightly to allow other async tasks (like websocket broadcasting) to run
            await asyncio.sleep(0.01)
            
        # Update status to complete/idle
        current_status = state_store.get_system_status()
        current_status.vision = Status.OFFLINE
        state_store.set_system_status(current_status)
        
    except Exception as exc:
        logger.error(f"Background video processing failed: {exc}", exc_info=True)
        current_status = state_store.get_system_status()
        current_status.vision = Status.ERROR
        state_store.set_system_status(current_status)


@app.post("/api/v1/video/upload")
async def upload_video(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Uploads a video for processing by the local vision pipeline."""
    # Ensure video dir exists
    os.makedirs("data/videos", exist_ok=True)
    input_path = os.path.join("data/videos", f"temp_{file.filename}")
    output_path = os.path.join("data/videos", f"output_{file.filename}")
    
    # Save the file locally
    with open(input_path, "wb") as buffer:
        buffer.write(await file.read())
        
    # Start background processing
    background_tasks.add_task(process_video_background, input_path, output_path)
    
    return {"status": "processing", "message": f"Video {file.filename} uploaded and processing started in background."}


async def process_image_background(input_path: str, output_path: str):
    """Background task to process the uploaded image through the vision adapter."""
    try:
        # Update status to processing
        current_status = state_store.get_system_status()
        current_status.vision = Status.ONLINE
        state_store.set_system_status(current_status)
        
        # Process image
        state = vision_adapter.process_image(input_path, output_path)
        if simulated_emergency:
            state.emergency = simulated_emergency
        await orchestrator.process_traffic_state(state)
        
        # Update status to complete/idle
        current_status = state_store.get_system_status()
        current_status.vision = Status.OFFLINE
        state_store.set_system_status(current_status)
        
    except Exception as exc:
        logger.error(f"Background image processing failed: {exc}", exc_info=True)
        current_status = state_store.get_system_status()
        current_status.vision = Status.ERROR
        state_store.set_system_status(current_status)

@app.post("/api/v1/image/upload")
async def upload_image(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Uploads an image for processing by the local vision pipeline."""
    # Ensure image dir exists
    os.makedirs("data/images", exist_ok=True)
    input_path = os.path.join("data/images", f"temp_{file.filename}")
    output_path = os.path.join("data/images", f"output_{file.filename}")
    
    # Save the file locally
    with open(input_path, "wb") as buffer:
        buffer.write(await file.read())
        
    # Start background processing
    background_tasks.add_task(process_image_background, input_path, output_path)
    
    return {"status": "processing", "message": f"Image {file.filename} uploaded and processing started in background."}


# ═══════════════════════════════════════════════════════════════
#  4-APPROACH PER-DIRECTION UPLOAD ENDPOINTS
# ═══════════════════════════════════════════════════════════════

# Shared state for accumulating per-approach lane results
_approach_lane_states = {}
_approach_emergencies = {}  # Per-approach vision-detected emergency state
_approach_lock = asyncio.Lock()


def _merge_emergency_states(simulated, vision_emergencies: dict) -> EmergencyState:
    """Merge simulated and vision-detected emergencies. Simulated takes precedence."""
    if simulated:
        return simulated
    # Check if any approach detected a real emergency via YOLO
    for approach_name, emg in vision_emergencies.items():
        if emg and emg.detected:
            return emg
    return EmergencyState()


async def process_approach_video_background(input_path: str, approach: str):
    """Background task to process an uploaded video for a single approach."""
    try:
        state_store.set_approach_status(approach, "PROCESSING")
        current_status = state_store.get_system_status()
        current_status.camera = Status.ONLINE
        current_status.vision = Status.ONLINE
        state_store.set_system_status(current_status)

        lane_state, detections, vision_emergency = vision_adapter.process_single_approach_video(
            input_path, approach, process_every_n_frames=5
        )

        # Store per-approach detection metadata for frontend
        det_summary = {}
        for det in detections:
            cls = det['class']
            det_summary[cls] = det_summary.get(cls, 0) + 1
        state_store.set_approach_detections(approach, {
            "vehicle_count": lane_state.vehicle_count,
            "occupancy": lane_state.occupancy,
            "heavy_vehicle_count": lane_state.heavy_vehicle_count,
            "pedestrian_count": lane_state.pedestrian_count,
            "class_breakdown": det_summary,
            "total_detections": len(detections),
            "raw_detections": detections,
        })

        # Accumulate into unified TrafficState
        async with _approach_lock:
            _approach_lane_states[approach] = lane_state
            _approach_emergencies[approach] = vision_emergency
            # Build unified TrafficState from all approaches processed so far
            from models import LaneState
            lanes = {}
            for dir_name in ["north", "south", "east", "west"]:
                if dir_name in _approach_lane_states:
                    lanes[Lane(dir_name)] = _approach_lane_states[dir_name]
                else:
                    lanes[Lane(dir_name)] = LaneState()

            emergency = _merge_emergency_states(simulated_emergency, _approach_emergencies)

            unified_state = TrafficState(
                timestamp=time.time(),
                lanes=lanes,
                emergency=emergency,
            )
            await orchestrator.process_traffic_state(unified_state)

        current_status = state_store.get_system_status()
        current_status.vision = Status.OFFLINE
        state_store.set_system_status(current_status)
        state_store.set_approach_status(approach, "ACTIVE")

    except Exception as exc:
        logger.error(f"Background approach video processing failed for {approach}: {exc}", exc_info=True)
        current_status = state_store.get_system_status()
        current_status.vision = Status.ERROR
        state_store.set_system_status(current_status)
        state_store.set_approach_status(approach, "ERROR")


async def process_approach_image_background(input_path: str, approach: str):
    """Background task to process an uploaded image for a single approach."""
    try:
        state_store.set_approach_status(approach, "PROCESSING")
        current_status = state_store.get_system_status()
        current_status.camera = Status.ONLINE
        current_status.vision = Status.ONLINE
        state_store.set_system_status(current_status)

        lane_state, detections, vision_emergency = vision_adapter.process_single_approach_image(
            input_path, approach
        )

        # Store per-approach detection metadata
        det_summary = {}
        for det in detections:
            cls = det['class']
            det_summary[cls] = det_summary.get(cls, 0) + 1
        state_store.set_approach_detections(approach, {
            "vehicle_count": lane_state.vehicle_count,
            "occupancy": lane_state.occupancy,
            "heavy_vehicle_count": lane_state.heavy_vehicle_count,
            "pedestrian_count": lane_state.pedestrian_count,
            "class_breakdown": det_summary,
            "total_detections": len(detections),
            "raw_detections": detections,
        })

        # Accumulate into unified TrafficState
        async with _approach_lock:
            _approach_lane_states[approach] = lane_state
            _approach_emergencies[approach] = vision_emergency
            from models import LaneState
            lanes = {}
            for dir_name in ["north", "south", "east", "west"]:
                if dir_name in _approach_lane_states:
                    lanes[Lane(dir_name)] = _approach_lane_states[dir_name]
                else:
                    lanes[Lane(dir_name)] = LaneState()

            emergency = _merge_emergency_states(simulated_emergency, _approach_emergencies)

            unified_state = TrafficState(
                timestamp=time.time(),
                lanes=lanes,
                emergency=emergency,
            )
            await orchestrator.process_traffic_state(unified_state)

        current_status = state_store.get_system_status()
        current_status.vision = Status.OFFLINE
        state_store.set_system_status(current_status)
        state_store.set_approach_status(approach, "ACTIVE")

    except Exception as exc:
        logger.error(f"Background approach image processing failed for {approach}: {exc}", exc_info=True)
        current_status = state_store.get_system_status()
        current_status.vision = Status.ERROR
        state_store.set_system_status(current_status)
        state_store.set_approach_status(approach, "ERROR")


@app.post("/api/v1/video/upload/{approach}")
async def upload_approach_video(approach: str, background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Uploads a video for a single approach direction (north/south/east/west)."""
    approach = approach.lower().strip()
    if approach not in ["north", "south", "east", "west"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid approach '{approach}'. Must be one of: north, south, east, west"
        )

    os.makedirs("data/videos", exist_ok=True)
    input_path = os.path.join("data/videos", f"approach_{approach}_{file.filename}")
    with open(input_path, "wb") as buffer:
        buffer.write(await file.read())

    background_tasks.add_task(process_approach_video_background, input_path, approach)
    return {"status": "processing", "approach": approach, "message": f"Video for {approach.upper()} approach uploaded and processing started."}


@app.post("/api/v1/image/upload/{approach}")
async def upload_approach_image(approach: str, background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Uploads an image for a single approach direction (north/south/east/west)."""
    approach = approach.lower().strip()
    if approach not in ["north", "south", "east", "west"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid approach '{approach}'. Must be one of: north, south, east, west"
        )

    os.makedirs("data/images", exist_ok=True)
    input_path = os.path.join("data/images", f"approach_{approach}_{file.filename}")
    with open(input_path, "wb") as buffer:
        buffer.write(await file.read())

    background_tasks.add_task(process_approach_image_background, input_path, approach)
    return {"status": "processing", "approach": approach, "message": f"Image for {approach.upper()} approach uploaded and processing started."}


@app.post("/api/v1/traffic/reset/{approach}", response_model=dict)
async def reset_approach_state(approach: str):
    """Resets the state of a single approach to WAITING_FOR_INPUT."""
    approach = approach.lower().strip()
    if approach not in ["north", "south", "east", "west"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid approach '{approach}'. Must be one of: north, south, east, west"
        )
    
    state_store.set_approach_status(approach, "WAITING_FOR_INPUT")
    state_store.set_approach_detections(approach, {})
    
    async with _approach_lock:
        if approach in _approach_lane_states:
            from models import LaneState
            _approach_lane_states[approach] = LaneState(has_media=False, status="WAITING_FOR_INPUT")
            
        if approach in _approach_emergencies:
            _approach_emergencies[approach] = EmergencyState()

        # Generate a new traffic state with the cleared approach
        lanes = {}
        from models import LaneState
        for dir_name in ["north", "south", "east", "west"]:
            if dir_name in _approach_lane_states:
                lanes[Lane(dir_name)] = _approach_lane_states[dir_name]
            else:
                lanes[Lane(dir_name)] = LaneState()
                
        emergency = _merge_emergency_states(simulated_emergency, _approach_emergencies)
        
        unified_state = TrafficState(
            timestamp=time.time(),
            lanes=lanes,
            emergency=emergency,
        )
        await orchestrator.process_traffic_state(unified_state)

    return {"status": "ok", "message": f"Approach {approach.upper()} state reset"}

@app.post("/api/v1/traffic/reset", response_model=dict)
async def reset_all_approaches():
    """Resets all approaches to WAITING_FOR_INPUT."""
    for approach in ["north", "south", "east", "west"]:
        state_store.set_approach_status(approach, "WAITING_FOR_INPUT")
        state_store.set_approach_detections(approach, {})
        
    async with _approach_lock:
        _approach_lane_states.clear()
        _approach_emergencies.clear()
        
        from models import LaneState
        lanes = {
            Lane.NORTH: LaneState(has_media=False, status="WAITING_FOR_INPUT"),
            Lane.SOUTH: LaneState(has_media=False, status="WAITING_FOR_INPUT"),
            Lane.EAST: LaneState(has_media=False, status="WAITING_FOR_INPUT"),
            Lane.WEST: LaneState(has_media=False, status="WAITING_FOR_INPUT")
        }
        
        emergency = _merge_emergency_states(simulated_emergency, _approach_emergencies)
        
        unified_state = TrafficState(
            timestamp=time.time(),
            lanes=lanes,
            emergency=emergency,
        )
        
        # Clear history and emit SYSTEM reset event
        state_store.clear_history()
        reset_event = Event(
            event_id=f"ev-sys-{uuid.uuid4().hex[:8]}",
            timestamp=time.time(),
            type="SYSTEM_RESET",
            category=EventCategory.SYSTEM,
            severity=EventSeverity.INFO,
            message="System state reset for new session.",
            source="System"
        )
        state_store.add_event(reset_event)
        
        await orchestrator.process_traffic_state(unified_state)

    return {"status": "ok", "message": "All approaches state reset"}


@app.post("/api/v1/demo/emergency/clear", response_model=dict)
async def post_demo_emergency_clear():
    """Clears any active simulated emergency event."""
    global simulated_emergency
    if simulated_emergency is not None:
        lane = simulated_emergency.lane.value.upper()
        simulated_emergency = None
        
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

        # Immediately process through pipeline to return to normal adaptive control
        cur_traffic = state_store.get_traffic_state()
        if cur_traffic:
            cur_traffic.emergency = EmergencyState()
            cur_traffic.timestamp = now
            await orchestrator.process_traffic_state(cur_traffic)
        
    return {"status": "ok", "message": "Emergency cleared"}


@app.post("/api/v1/demo/emergency/{lane}", response_model=dict)
async def post_demo_emergency(lane: str):
    """
    Simulates an emergency vehicle detection on a given lane.
    This is explicitly documented as a 'Simulated Emergency Event' for MVP demonstration.
    """
    global simulated_emergency
    
    try:
        lane_enum = Lane(lane.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid lane '{lane}'. Valid lanes are: {[l.value for l in Lane]}"
        )
        
    simulated_emergency = EmergencyState(
        detected=True,
        lane=lane_enum,
        vehicle_type="ambulance"
    )
    
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

    # Immediately process through pipeline so decision, safety, and controller execute
    cur_traffic = state_store.get_traffic_state()
    if cur_traffic:
        cur_traffic.emergency = simulated_emergency
        cur_traffic.timestamp = now
        await orchestrator.process_traffic_state(cur_traffic)
    else:
        new_traffic = TrafficState(
            timestamp=now,
            emergency=simulated_emergency
        )
        await orchestrator.process_traffic_state(new_traffic)
    
    return {"status": "ok", "message": f"Simulated emergency activated on {lane_enum.value.upper()}"}


@app.websocket("/ws/traffic")
async def websocket_traffic_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint broadcasting unified snapshots to clients.
    """
    await ws_manager.connect(websocket)

    try:
        # Send initial state snapshot on connection
        current_signal = orchestrator.get_current_signal_state()

        await websocket.send_json({
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
        })

        # Keep connection open and receive optional client heartbeats/messages
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as exc:
        logger.warning(f"WebSocket connection error: {exc}")
        ws_manager.disconnect(websocket)
