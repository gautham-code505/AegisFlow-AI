"""
AegisFlow AI Safety Validation Package
"""

from .models import ValidationResult, ValidationStatus
from .conflicts import ConflictMatrix
from .phase_groups import (
    PhaseGroup,
    PHASE_NS,
    PHASE_EW,
    PHASE_ALL_RED,
    SAFE_PHASE_GROUPS,
    get_safe_phases,
    is_compatible,
    get_phase_group,
    get_compatible_phase_for_lane,
    evaluate_phase_demand,
)
from .validator import SafetyValidator
from .fallback import FallbackController

__all__ = [
    "ValidationResult",
    "ValidationStatus",
    "ConflictMatrix",
    "PhaseGroup",
    "PHASE_NS",
    "PHASE_EW",
    "PHASE_ALL_RED",
    "SAFE_PHASE_GROUPS",
    "get_safe_phases",
    "is_compatible",
    "get_phase_group",
    "get_compatible_phase_for_lane",
    "evaluate_phase_demand",
    "SafetyValidator",
    "FallbackController",
]
