"""
AegisFlow AI - Signal Conflict Matrix

Defines legal approach relationships and evaluates signal head states against
explicitly permitted safe phase groups. Prevents conflicting cross-traffic green phases.
"""

from typing import Dict, List, Set
from models import Lane, SignalColor, SignalState
from .phase_groups import is_compatible, ALLOWED_GREEN_LANE_SETS


class ConflictMatrix:
    """Evaluates 4-way signal light configurations against permitted safe phase groups."""

    @staticmethod
    def check_conflict(signal_colors: Dict[Lane, SignalColor]) -> List[str]:
        """
        Checks signal light colors for conflict violations.
        Returns a list of conflict error messages if the set of active (GREEN or YELLOW)
        approaches does not match any explicitly declared safe phase group.
        """
        active_approaches: Set[Lane] = set()
        for lane, color in signal_colors.items():
            if color in (SignalColor.GREEN, SignalColor.YELLOW):
                active_approaches.add(lane)

        conflicts: List[str] = []
        if not is_compatible(active_approaches):
            active_names = sorted([l.value.upper() for l in active_approaches])
            conflicts.append(
                f"SAFETY CONFLICT VIOLATION: Active approach combination ({', '.join(active_names)}) "
                "is not an explicitly permitted safe phase group. Permitted groups: "
                "NORTH+SOUTH, EAST+WEST, single approach phases, or ALL_RED."
            )

        return conflicts

    @classmethod
    def is_safe_signal_state(cls, signal_state: SignalState) -> bool:
        """Returns True if SignalState satisfies the conflict matrix safety invariants."""
        colors = {
            Lane.NORTH: signal_state.north,
            Lane.SOUTH: signal_state.south,
            Lane.EAST: signal_state.east,
            Lane.WEST: signal_state.west,
        }
        conflicts = cls.check_conflict(colors)
        return len(conflicts) == 0
