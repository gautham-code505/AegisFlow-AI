"""
AegisFlow AI - In-Memory State Store

Thread-safe in-memory state store for holding the latest TrafficState,
latest SignalDecision, latest SignalState, current SystemStatus, and a bounded event history (max 100).
"""

import time
import threading
from typing import Dict, Any, List, Optional
from models import (
    TrafficState,
    SignalDecision,
    SignalState,
    SystemStatus,
    Event,
    ServiceMeasurement,
    EventCategory,
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
        self._measurements: List[ServiceMeasurement] = []
        self._approach_detections: Dict[str, Any] = {}
        self._approach_statuses: Dict[str, str] = {}
        self._safety_result: Optional[Dict[str, Any]] = None
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

    def set_approach_detections(self, approach: str, detections: Dict[str, Any]) -> None:
        """Store per-approach detection metadata for frontend display."""
        with self._lock:
            self._approach_detections[approach.lower()] = detections

    def get_approach_detections(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._approach_detections)
            
    def set_approach_status(self, approach: str, status: str) -> None:
        """Store per-approach input lifecycle status."""
        with self._lock:
            if not hasattr(self, '_approach_statuses'):
                self._approach_statuses = {}
            self._approach_statuses[approach.lower()] = status
            
    def get_approach_status(self, approach: str) -> str:
        """Get per-approach input lifecycle status."""
        with self._lock:
            if not hasattr(self, '_approach_statuses'):
                self._approach_statuses = {}
            return self._approach_statuses.get(approach.lower(), "WAITING_FOR_INPUT")
            
    def get_all_approach_statuses(self) -> Dict[str, str]:
        """Get all approach statuses."""
        with self._lock:
            if not hasattr(self, '_approach_statuses'):
                self._approach_statuses = {}
            return dict(self._approach_statuses)

    def set_safety_result(self, result: Dict[str, Any]) -> None:
        """Store the latest safety validation result for frontend display."""
        with self._lock:
            self._safety_result = result

    def get_safety_result(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._safety_result

    def add_event(self, event: Event) -> None:
        with self._lock:
            self._events.append(event)
            if len(self._events) > self._max_events:
                self._events = self._events[-self._max_events:]

    def get_events(self, limit: int = 50) -> List[Event]:
        with self._lock:
            return list(self._events[-limit:])

    def add_measurement(self, measurement: ServiceMeasurement) -> None:
        with self._lock:
            self._measurements.append(measurement)
            if len(self._measurements) > self._max_events:
                self._measurements = self._measurements[-self._max_events:]

    def get_measurements(self, limit: int = 50) -> List[ServiceMeasurement]:
        with self._lock:
            return list(self._measurements[-limit:])
            
    def clear_history(self) -> None:
        """Clears events and measurements history."""
        with self._lock:
            self._events.clear()
            self._measurements.clear()

    def get_analytics(self) -> Dict[str, Any]:
        """Calculates historical backend analytics from bounded state."""
        with self._lock:
            events = list(self._events)
            measurements = list(self._measurements)
            
        completed_measurements = [m for m in measurements if m.end_timestamp is not None]
        
        wait_avgs = [m.wait_avg_after for m in completed_measurements if m.wait_avg_after is not None]
        wait_maxs = [m.wait_max_after for m in completed_measurements if m.wait_max_after is not None]
        
        qb = [m.queue_before for m in completed_measurements if m.queue_before is not None]
        qa = [m.queue_after for m in completed_measurements if m.queue_after is not None]
        
        wb = [m.wait_avg_before for m in completed_measurements if m.wait_avg_before is not None]
        
        avg_wait = sum(wait_avgs) / len(wait_avgs) if wait_avgs else None
        max_wait = max(wait_maxs) if wait_maxs else None
        avg_queue_before = sum(qb) / len(qb) if qb else None
        avg_queue_after = sum(qa) / len(qa) if qa else None
        
        avg_queue_change = None
        if avg_queue_before is not None and avg_queue_after is not None:
            avg_queue_change = avg_queue_after - avg_queue_before
            
        avg_wait_change = None
        if wb and wait_avgs:
            avg_wait_before_val = sum(wb) / len(wb)
            avg_wait_change = avg_wait - avg_wait_before_val

        decisions = [e for e in events if e.category == EventCategory.DECISION]
        emergencies = [e for e in events if e.category == EventCategory.EMERGENCY and "activated" in e.message.lower() or "detected" in e.message.lower()]
        safety_rejections = [e for e in events if e.category == EventCategory.SAFETY and "rejected" in e.message.lower()]

        decision_counts = {}
        for d in decisions:
            # Extract priority from message e.g. "NORTH selected (NORMAL)." -> "NORMAL"
            import re
            match = re.search(r'\((.*?)\)', d.message)
            if match:
                dt = match.group(1)
                decision_counts[dt] = decision_counts.get(dt, 0) + 1

        return {
            "completed_service_intervals": len(completed_measurements),
            "average_observed_wait": round(avg_wait, 1) if avg_wait is not None else None,
            "maximum_observed_wait": round(max_wait, 1) if max_wait is not None else None,
            "average_queue_before": round(avg_queue_before, 1) if avg_queue_before is not None else None,
            "average_queue_after": round(avg_queue_after, 1) if avg_queue_after is not None else None,
            "average_observed_queue_change": round(avg_queue_change, 1) if avg_queue_change is not None else None,
            "average_observed_wait_change": round(avg_wait_change, 1) if avg_wait_change is not None else None,
            "decision_counts": decision_counts,
            "emergency_event_count": len(emergencies),
            "safety_rejection_count": len(safety_rejections),
        }

