from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum

class Priority(str, Enum):
    NORMAL = "NORMAL"
    EMERGENCY = "EMERGENCY"
    STARVATION_PREVENTION = "STARVATION_PREVENTION"

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
    decision_id: str
    timestamp: float
    selected_lane: str
    duration: int
    priority: Priority
    reasons: List[str] = field(default_factory=list)
    score_breakdown: Dict[str, float] = field(default_factory=dict)
    confidence: Optional[float] = None

    @property
    def active_lane(self) -> str:
        return self.selected_lane

    @property
    def reason(self) -> List[str]:
        return self.reasons
