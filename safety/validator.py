"""
AegisFlow AI - Safety Validator

Central safety evaluation service. Validates proposed SignalDecision objects against
traffic state observations, current controller state, and safety rules before execution.
"""

import time
import logging
from typing import Optional, List
from models import TrafficState, SignalDecision, SignalState, Priority
from controller.config import ControllerConfig, DEFAULT_CONTROLLER_CONFIG
from .models import ValidationResult, ValidationStatus
from .rules import (
    check_lane_validity,
    check_duration_bounds,
    check_traffic_data_freshness,
    check_decision_freshness,
    check_minimum_green_hold,
)

logger = logging.getLogger(__name__)


class SafetyValidator:
    """Evaluates proposed SignalDecisions against safety rules and invariant constraints."""

    def __init__(self, config: ControllerConfig = DEFAULT_CONTROLLER_CONFIG):
        self.config = config

    def validate(
        self,
        current_signal_state: Optional[SignalState],
        proposed_decision: Optional[SignalDecision],
        traffic_state: Optional[TrafficState],
        current_time: Optional[float] = None,
    ) -> ValidationResult:
        """
        Evaluates safety rules for a proposed SignalDecision.
        Returns a comprehensive ValidationResult indicating APPROVED, REJECTED, or FALLBACK.
        """
        now = current_time if current_time is not None else time.time()
        rejection_reasons: List[str] = []

        # 1. Check for missing decision
        if not proposed_decision:
            logger.warning("Safety Validation: Proposed decision is missing. Triggering FALLBACK.")
            return ValidationResult(
                status=ValidationStatus.FALLBACK,
                approved=False,
                reasons=["Proposed decision recommendation is missing."],
            )

        # 2. Check TrafficState freshness
        stale_data_reasons = check_traffic_data_freshness(traffic_state, now, self.config)
        if stale_data_reasons:
            logger.warning(f"Safety Validation: Stale traffic data ({stale_data_reasons}). Triggering FALLBACK.")
            return ValidationResult(
                status=ValidationStatus.FALLBACK,
                approved=False,
                reasons=stale_data_reasons,
            )

        # 3. Check Decision freshness
        stale_decision_reasons = check_decision_freshness(proposed_decision, now, self.config)
        if stale_decision_reasons:
            logger.warning(f"Safety Validation: Stale decision ({stale_decision_reasons}). Rejecting decision.")
            rejection_reasons.extend(stale_decision_reasons)

        # 4. Check Lane enum validity
        lane_reasons = check_lane_validity(proposed_decision.selected_lane)
        if lane_reasons:
            rejection_reasons.extend(lane_reasons)

        # 5. Check Duration bounds
        duration_reasons = check_duration_bounds(proposed_decision.duration, self.config)
        if duration_reasons:
            rejection_reasons.extend(duration_reasons)

        # 6. Check Minimum Green hold if current signal is green (Emergency decisions may bypass min green if safe)
        if current_signal_state and proposed_decision.priority != Priority.EMERGENCY:
            min_green_reasons = check_minimum_green_hold(
                current_signal_state, proposed_decision.selected_lane, now, self.config
            )
            if min_green_reasons:
                rejection_reasons.extend(min_green_reasons)

        # If any rejection rules fired: REJECT decision
        if rejection_reasons:
            logger.warning(f"Safety Validation REJECTED decision: {rejection_reasons}")
            return ValidationResult(
                status=ValidationStatus.REJECTED,
                approved=False,
                reasons=rejection_reasons,
                proposed_lane=proposed_decision.selected_lane,
                proposed_duration=proposed_decision.duration,
            )

        # All safety rules passed -> APPROVE decision
        approval_reasons = [
            "All safety validation rules satisfied.",
            f"Selected lane '{proposed_decision.selected_lane.value.upper()}' approved.",
            f"Allocated green phase duration of {proposed_decision.duration}s within safe bounds.",
        ]

        logger.info(f"Safety Validation APPROVED decision for '{proposed_decision.selected_lane.value.upper()}' ({proposed_decision.duration}s)")
        return ValidationResult(
            status=ValidationStatus.APPROVED,
            approved=True,
            reasons=approval_reasons,
            proposed_lane=proposed_decision.selected_lane,
            proposed_duration=proposed_decision.duration,
        )
