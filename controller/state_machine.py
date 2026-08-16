"""
AegisFlow AI - Signal Controller State Machine

Manages active signal phases (GREEN -> YELLOW -> ALL_RED -> GREEN),
phase timers, multi-lane target transitions, and 4-way light color computation.
"""

from typing import Dict, Optional, List, Union, Set
from models import Lane, SignalColor, SignalPhase, SignalState
from .config import ControllerConfig, DEFAULT_CONTROLLER_CONFIG


class SignalStateMachine:
    """Finite State Machine driving 4-way signal light phase transitions."""

    def __init__(self, config: ControllerConfig = DEFAULT_CONTROLLER_CONFIG):
        self.config = config
        self.active_lanes: List[Lane] = []
        self.target_lanes: Optional[List[Lane]] = None
        self.target_duration: int = self.config.MIN_GREEN_SECONDS
        self.phase: SignalPhase = SignalPhase.ALL_RED
        self.phase_start_time: float = 0.0
        self.phase_duration: int = self.config.ALL_RED_SECONDS

    @property
    def active_lane(self) -> Optional[Lane]:
        """Primary active lane for backward compatibility."""
        return self.active_lanes[0] if self.active_lanes else None

    @active_lane.setter
    def active_lane(self, lane: Optional[Lane]) -> None:
        self.active_lanes = [lane] if lane else []

    @property
    def target_lane(self) -> Optional[Lane]:
        """Primary target lane for backward compatibility."""
        return self.target_lanes[0] if self.target_lanes else None

    @target_lane.setter
    def target_lane(self, lane: Optional[Lane]) -> None:
        self.target_lanes = [lane] if lane else None

    def initialize(self, timestamp: float) -> None:
        """Sets safe initial state: ALL RED for all approaches."""
        self.active_lanes = []
        self.target_lanes = None
        self.phase = SignalPhase.ALL_RED
        self.phase_start_time = timestamp
        self.phase_duration = 0

    def transition_to(
        self,
        new_phase: SignalPhase,
        active_lanes: Optional[Union[Lane, List[Lane], Set[Lane]]] = None,
        duration: int = 15,
        timestamp: float = 0.0,
        target_lanes: Optional[Union[Lane, List[Lane], Set[Lane]]] = None,
        target_duration: Optional[int] = None,
        active_lane: Optional[Lane] = None,
        target_lane: Optional[Lane] = None,
    ) -> None:
        """Executes a phase transition in the state machine."""
        self.phase = new_phase

        # Handle active_lanes / active_lane
        chosen_active = active_lanes if active_lanes is not None else active_lane
        if chosen_active is None:
            self.active_lanes = []
        elif isinstance(chosen_active, Lane):
            self.active_lanes = [chosen_active]
        else:
            self.active_lanes = list(chosen_active)

        # Handle target_lanes / target_lane
        chosen_target = target_lanes if target_lanes is not None else target_lane
        if chosen_target is None:
            self.target_lanes = None
        elif isinstance(chosen_target, Lane):
            self.target_lanes = [chosen_target]
        else:
            self.target_lanes = list(chosen_target)

        if target_duration is not None:
            self.target_duration = target_duration

        self.phase_duration = max(1, duration)
        self.phase_start_time = timestamp

    def get_remaining_seconds(self, current_time: float) -> int:
        """Calculates remaining seconds in the current active phase."""
        elapsed = current_time - self.phase_start_time
        remaining = self.phase_duration - int(elapsed)
        return max(0, remaining)

    def is_phase_complete(self, current_time: float) -> bool:
        """Checks if current phase duration has elapsed."""
        return (current_time - self.phase_start_time) >= self.phase_duration

    def compute_signal_colors(self) -> Dict[Lane, SignalColor]:
        """
        Computes 4-way signal light colors based on current phase and active lanes.
        Supports concurrent compatible green approaches.
        """
        colors: Dict[Lane, SignalColor] = {
            Lane.NORTH: SignalColor.RED,
            Lane.SOUTH: SignalColor.RED,
            Lane.EAST: SignalColor.RED,
            Lane.WEST: SignalColor.RED,
        }

        if self.phase == SignalPhase.GREEN:
            for lane in self.active_lanes:
                if lane in colors:
                    colors[lane] = SignalColor.GREEN
        elif self.phase == SignalPhase.YELLOW:
            for lane in self.active_lanes:
                if lane in colors:
                    colors[lane] = SignalColor.YELLOW
        # During SignalPhase.ALL_RED, all colors remain RED

        return colors

    def get_signal_state(self, current_time: float) -> SignalState:
        """Generates canonical SignalState snapshot."""
        colors = self.compute_signal_colors()
        remaining = self.get_remaining_seconds(current_time)

        return SignalState(
            timestamp=current_time,
            north=colors[Lane.NORTH],
            south=colors[Lane.SOUTH],
            east=colors[Lane.EAST],
            west=colors[Lane.WEST],
            active_lanes=list(self.active_lanes),
            active_lane=self.active_lane,
            phase=self.phase,
            remaining_seconds=remaining,
        )
