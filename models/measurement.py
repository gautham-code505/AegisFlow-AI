"""
AegisFlow AI - Measurement Contract Model

Represents a completed or active Service Interval measurement loop.
Captures observations before and after a GREEN service phase to assess impact neutrally.
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from .enums import Lane, Priority


class ServiceMeasurement(BaseModel):
    """Represents a measured interval of service (a GREEN phase)."""
    measurement_id: str = Field(..., description="Unique measurement identifier")
    target_lanes: List[Lane] = Field(..., description="Lanes serviced during this interval")
    start_timestamp: float = Field(..., ge=0.0, description="Authoritative timestamp when GREEN phase started")
    end_timestamp: Optional[float] = Field(default=None, description="Authoritative timestamp when GREEN phase ended (transition to YELLOW)")
    green_duration: Optional[float] = Field(default=None, description="Total duration of the GREEN phase in seconds")
    
    # Decision Context
    priority_type: Priority = Field(default=Priority.NORMAL, description="Priority type from the associated signal decision")
    decision_reason: Optional[str] = Field(default=None, description="Primary reason for the decision that initiated this service")
    decision_timestamp: Optional[float] = Field(default=None, description="Timestamp of the decision that initiated this service")

    # Tracking Availability
    has_tracking_data: bool = Field(default=False, description="Whether tracking metrics were available during this interval")

    # Before State (Captured at GREEN START)
    queue_before: Optional[int] = Field(default=None, description="Sum of queued tracked vehicles across target lanes before service")
    wait_avg_before: Optional[float] = Field(default=None, description="Max observed average wait across target lanes before service")
    wait_max_before: Optional[float] = Field(default=None, description="Max observed absolute wait across target lanes before service")
    
    # After State (Captured at GREEN END)
    queue_after: Optional[int] = Field(default=None, description="Sum of queued tracked vehicles across target lanes after service")
    wait_avg_after: Optional[float] = Field(default=None, description="Max observed average wait across target lanes after service")
    wait_max_after: Optional[float] = Field(default=None, description="Max observed absolute wait across target lanes after service")
