"""
AegisFlow AI - Virtual Signal Controller

Virtual software controller driving physical signal transitions through safe state machine execution.
Supports concurrent compatible phase execution and generates canonical models.SignalState objects.
"""

import time
import logging
from typing import Optional, Union, List, Set
from models import Lane, SignalPhase, SignalState
from .config import ControllerConfig, DEFAULT_CONTROLLER_CONFIG
from .state_machine import SignalStateMachine
from safety.conflicts import ConflictMatrix

logger = logging.getLogger(__name__)


class VirtualSignalController:
    """Software virtual signal controller executing safe phase transitions."""

    def __init__(self, config: ControllerConfig = DEFAULT_CONTROLLER_CONFIG):
        self.config = config
        self.state_machine = SignalStateMachine(self.config)
        self.state_machine.initialize(time.time())

    def get_current_signal_state(self, current_time: Optional[float] = None) -> SignalState:
        """Returns the current canonical SignalState snapshot."""
        now = current_time if current_time is not None else time.time()
        
        # Fast-forward any pending automatic transitions (e.g. YELLOW -> ALL_RED -> target GREEN)
        max_iterations = 5
        for _ in range(max_iterations):
            if not self.state_machine.is_phase_complete(now):
                break
            prev_phase = self.state_machine.phase
            self.advance_time(now)
            if self.state_machine.phase == prev_phase:
                break
                
        return self.state_machine.get_signal_state(now)

    def execute_decision(
        self,
        target_lane: Union[Lane, List[Lane], Set[Lane]],
        duration: int,
        current_time: Optional[float] = None,
    ) -> SignalState:
        """
        Executes an approved signal decision for a target approach or compatible approach group.
        Handles phase transitions safely:
        - If current is GREEN on different lanes: GREEN -> YELLOW -> ALL_RED -> target GREEN
        - If current is GREEN on same lanes: extends GREEN phase up to MAX_GREEN_SECONDS
        - If current is ALL_RED: ALL_RED -> target GREEN
        """
        now = current_time if current_time is not None else time.time()
        current_phase = self.state_machine.phase
        current_active = set(self.state_machine.active_lanes)

        # Normalize target_lanes to List[Lane]
        if isinstance(target_lane, Lane):
            target_lanes = [target_lane]
        else:
            target_lanes = list(target_lane)

        target_set = set(target_lanes)

        # Defense-in-depth: check ConflictMatrix
        conflict_reasons = ConflictMatrix.check_target_lanes(target_lanes)
        if conflict_reasons:
            logger.error(f"Controller defense-in-depth REJECTED conflicting target lanes: {conflict_reasons}")
            return self.state_machine.get_signal_state(now)

        # Bound green duration between min and max config bounds
        bounded_duration = max(
            self.config.MIN_GREEN_SECONDS,
            min(self.config.MAX_GREEN_SECONDS, int(duration)),
        )

        target_names = "+".join([l.value.upper() for l in target_lanes])

        if current_phase == SignalPhase.GREEN and current_active == target_set:
            # Continue/Extend GREEN phase on same approaches
            logger.info(f"Extending GREEN phase on approach group [{target_names}] for {bounded_duration}s")
            self.state_machine.transition_to(
                new_phase=SignalPhase.GREEN,
                active_lanes=target_lanes,
                duration=bounded_duration,
                timestamp=now,
            )
        elif current_phase == SignalPhase.GREEN and current_active != target_set:
            # Initiate yellow clearance for current active lanes
            active_names = "+".join([l.value.upper() for l in current_active])
            logger.info(f"Initiating YELLOW clearance for [{active_names}] before switching to [{target_names}]")
            self.state_machine.transition_to(
                new_phase=SignalPhase.YELLOW,
                active_lanes=self.state_machine.active_lanes,
                duration=self.config.YELLOW_SECONDS,
                timestamp=now,
                target_lanes=target_lanes,
                target_duration=bounded_duration,
            )
        elif current_phase == SignalPhase.YELLOW:
            # Already in YELLOW phase, move to ALL_RED clearance
            logger.info(f"Transitioning from YELLOW clearance to ALL_RED clearance for target [{target_names}]")
            self.state_machine.transition_to(
                new_phase=SignalPhase.ALL_RED,
                active_lanes=[],
                duration=self.config.ALL_RED_SECONDS,
                timestamp=now,
                target_lanes=target_lanes,
                target_duration=bounded_duration,
            )
        else:
            # In ALL_RED phase or starting up: transition directly to target GREEN
            logger.info(f"Transitioning from ALL_RED to GREEN phase on approach group [{target_names}] for {bounded_duration}s")
            self.state_machine.transition_to(
                new_phase=SignalPhase.GREEN,
                active_lanes=target_lanes,
                duration=bounded_duration,
                timestamp=now,
            )

        return self.state_machine.get_signal_state(now)

    def advance_time(self, current_time: float) -> SignalState:
        """
        Advances controller clock and executes automatic phase progression
        (YELLOW -> ALL_RED -> target GREEN).
        """
        if self.state_machine.is_phase_complete(current_time):
            current_phase = self.state_machine.phase
            targets = self.state_machine.target_lanes

            # Calculate exact completion time to prevent clock drift during catch-up
            completion_time = self.state_machine.phase_start_time + self.state_machine.phase_duration
            if completion_time > current_time:
                completion_time = current_time

            if current_phase == SignalPhase.YELLOW:
                # Yellow completed -> transition to ALL_RED
                logger.info("YELLOW phase complete. Transitioning to ALL_RED clearance.")
                self.state_machine.transition_to(
                    new_phase=SignalPhase.ALL_RED,
                    active_lanes=[],
                    duration=self.config.ALL_RED_SECONDS,
                    timestamp=completion_time,
                    target_lanes=targets,
                )
            elif current_phase == SignalPhase.ALL_RED and targets is not None:
                # All-Red completed -> transition to target GREEN
                target_names = "+".join([l.value.upper() for l in targets])
                target_duration = self.state_machine.target_duration
                logger.info(f"ALL_RED clearance complete. Activating GREEN phase for [{target_names}].")
                self.state_machine.transition_to(
                    new_phase=SignalPhase.GREEN,
                    active_lanes=targets,
                    duration=target_duration,
                    timestamp=completion_time,
                    target_lanes=None,
                )

        return self.state_machine.get_signal_state(current_time)
