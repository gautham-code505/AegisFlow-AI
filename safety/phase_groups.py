"""
AegisFlow AI - Safe Concurrent Phase Groups

Defines canonical, configurable, and deterministic compatible signal phase groups.
Ensures only explicitly permitted approach combinations can receive concurrent green phases.
"""

from typing import Set, List, Optional, Dict
from pydantic import BaseModel, Field
from models import Lane, TrafficState


class PhaseGroup(BaseModel):
    """Represents an explicitly permitted safe signal phase group."""
    name: str = Field(..., description="Unique phase group identifier")
    green_lanes: Set[Lane] = Field(default_factory=set, description="Set of approaches permitted to receive green")
    red_lanes: Set[Lane] = Field(default_factory=set, description="Set of approaches required to remain red")


ALL_LANES: Set[Lane] = {Lane.NORTH, Lane.SOUTH, Lane.EAST, Lane.WEST}

# Canonical Phase Group Definitions
PHASE_NS = PhaseGroup(
    name="NORTH_SOUTH",
    green_lanes={Lane.NORTH, Lane.SOUTH},
    red_lanes={Lane.EAST, Lane.WEST},
)

PHASE_EW = PhaseGroup(
    name="EAST_WEST",
    green_lanes={Lane.EAST, Lane.WEST},
    red_lanes={Lane.NORTH, Lane.SOUTH},
)

PHASE_ALL_RED = PhaseGroup(
    name="ALL_RED",
    green_lanes=set(),
    red_lanes=ALL_LANES,
)

# Single Approach Phases (e.g. for dedicated emergency priority or specific maneuvers)
PHASE_NORTH = PhaseGroup(name="NORTH", green_lanes={Lane.NORTH}, red_lanes={Lane.SOUTH, Lane.EAST, Lane.WEST})
PHASE_SOUTH = PhaseGroup(name="SOUTH", green_lanes={Lane.SOUTH}, red_lanes={Lane.NORTH, Lane.EAST, Lane.WEST})
PHASE_EAST = PhaseGroup(name="EAST", green_lanes={Lane.EAST}, red_lanes={Lane.NORTH, Lane.SOUTH, Lane.WEST})
PHASE_WEST = PhaseGroup(name="WEST", green_lanes={Lane.WEST}, red_lanes={Lane.NORTH, Lane.SOUTH, Lane.EAST})

SAFE_PHASE_GROUPS: List[PhaseGroup] = [
    PHASE_NS,
    PHASE_EW,
    PHASE_ALL_RED,
    PHASE_NORTH,
    PHASE_SOUTH,
    PHASE_EAST,
    PHASE_WEST,
]

# Set of all explicitly permitted green lane combinations
ALLOWED_GREEN_LANE_SETS: Set[frozenset] = {
    frozenset(pg.green_lanes) for pg in SAFE_PHASE_GROUPS
}


def get_safe_phases() -> List[PhaseGroup]:
    """Returns the list of all explicitly declared safe phase groups."""
    return list(SAFE_PHASE_GROUPS)


def is_compatible(green_lanes: Set[Lane]) -> bool:
    """Returns True if the given set of green lanes is an explicitly declared safe phase group."""
    return frozenset(green_lanes) in ALLOWED_GREEN_LANE_SETS


def get_phase_group(name: str) -> Optional[PhaseGroup]:
    """Retrieves a PhaseGroup by its unique name (case-insensitive)."""
    normalized = name.strip().upper().replace(" ", "_").replace("-", "_")
    for pg in SAFE_PHASE_GROUPS:
        if pg.name.upper() == normalized:
            return pg
    return None


def get_compatible_phase_for_lane(lane: Lane) -> PhaseGroup:
    """Maps an individual lane to its primary compatible corridor phase group."""
    if lane in (Lane.NORTH, Lane.SOUTH):
        return PHASE_NS
    elif lane in (Lane.EAST, Lane.WEST):
        return PHASE_EW
    return PHASE_ALL_RED


def evaluate_phase_demand(traffic_state: TrafficState) -> Dict[str, float]:
    """
    Calculates aggregate demand scores for safe corridor phase groups.
    Combines normalized occupancy and vehicle counts deterministically.
    """
    lanes = traffic_state.lanes
    ns_occupancy = lanes[Lane.NORTH].occupancy + lanes[Lane.SOUTH].occupancy
    ns_vehicles = lanes[Lane.NORTH].vehicle_count + lanes[Lane.SOUTH].vehicle_count
    ns_score = (ns_occupancy * 100.0) + (ns_vehicles * 1.5)

    ew_occupancy = lanes[Lane.EAST].occupancy + lanes[Lane.WEST].occupancy
    ew_vehicles = lanes[Lane.EAST].vehicle_count + lanes[Lane.WEST].vehicle_count
    ew_score = (ew_occupancy * 100.0) + (ew_vehicles * 1.5)

    return {
        "NORTH_SOUTH": round(ns_score, 2),
        "EAST_WEST": round(ew_score, 2),
    }
