"""
AegisFlow AI - In-Memory State Store

Thread-safe in-memory state store for holding the latest TrafficState,
latest SignalDecision, latest SignalState, current SystemStatus, and a bounded event history (max 100).
"""

import time
import threading
from typing import List, Optional
from models import (
    TrafficState,
    SignalDecision,
    SignalState,
    SystemStatus,
    Event,
    SystemMode,
    Status,
)


class StateStore:
    """Thread-safe bounded in-memory state store for AegisFlow AI edge node."""

    def __init__(self, max_events: int = 100):
        self._lock = threading.RLock()
        self._max_events = max_events
        self._traffic_state: Optional[TrafficState] = None
        self._signal_decision: Optional[SignalDecision] = None
        self._signal_state: Optional[SignalState] = None
        self._events: List[Event] = []
        self._system_status: SystemStatus = SystemStatus(
            timestamp=time.time(),
            mode=SystemMode.LOCAL,
            internet=Status.OFFLINE,
            camera=Status.OFFLINE,
            vision=Status.OFFLINE,
            decision_engine=Status.ONLINE,
            safety=Status.ONLINE,
            controller=Status.ONLINE,
        )

    def set_traffic_state(self, state: Optional[TrafficState]) -> None:
        with self._lock:
            self._traffic_state = state

    def get_traffic_state(self) -> Optional[TrafficState]:
        with self._lock:
            return self._traffic_state

    def set_decision(self, decision: Optional[SignalDecision]) -> None:
        with self._lock:
            self._signal_decision = decision

    def get_decision(self) -> Optional[SignalDecision]:
        with self._lock:
            return self._signal_decision

    def set_signal_state(self, signal_state: Optional[SignalState]) -> None:
        with self._lock:
            self._signal_state = signal_state

    def get_signal_state(self) -> Optional[SignalState]:
        with self._lock:
            return self._signal_state

    def get_system_status(self) -> SystemStatus:
        with self._lock:
            return SystemStatus(
                timestamp=time.time(),
                mode=self._system_status.mode,
                internet=self._system_status.internet,
                camera=self._system_status.camera,
                vision=self._system_status.vision,
                decision_engine=self._system_status.decision_engine,
                safety=self._system_status.safety,
                controller=self._system_status.controller,
            )

    def set_system_status(self, status: SystemStatus) -> None:
        with self._lock:
            self._system_status = status

    def add_event(self, event: Event) -> None:
        with self._lock:
            self._events.append(event)
            if len(self._events) > self._max_events:
                self._events = self._events[-self._max_events:]

    def get_events(self, limit: int = 50) -> List[Event]:
        with self._lock:
            return list(self._events[-limit:])
