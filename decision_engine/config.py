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

    # Scoring Weights (Must sum to 1.0 or scale appropriately)
    OCCUPANCY_WEIGHT: float = 0.4
    VEHICLE_WEIGHT: float = 0.3
    WAITING_WEIGHT: float = 0.1
    PEDESTRIAN_WEIGHT: float = 0.1
    STARVATION_WEIGHT: float = 0.1

    # Normalization Maxima
    MAX_EXPECTED_VEHICLES: int = 30
    MAX_EXPECTED_PEDESTRIANS: int = 10

    # System Configuration
    VALID_LANES: Set[str] = field(default_factory=lambda: {"north", "south", "east", "west"})
    DEFAULT_LANE: str = "north"

# Shared default configuration instance
DEFAULT_CONFIG = DecisionEngineConfig()
