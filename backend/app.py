"""
AegisFlow AI - FastAPI Backend Application Entrypoint

This module acts as the Composition Root. It creates the FastAPI application,
instantiates runtime managers by injecting foundational dependencies from `core.py`,
and wires up API routers.

It also re-exports several core components for backward compatibility with the test suite.
"""

from contextlib import asynccontextmanager
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

# 1. Foundational Dependencies
from backend import core

# 2. Runtime Execution Classes
from backend.runtime import (
    CameraRuntimeManager,
    _decision_loop,
    _telemetry_broadcast_loop,
    DECISION_INTERVAL,
)

# 3. API Routers
from backend.api.endpoints import create_endpoints_router
from backend.api.legacy import create_legacy_router, _approach_lane_states, _approach_emergencies, _approach_lock
from backend.api.websocket import create_websocket_router

logger = logging.getLogger("aegisflow.backend")

# ==========================================
# WIRING & COMPOSITION
# ==========================================

# Instantiate the Camera Manager by injecting core dependencies
camera_manager = CameraRuntimeManager(
    state_store=core.state_store,
    vision_adapter=core.vision_adapter,
    decision_event=core._decision_event,
    get_simulated_emergency=lambda: core.simulated_emergency,
    logger=logger
)

# Instantiate the Routers by injecting core dependencies and the camera manager
endpoints_router = create_endpoints_router(
    state_store=core.state_store,
    orchestrator=core.orchestrator,
    camera_manager=camera_manager,
    vision_adapter=core.vision_adapter,
    get_simulated_emergency=lambda: core.simulated_emergency,
    set_simulated_emergency=lambda e: setattr(core, 'simulated_emergency', e),
    decision_event=core._decision_event,
    logger=logger
)

legacy_router = create_legacy_router(
    state_store=core.state_store,
    orchestrator=core.orchestrator,
    vision_adapter=core.vision_adapter,
    camera_manager=camera_manager,
    get_simulated_emergency=lambda: core.simulated_emergency,
    decision_event=core._decision_event,
    logger=logger
)

websocket_router = create_websocket_router(
    state_store=core.state_store,
    orchestrator=core.orchestrator,
    ws_manager=core.ws_manager,
    logger=logger
)


# ==========================================
# APPLICATION LIFECYCLE
# ==========================================

_telemetry_task = None
_decision_task = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _telemetry_task, _decision_task
    
    # Start physical hardware layer (if present)
    if hasattr(core, 'physical_adapter') and core.physical_adapter:
        core.physical_adapter.start()
        
    # Inject dependencies into background loops
    _telemetry_task = asyncio.create_task(
        _telemetry_broadcast_loop(core.state_store, core.orchestrator, core.ws_manager, logger)
    )
    _decision_task = asyncio.create_task(
        _decision_loop(core.state_store, core.orchestrator, core._decision_event, logger)
    )
    yield
    if _telemetry_task:
        _telemetry_task.cancel()
    if _decision_task:
        _decision_task.cancel()
    
    # Clean shutdown of physical hardware layer
    if hasattr(core, 'physical_adapter') and core.physical_adapter:
        core.physical_adapter.stop()
        
    # Clean shutdown of camera runtime
    if camera_manager:
        await camera_manager.shutdown()
        
    try:
        await asyncio.gather(_telemetry_task, _decision_task, return_exceptions=True)
    except Exception:
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

@app.get("/")
def read_root():
    """Health check root endpoint."""
    return {"status": "ok", "service": "AegisFlow AI Backend OS", "mode": "LOCAL"}

# Include all wired API routes
app.include_router(endpoints_router)
app.include_router(legacy_router)
app.include_router(websocket_router)


# ==========================================
# BACKWARD COMPATIBILITY EXPORTS
# ==========================================
# Existing tests import these directly from backend.app.
# We re-export them here so tests pass without modification.
state_store = core.state_store
virtual_controller = core.virtual_controller
_decision_event = core._decision_event
vision_adapter = core.vision_adapter
orchestrator = core.orchestrator
