"""
AegisFlow AI - SystemStatus Contract Model

Represents edge node subsystem telemetry and health status.
"""

from pydantic import BaseModel, Field
from .enums import SystemMode, Status


class SystemStatus(BaseModel):
    """Subsystem operational mode and status metrics."""
    timestamp: float = Field(..., ge=0.0, description="Status sample timestamp in seconds")
    mode: SystemMode = Field(default=SystemMode.LOCAL, description="Operating execution mode")
    internet: Status = Field(default=Status.OFFLINE, description="Cloud connectivity status")
    camera: Status = Field(default=Status.OFFLINE, description="Video feed camera status")
    vision: Status = Field(default=Status.OFFLINE, description="Vision perception pipeline status")
    decision_engine: Status = Field(default=Status.OFFLINE, description="Decision Engine algorithm status")
    safety: Status = Field(default=Status.OFFLINE, description="Safety Validator engine status")
    controller: Status = Field(default=Status.OFFLINE, description="Hardware controller interface status")
