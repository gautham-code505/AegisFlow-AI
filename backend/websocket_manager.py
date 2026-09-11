"""
AegisFlow AI - WebSocket Connection & Broadcast Manager

Manages client connections to /ws/traffic and broadcasts unified state snapshots.
Ensures WebSocket client failures/disconnects do not crash the backend loop.
"""

import logging
from typing import List, Optional, Dict, Any
from fastapi import WebSocket
from models import TrafficState, SignalDecision, SignalState, SystemStatus, Event, ServiceMeasurement

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages active WebSocket client connections for real-time traffic updates."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """Accepts incoming WebSocket connection and registers client."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket) -> None:
        """Removes disconnected WebSocket client cleanly."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Remaining connections: {len(self.active_connections)}")

    async def broadcast_snapshot(
        self,
        traffic_state: Optional[TrafficState],
        signal_decision: Optional[SignalDecision],
        signal_state: Optional[SignalState],
        system_status: SystemStatus,
        events: List[Event],
        measurements: List[ServiceMeasurement],
        approach_detections: Optional[Dict[str, Any]] = None,
        approach_statuses: Optional[Dict[str, str]] = None,
        safety_result: Optional[Dict[str, Any]] = None,
        analytics: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Broadcasts unified snapshot to all active clients.
        Includes per-approach detection metadata, input lifecycle status, and safety validation results.
        """
        payload = {
            "trafficState": traffic_state.model_dump() if traffic_state else None,
            "signalDecision": signal_decision.model_dump() if signal_decision else None,
            "signalState": signal_state.model_dump() if signal_state else None,
            "systemStatus": system_status.model_dump(),
            "events": [e.model_dump() for e in events],
            "measurements": [m.model_dump() for m in measurements] if measurements else [],
            "approachDetections": approach_detections or {},
            "approachStatuses": approach_statuses or {},
            "safetyResult": safety_result,
            "analytics": analytics or {},
        }

        stale_connections: List[WebSocket] = []
        for connection in list(self.active_connections):
            try:
                await connection.send_json(payload)
            except Exception as exc:
                logger.warning(f"Error sending WebSocket update, marking connection for removal: {exc}")
                stale_connections.append(connection)

        for conn in stale_connections:
            self.disconnect(conn)
