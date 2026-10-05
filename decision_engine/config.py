from dataclasses import dataclass, field
from typing import Set

@dataclass
class DecisionEngineConfig:
    # Timing Limits
    MIN_GREEN_TIME: int = 10
    MAX_GREEN_TIME: int = 45
    DEFAULT_GREEN_DURATION: int = 15

    # Starvation Settings
    STARVATION_THRESHOLD: float = 60.0  # seconds
    MAX_CONSECUTIVE_SKIPS: int = 5

    # Scoring Weights (Normalized to 1.0)
    TRACKING_QUEUE_WEIGHT: float = 0.60
    TRACKING_DELAY_WEIGHT: float = 0.40
    
    FALLBACK_OCCUPANCY_WEIGHT: float = 0.50
    FALLBACK_VEHICLE_WEIGHT: float = 0.50

    # Normalization Maxima
    MAX_EXPECTED_VEHICLES: int = 30
    MAX_EXPECTED_QUEUED: int = 15
    MAX_EXPECTED_OBSERVED_WAIT: float = 60.0

    # System Configuration
    VALID_LANES: Set[str] = field(default_factory=lambda: {"north", "south", "east", "west"})
    DEFAULT_LANE: str = "north"

# Shared default configuration instance
DEFAULT_CONFIG = DecisionEngineConfig()
