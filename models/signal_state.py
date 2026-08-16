"""
AegisFlow AI - SignalState Contract Model

Represents what the physical or virtual signal controller is currently executing.
Supports safe concurrent active lanes while maintaining single active_lane backward compatibility.
"""

from typing import Optional, List, Union
from pydantic import BaseModel, Field, model_validator
from .enums import Lane, SignalColor, SignalPhase


class SignalState(BaseModel):
    """Actual real-time execution status of intersection signal heads."""
    timestamp: float = Field(..., ge=0.0, description="Status snapshot timestamp in seconds")
    north: SignalColor = Field(default=SignalColor.RED, description="North signal light status")
    south: SignalColor = Field(default=SignalColor.RED, description="South signal light status")
    east: SignalColor = Field(default=SignalColor.RED, description="East signal light status")
    west: SignalColor = Field(default=SignalColor.RED, description="West signal light status")
    active_lanes: List[Lane] = Field(default_factory=list, description="List of currently active approach lanes")
    active_lane: Optional[Lane] = Field(default=None, description="Primary active approach lane for backward compatibility")
    phase: SignalPhase = Field(default=SignalPhase.ALL_RED, description="Current phase (GREEN, YELLOW, ALL_RED)")
    remaining_seconds: int = Field(default=0, ge=0, description="Remaining seconds in active phase")

    @model_validator(mode="after")
    def synchronize_active_lanes(self) -> "SignalState":
        """Ensures bidirectional synchronization between active_lanes and legacy active_lane."""
        if self.active_lanes and not self.active_lane:
            self.active_lane = self.active_lanes[0]
        elif self.active_lane and not self.active_lanes:
            self.active_lanes = [self.active_lane]
        elif not self.active_lanes and not self.active_lane:
            self.active_lanes = []
            self.active_lane = None
        return self
