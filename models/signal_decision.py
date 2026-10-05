"""
AegisFlow AI - SignalDecision Contract Model

Represents what the Decision Engine recommends for signal control.
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from .enums import Lane, Priority


class SignalDecision(BaseModel):
    """Signal decision output recommendation from Decision Engine."""
    decision_id: str = Field(..., description="Unique decision identifier")
    timestamp: float = Field(..., ge=0.0, description="Decision creation timestamp in seconds")
    selected_lane: Lane = Field(..., description="Lane recommended for green phase allocation")
    duration: int = Field(..., gt=0, description="Recommended green phase duration in seconds (>0)")
    priority: Priority = Field(default=Priority.NORMAL, description="Decision priority level")
    reasons: List[str] = Field(default_factory=list, description="Explainable reason trace for decision")
    score_breakdown: Optional[Dict[str, Any]] = Field(default=None, description="Detailed algorithm scoring metrics per lane")
