"""
AegisFlow AI - Signal Conflict Matrix

Defines legal approach relationships and evaluates signal head states against
explicitly permitted safe phase groups. Prevents conflicting cross-traffic green phases.
"""

from typing import Dict, List, Set, Iterable, Optional, TYPE_CHECKING
from models import Lane, SignalColor, SignalState
from .phase_groups import get_allowed_green_lane_sets

if TYPE_CHECKING:
    # Imported lazily at call time: controller imports this module, so a
    # module-level import would be circular.
    from controller.config import ControllerConfig


def _single_approach_phasing(config: Optional["ControllerConfig"]) -> bool:
    if config is None:
        from controller.config import DEFAULT_CONTROLLER_CONFIG
        config = DEFAULT_CONTROLLER_CONFIG
    return config.SINGLE_APPROACH_PHASING


class ConflictMatrix:
    """Evaluates 4-way signal light configurations against permitted safe phase groups."""

    @classmethod
    def check_target_lanes(
        cls,
        target_lanes: Iterable[Lane],
        config: Optional["ControllerConfig"] = None,
    ) -> List[str]:
        """
        Checks a proposed set of target lanes for conflict violations.
        Returns a list of conflict error messages if the set of approaches
        does not match any phase group permitted by the active phasing policy.
        """
        active_approaches = set(target_lanes)
        conflicts: List[str] = []
        single_approach = _single_approach_phasing(config)
        if frozenset(active_approaches) not in get_allowed_green_lane_sets(single_approach):
            active_names = sorted([l.value.upper() for l in active_approaches])
            permitted = (
                "a single approach phase or ALL_RED (single-approach phasing)"
                if single_approach
                else "NORTH+SOUTH, EAST+WEST, single approach phases, or ALL_RED"
            )
            conflicts.append(
                f"SAFETY CONFLICT VIOLATION: Active approach combination ({', '.join(active_names)}) "
                f"is not an explicitly permitted safe phase group. Permitted groups: {permitted}."
            )
        return conflicts

    @classmethod
    def check_conflict(
        cls,
        signal_colors: Dict[Lane, SignalColor],
        config: Optional["ControllerConfig"] = None,
    ) -> List[str]:
        """
        Checks signal light colors for conflict violations.
        Returns a list of conflict error messages if the set of active (GREEN or YELLOW)
        approaches does not match any explicitly declared safe phase group.
        """
        active_approaches: Set[Lane] = set()
        for lane, color in signal_colors.items():
            if color in (SignalColor.GREEN, SignalColor.YELLOW):
                active_approaches.add(lane)

        return cls.check_target_lanes(active_approaches, config)

    @classmethod
    def is_safe_signal_state(
        cls,
        signal_state: SignalState,
        config: Optional["ControllerConfig"] = None,
    ) -> bool:
        """Returns True if SignalState satisfies the conflict matrix safety invariants."""
        colors = {
            Lane.NORTH: signal_state.north,
            Lane.SOUTH: signal_state.south,
            Lane.EAST: signal_state.east,
            Lane.WEST: signal_state.west,
        }
        conflicts = cls.check_conflict(colors, config)
        return len(conflicts) == 0
