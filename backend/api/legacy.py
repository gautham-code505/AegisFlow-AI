"""
AegisFlow AI - Legacy 4-Camera Endpoints and State
"""
import time
import uuid
import os
import asyncio
import warnings
from typing import Callable
import logging
from fastapi import APIRouter, HTTPException, status, UploadFile, File, BackgroundTasks

from models import TrafficState, Status, SourceType, VisionStatus, Event, EventCategory, EventSeverity, EmergencyState, LaneState, Lane

# Shared state for accumulating per-approach lane results
_approach_lane_states = {}
_approach_emergencies = {}  # Per-approach vision-detected emergency state
_approach_lock = asyncio.Lock()


def _merge_emergency_states(simulated, vision_emergencies: dict) -> EmergencyState:
    """Merge simulated and vision-detected emergencies. Simulated takes precedence."""
    if simulated:
        return simulated
    for approach_name, emg in vision_emergencies.items():
        if emg and emg.detected:
            return emg
    return EmergencyState()

def create_legacy_router(
    state_store, 
    orchestrator, 
    vision_adapter, 
    camera_manager,
    get_simulated_emergency: Callable[[], EmergencyState],
    decision_event: asyncio.Event,
    logger: logging.Logger
):
    router = APIRouter()

    async def process_approach_video_background(input_path: str, approach: str):
        try:
            state_store.set_approach_status(approach, "PROCESSING")
            current_status = state_store.get_system_status()
            current_status.camera = SourceType.RECORDED_VIDEO
            current_status.vision = VisionStatus.PROCESSING
            state_store.set_system_status(current_status)

            lane_state, detections, vision_emergency = vision_adapter.process_single_approach_video(
                input_path, approach, process_every_n_frames=5
            )

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

            async with _approach_lock:
                _approach_lane_states[approach] = lane_state
                _approach_emergencies[approach] = vision_emergency
                lanes = {}
                for dir_name in ["north", "south", "east", "west"]:
                    if dir_name in _approach_lane_states:
                        lanes[Lane(dir_name)] = _approach_lane_states[dir_name]
                    else:
                        lanes[Lane(dir_name)] = LaneState()

                sim_emg = get_simulated_emergency()
                emergency = _merge_emergency_states(sim_emg, _approach_emergencies)

                unified_state = TrafficState(
                    timestamp=time.time(),
                    lanes=lanes,
                    emergency=emergency,
                )
                state_store.set_traffic_state(unified_state)
                if emergency and emergency.detected:
                    decision_event.set()

            current_status = state_store.get_system_status()
            current_status.camera = SourceType.NO_INPUT
            current_status.vision = VisionStatus.STOPPED
            state_store.set_system_status(current_status)
            state_store.set_approach_status(approach, "ACTIVE")

        except Exception as exc:
            logger.error(f"Background approach video processing failed for {approach}: {exc}", exc_info=True)
            current_status = state_store.get_system_status()
            current_status.camera = SourceType.NO_INPUT
            current_status.vision = VisionStatus.ERROR
            state_store.set_system_status(current_status)
            state_store.set_approach_status(approach, "ERROR")
        finally:
            await camera_manager.release_legacy()

    async def process_approach_image_background(input_path: str, approach: str):
        try:
            state_store.set_approach_status(approach, "PROCESSING")
            current_status = state_store.get_system_status()
            current_status.camera = SourceType.IMAGE
            current_status.vision = VisionStatus.PROCESSING
            state_store.set_system_status(current_status)

            lane_state, detections, vision_emergency = vision_adapter.process_single_approach_image(
                input_path, approach
            )

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

            async with _approach_lock:
                _approach_lane_states[approach] = lane_state
                _approach_emergencies[approach] = vision_emergency
                lanes = {}
                for dir_name in ["north", "south", "east", "west"]:
                    if dir_name in _approach_lane_states:
                        lanes[Lane(dir_name)] = _approach_lane_states[dir_name]
                    else:
                        lanes[Lane(dir_name)] = LaneState()

                sim_emg = get_simulated_emergency()
                emergency = _merge_emergency_states(sim_emg, _approach_emergencies)

                unified_state = TrafficState(
                    timestamp=time.time(),
                    lanes=lanes,
                    emergency=emergency,
                )
                await orchestrator.process_traffic_state(unified_state)

            current_status = state_store.get_system_status()
            current_status.camera = SourceType.NO_INPUT
            current_status.vision = VisionStatus.STOPPED
            state_store.set_system_status(current_status)
            state_store.set_approach_status(approach, "ACTIVE")

        except Exception as exc:
            logger.error(f"Background approach image processing failed for {approach}: {exc}", exc_info=True)
            current_status = state_store.get_system_status()
            current_status.camera = SourceType.NO_INPUT
            current_status.vision = VisionStatus.ERROR
            state_store.set_system_status(current_status)
            state_store.set_approach_status(approach, "ERROR")
        finally:
            await camera_manager.release_legacy()

    @router.post("/api/v1/video/upload/{approach}")
    async def upload_approach_video(approach: str, background_tasks: BackgroundTasks, file: UploadFile = File(...)):
        warnings.warn("The 4-approach video upload API is deprecated. Use the canonical one-camera pipeline.", DeprecationWarning)
        
        if not await camera_manager.try_acquire_legacy():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot process legacy four-video uploads while the canonical One-Camera runtime is active."
            )

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
        return {
            "status": "processing", 
            "approach": approach, 
            "message": f"Video for {approach.upper()} approach uploaded and processing started.",
            "deprecated": True
        }

    @router.post("/api/v1/image/upload/{approach}")
    async def upload_approach_image(approach: str, background_tasks: BackgroundTasks, file: UploadFile = File(...)):
        warnings.warn("The 4-approach image upload API is deprecated. Use the canonical one-camera pipeline.", DeprecationWarning)
        
        if not await camera_manager.try_acquire_legacy():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot process legacy four-video uploads while the canonical One-Camera runtime is active."
            )

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
        return {
            "status": "processing", 
            "approach": approach, 
            "message": f"Image for {approach.upper()} approach uploaded and processing started.",
            "deprecated": True
        }

    @router.post("/api/v1/traffic/reset/{approach}", response_model=dict)
    async def reset_approach_state(approach: str):
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
                _approach_lane_states[approach] = LaneState(has_media=False, status="WAITING_FOR_INPUT")
                
            if approach in _approach_emergencies:
                _approach_emergencies[approach] = EmergencyState()

            lanes = {}
            for dir_name in ["north", "south", "east", "west"]:
                if dir_name in _approach_lane_states:
                    lanes[Lane(dir_name)] = _approach_lane_states[dir_name]
                else:
                    lanes[Lane(dir_name)] = LaneState()
                    
            sim_emg = get_simulated_emergency()
            emergency = _merge_emergency_states(sim_emg, _approach_emergencies)
            
            unified_state = TrafficState(
                timestamp=time.time(),
                lanes=lanes,
                emergency=emergency,
            )
            await orchestrator.process_traffic_state(unified_state)

        return {"status": "ok", "message": f"Approach {approach.upper()} state reset"}

    @router.post("/api/v1/traffic/reset", response_model=dict)
    async def reset_all_approaches():
        for approach in ["north", "south", "east", "west"]:
            state_store.set_approach_status(approach, "WAITING_FOR_INPUT")
            state_store.set_approach_detections(approach, {})
            
        async with _approach_lock:
            _approach_lane_states.clear()
            _approach_emergencies.clear()
            
            lanes = {
                Lane.NORTH: LaneState(has_media=False, status="WAITING_FOR_INPUT"),
                Lane.SOUTH: LaneState(has_media=False, status="WAITING_FOR_INPUT"),
                Lane.EAST: LaneState(has_media=False, status="WAITING_FOR_INPUT"),
                Lane.WEST: LaneState(has_media=False, status="WAITING_FOR_INPUT")
            }
            
            sim_emg = get_simulated_emergency()
            emergency = _merge_emergency_states(sim_emg, _approach_emergencies)
            
            unified_state = TrafficState(
                timestamp=time.time(),
                lanes=lanes,
                emergency=emergency,
            )
            
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

    return router
