"""
AegisFlow AI - Safety Data Models

Validation result structures and evaluation status enumerations for safety auditing.
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
from models import Lane


class ValidationStatus(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    FALLBACK = "FALLBACK"


class ValidationResult(BaseModel):
    """Detailed audit result returned by SafetyValidator."""
    status: ValidationStatus = Field(..., description="Validation outcome status")
    approved: bool = Field(..., description="Boolean flag indicating if proposed decision is approved for execution")
    reasons: List[str] = Field(default_factory=list, description="Detailed explanation trace for validation result")
    proposed_lane: Optional[Lane] = Field(default=None, description="Validated lane selection")
    proposed_duration: Optional[int] = Field(default=None, description="Validated green duration")
