"""
AegisFlow AI - Safe Fallback Controller

Provides deterministic round-robin signal control when perception, decision engine,
or safety validation failures prevent safe adaptive operation.
"""

import time
import logging
from typing import List, Optional
from models import Lane, SignalPhase, SignalState
from controller.config import ControllerConfig, DEFAULT_CONTROLLER_CONFIG
from controller.state_machine import SignalStateMachine

logger = logging.getLogger(__name__)

FALLBACK_SEQUENCE: List[Lane] = [Lane.NORTH, Lane.EAST, Lane.SOUTH, Lane.WEST]


class FallbackController:
    """Safe fixed-cycle round-robin fallback manager."""

    def __init__(self, config: ControllerConfig = DEFAULT_CONTROLLER_CONFIG):
        self.config = config
        self.state_machine = SignalStateMachine(self.config)
        self.sequence_index: int = 0
        self._initialized: bool = False

    def get_fallback_signal_state(self, current_time: Optional[float] = None) -> SignalState:
        """
        Calculates and returns the current safe fallback SignalState snapshot.
        Progresses deterministically through NORTH -> EAST -> SOUTH -> WEST sequence
        with full yellow and all-red clearance intervals between approaches.
        """
        now = current_time if current_time is not None else time.time()

        if not self._initialized:
            self.state_machine.initialize(now)
            self._initialized = True

        max_iterations = 5
        for _ in range(max_iterations):
            if not self.state_machine.is_phase_complete(now):
                break

            current_phase = self.state_machine.phase
            active_lane = self.state_machine.active_lane

            completion_time = self.state_machine.phase_start_time + self.state_machine.phase_duration
            if completion_time > now:
                completion_time = now

            if current_phase == SignalPhase.ALL_RED or active_lane is None:
                # Transition from ALL_RED to next GREEN in sequence
                next_lane = FALLBACK_SEQUENCE[self.sequence_index % len(FALLBACK_SEQUENCE)]
                self.sequence_index += 1
                logger.warning(f"[FALLBACK MODE] Activating safe green phase for approach '{next_lane.value.upper()}' ({self.config.FALLBACK_GREEN_SECONDS}s)")
                self.state_machine.transition_to(
                    new_phase=SignalPhase.GREEN,
                    active_lane=next_lane,
                    duration=self.config.FALLBACK_GREEN_SECONDS,
                    timestamp=completion_time if active_lane is None else completion_time,
                )
            elif current_phase == SignalPhase.GREEN:
                # Transition from GREEN to YELLOW clearance
                logger.warning(f"[FALLBACK MODE] Initiating YELLOW clearance for approach '{active_lane.value.upper()}' ({self.config.YELLOW_SECONDS}s)")
                self.state_machine.transition_to(
                    new_phase=SignalPhase.YELLOW,
                    active_lane=active_lane,
                    duration=self.config.YELLOW_SECONDS,
                    timestamp=completion_time,
                )
            elif current_phase == SignalPhase.YELLOW:
                # Transition from YELLOW to ALL_RED clearance
                logger.warning(f"[FALLBACK MODE] Initiating ALL_RED clearance ({self.config.ALL_RED_SECONDS}s)")
                self.state_machine.transition_to(
                    new_phase=SignalPhase.ALL_RED,
                    active_lane=None,
                    duration=self.config.ALL_RED_SECONDS,
                    timestamp=completion_time,
                )

        return self.state_machine.get_signal_state(now)
