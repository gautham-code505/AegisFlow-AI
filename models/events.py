"""
AegisFlow AI - Event Contract Model

Represents system audit logs and operational event signals.
"""

from pydantic import BaseModel, Field
from .enums import EventSeverity


class Event(BaseModel):
    """System event record for audit trails and alert feeds."""
    event_id: str = Field(..., description="Unique event record identifier")
    timestamp: float = Field(..., ge=0.0, description="Event generation timestamp in seconds")
    type: str = Field(
        ...,
        description="Event classification type e.g. TRAFFIC_UPDATE, SIGNAL_DECISION, SIGNAL_CHANGED, EMERGENCY_DETECTED, SYSTEM_WARNING, SYSTEM_ERROR, FALLBACK_ACTIVATED, OVERRIDE_REQUEST, OVERRIDE_REJECTED"
    )
    severity: EventSeverity = Field(default=EventSeverity.INFO, description="Event severity classification")
    message: str = Field(..., description="Human-readable event message description")
