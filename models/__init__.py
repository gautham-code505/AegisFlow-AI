"""
AegisFlow AI Shared Contract Models Package

Single source of truth Pydantic models and canonical enums exchanged across:
Vision Perception -> TrafficState -> Decision Engine -> SignalDecision -> Safety/Controller -> SignalState -> Dashboard.
"""

from .enums import Lane, SignalColor, SignalPhase, EventSeverity, EventCategory, SystemMode, Status, Priority
from .traffic_state import TrafficState, LaneState, EmergencyState
from .signal_state import SignalState
from .signal_decision import SignalDecision
from .system_status import SystemStatus
from .events import Event
from .measurement import ServiceMeasurement

__all__ = [
    "Lane",
    "SignalColor",
    "SignalPhase",
    "EventSeverity",
    "EventCategory",
    "SystemMode",
    "Status",
    "Priority",
    "TrafficState",
    "LaneState",
    "EmergencyState",
    "SignalState",
    "SignalDecision",
    "SystemStatus",
    "Event",
    "ServiceMeasurement",
]
