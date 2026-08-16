"""
AegisFlow AI - Shared Contract Enums

Canonical enums used across all AegisFlow AI sub-systems (Vision, Decision Engine, Controller, Dashboard).
"""

from enum import Enum


class StrEnum(str, Enum):
    """Base string enum for clean JSON serialization."""
    def __str__(self) -> str:
        return str(self.value)


class Lane(StrEnum):
    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"


class SignalColor(StrEnum):
    RED = "RED"
    YELLOW = "YELLOW"
    GREEN = "GREEN"


class SignalPhase(StrEnum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    ALL_RED = "ALL_RED"


class Priority(StrEnum):
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    EMERGENCY = "EMERGENCY"
    FALLBACK = "FALLBACK"
    MANUAL = "MANUAL"


class SystemMode(StrEnum):
    LOCAL = "LOCAL"
    MOCK = "MOCK"
    FALLBACK = "FALLBACK"


class Status(StrEnum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    DEGRADED = "DEGRADED"
    ERROR = "ERROR"


class EventSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
