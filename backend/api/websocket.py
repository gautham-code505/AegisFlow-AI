"""
AegisFlow AI - WebSocket Endpoints
"""
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

def create_websocket_router(state_store, orchestrator, ws_manager, logger: logging.Logger):
    router = APIRouter()

    @router.websocket("/ws/traffic")
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

    return router
