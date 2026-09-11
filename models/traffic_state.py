"""
AegisFlow AI - TrafficState Contract Model

Represents what the Vision Perception system observed at an intersection approach.
"""

from typing import Dict, Optional
from pydantic import BaseModel, Field
from .enums import Lane


class LaneState(BaseModel):
    """Observation metrics for an individual traffic lane approach."""
    vehicle_count: int = Field(default=0, ge=0, description="Count of detected vehicles in lane")
    occupancy: float = Field(default=0.0, ge=0.0, le=1.0, description="Occupancy ratio between 0.0 and 1.0")
    pedestrian_count: int = Field(default=0, ge=0, description="Count of waiting pedestrians")
    heavy_vehicle_count: int = Field(default=0, ge=0, description="Count of heavy vehicles (trucks, buses)")
    has_media: bool = Field(default=False, description="Whether this approach has active media input")
    status: str = Field(default="WAITING_FOR_INPUT", description="Status: WAITING_FOR_INPUT, PROCESSING, ACTIVE, ERROR")
    queued_vehicle_count: int = Field(default=0, ge=0, description="Tracked vehicles currently stationary/queued (0 when tracking disabled)")
    moving_vehicle_count: int = Field(default=0, ge=0, description="Tracked vehicles currently moving through the ROI (0 when tracking disabled)")
    observed_average_wait: float = Field(default=0.0, ge=0.0, description="Average wait time of queued vehicles in seconds (0.0 when tracking disabled)")
    observed_max_wait: float = Field(default=0.0, ge=0.0, description="Max wait time of queued vehicles in seconds (0.0 when tracking disabled)")


class EmergencyState(BaseModel):
    """Status of emergency vehicle detection."""
    detected: bool = Field(default=False, description="Whether an emergency vehicle is detected")
    lane: Optional[Lane] = Field(default=None, description="Lane where emergency vehicle was detected")
    vehicle_type: Optional[str] = Field(default=None, description="Type of emergency vehicle e.g. AMBULANCE")
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Detection confidence score")
    vehicle_count: int = Field(default=0, ge=0, description="Number of emergency vehicles detected")


class TrafficState(BaseModel):
    """Complete traffic state snapshot observed by Vision system."""
    timestamp: float = Field(..., ge=0.0, description="Observation timestamp in seconds")
    frame_id: Optional[int] = Field(default=None, ge=0, description="Sequential vision frame index")
    source: Optional[str] = Field(default=None, description="Identifier for camera/video feed source")
    has_tracking_data: bool = Field(default=False, description="Explicitly indicates if tracking metrics (queued, moving) are populated")
    lanes: Dict[Lane, LaneState] = Field(
        default_factory=lambda: {
            Lane.NORTH: LaneState(),
            Lane.SOUTH: LaneState(),
            Lane.EAST: LaneState(),
            Lane.WEST: LaneState(),
        },
        description="Per-lane approach state mapping"
    )
    emergency: EmergencyState = Field(default_factory=EmergencyState, description="Emergency preemption state")
