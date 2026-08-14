from dataclasses import dataclass, field
from typing import Dict, List, Optional

@dataclass
class LaneState:
    vehicle_count: int
    occupancy: float  # Range: 0.0 - 1.0

@dataclass
class EmergencyState:
    detected: bool
    lane: Optional[str] = None

@dataclass
class TrafficState:
    timestamp: float
    lanes: Dict[str, LaneState]
    emergency: EmergencyState
    pedestrians: Optional[Dict[str, int]] = None

@dataclass
class SignalDecision:
    active_lane: str
    duration: int
    priority: str  # "normal", "emergency", "high"
    reason: List[str] = field(default_factory=list)
