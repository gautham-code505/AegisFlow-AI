"""
AegisFlow AI Shared Contract Models Package

Single source of truth Pydantic models and canonical enums exchanged across:
Vision Perception -> TrafficState -> Decision Engine -> SignalDecision -> Safety/Controller -> SignalState -> Dashboard.
"""

from .enums import (
    Lane,
    SignalColor,
    SignalPhase,
    Priority,
    SystemMode,
    Status,
    EventSeverity,
)
from .traffic_state import LaneState, EmergencyState, TrafficState
from .signal_decision import SignalDecision
from .signal_state import SignalState
from .system_status import SystemStatus
from .events import Event

__all__ = [
    "Lane",
    "SignalColor",
    "SignalPhase",
    "Priority",
    "SystemMode",
    "Status",
    "EventSeverity",
    "LaneState",
    "EmergencyState",
    "TrafficState",
    "SignalDecision",
    "SignalState",
    "SystemStatus",
    "Event",
]
