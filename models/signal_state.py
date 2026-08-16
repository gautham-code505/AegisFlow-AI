"""
AegisFlow AI - SignalState Contract Model

Represents what the physical signal controller is currently executing.
"""

from typing import Optional
from pydantic import BaseModel, Field
from .enums import Lane, SignalColor, SignalPhase


class SignalState(BaseModel):
    """Actual real-time hardware execution status of intersection signal heads."""
    timestamp: float = Field(..., ge=0.0, description="Status snapshot timestamp in seconds")
    north: SignalColor = Field(default=SignalColor.RED, description="North signal light status")
    south: SignalColor = Field(default=SignalColor.RED, description="South signal light status")
    east: SignalColor = Field(default=SignalColor.RED, description="East signal light status")
    west: SignalColor = Field(default=SignalColor.RED, description="West signal light status")
    active_lane: Optional[Lane] = Field(default=None, description="Currently active approach lane receiving green phase")
    phase: SignalPhase = Field(default=SignalPhase.ALL_RED, description="Current phase (GREEN, YELLOW, ALL_RED)")
    remaining_seconds: int = Field(default=0, ge=0, description="Remaining seconds in active phase")
