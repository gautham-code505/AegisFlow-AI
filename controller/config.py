"""
AegisFlow AI - Controller & Safety Configuration Parameters

Centralized constants and default timing thresholds for signal control,
phase transitions, clearance intervals, and safety monitoring.
"""

from pydantic import BaseModel, Field


class ControllerConfig(BaseModel):
    """Configuration settings for virtual signal controller and safety validator."""

    # Phase Timing Thresholds (Seconds)
    MIN_GREEN_SECONDS: int = Field(default=10, ge=1, description="Minimum green phase duration")
    MAX_GREEN_SECONDS: int = Field(default=60, ge=10, description="Maximum green phase duration")
    YELLOW_SECONDS: int = Field(default=3, ge=1, description="Yellow clearance phase duration")
    ALL_RED_SECONDS: int = Field(default=2, ge=1, description="All-red clearance phase duration")
    FALLBACK_GREEN_SECONDS: int = Field(default=15, ge=5, description="Green duration during safe fallback cycle")

    # Phasing Policy
    SINGLE_APPROACH_PHASING: bool = Field(
        default=True,
        description="Only one approach may be GREEN at a time (protected phase per approach). "
                    "False re-enables paired NORTH+SOUTH / EAST+WEST corridor phases.",
    )

    # Safety Monitoring Thresholds (Seconds)
    STALE_DATA_SECONDS: float = Field(default=3.0, ge=1.0, description="Max allowed age for TrafficState before it is treated as stale (forces ALL_RED)")
    DECISION_TIMEOUT_SECONDS: float = Field(default=5.0, ge=1.0, description="Max allowed age for SignalDecision before rejection")


# Shared global configuration instance
DEFAULT_CONTROLLER_CONFIG = ControllerConfig()
