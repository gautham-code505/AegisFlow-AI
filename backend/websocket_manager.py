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
        self._last_broadcast_time = 0.0
        self._last_broadcast_phase = None
        self._last_broadcast_lanes = None
        self._last_broadcast_status_mode = None
        self._last_broadcast_status_camera = None
        self._last_broadcast_status_vision = None
        self._last_broadcast_status_controller = None

    async def connect(self, websocket: WebSocket) -> None:
        """Accepts incoming WebSocket connection and registers client."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total connections: {len(self.active_connections)}")
        # Reset throttling state on new connection to ensure immediate first payload
        self._last_broadcast_time = 0.0

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
        Includes state-aware throttling to prevent flooding React frontends.
        Updates are limited to ~1 per second UNLESS a meaningful state change occurs.
        """
        if not self.active_connections:
            return

        import time
        now = time.time()
        
        # Determine if this broadcast contains a significant state change
        is_significant = False
        
        # 1. Safety Rejection or Fallback
        if safety_result and safety_result.get("status") != "APPROVED":
            is_significant = True
            
        # 2. Emergency detected
        if signal_decision and signal_decision.priority.value == "EMERGENCY":
            is_significant = True
            
        # 3. SignalState changes
        if signal_state:
            if self._last_broadcast_phase != signal_state.phase:
                is_significant = True
            if self._last_broadcast_lanes != signal_state.active_lanes:
                is_significant = True
                
        # 4. System Status changes (Source start/stop, failure, HW status)
        if system_status:
            if self._last_broadcast_status_mode != system_status.mode:
                is_significant = True
            if self._last_broadcast_status_camera != system_status.camera:
                is_significant = True
            if self._last_broadcast_status_vision != system_status.vision:
                is_significant = True
            if self._last_broadcast_status_controller != system_status.controller:
                is_significant = True

        # Throttle logic
        if not is_significant and (now - self._last_broadcast_time) < 1.0:
            return

        # Update tracking variables
        self._last_broadcast_time = now
        if signal_state:
            self._last_broadcast_phase = signal_state.phase
            self._last_broadcast_lanes = signal_state.active_lanes
        if system_status:
            self._last_broadcast_status_mode = system_status.mode
            self._last_broadcast_status_camera = system_status.camera
            self._last_broadcast_status_vision = system_status.vision
            self._last_broadcast_status_controller = system_status.controller

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
