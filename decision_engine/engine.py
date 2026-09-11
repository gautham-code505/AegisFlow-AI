import logging
from typing import Dict, Union, Any, List

from models import TrafficState, SignalDecision, LaneState, Lane, Priority
from .config import DecisionEngineConfig, DEFAULT_CONFIG
from .validator import validate_traffic_state
from .emergency import check_emergency
from .starvation import check_starvation
from .scorer import calculate_lane_scores
from .timing import calculate_green_time

import uuid

logger = logging.getLogger(__name__)

class DecisionEngine:
    def __init__(self, config: DecisionEngineConfig = DEFAULT_CONFIG):
        """
        Initializes the DecisionEngine with configurations and sets up
        the internal state tracker for waiting times and skips.
        """
        self.config = config
        
        # Internal state tracking uses string representations for config compatibility
        self.waiting_times: Dict[str, float] = {lane: 0.0 for lane in self.config.VALID_LANES}
        self.consecutive_skips: Dict[str, int] = {lane: 0 for lane in self.config.VALID_LANES}
        
        self.last_timestamp: Any = None
        self.last_active_lane: Any = None
        self.last_duration: float = 0.0
        self.last_scores: Dict[str, Any] = {}

    def decide(self, traffic_state: Union[dict, TrafficState]) -> SignalDecision:
        """
        Determines the next signal decision based on the traffic state input.
        Handles emergency overrides, starvation checks, scoring, dynamic timing,
        and updates internal state.
        """
        # 1. Validate and sanitize input
        state, warnings = validate_traffic_state(traffic_state, self.config)
        for warning in warnings:
            logger.warning(warning)

        # 2. Update waiting times based on elapsed time since last decision
        if self.last_timestamp is not None:
            if state.timestamp > self.last_timestamp:
                elapsed = state.timestamp - self.last_timestamp
            else:
                elapsed = float(self.last_duration)

            for lane in self.config.VALID_LANES:
                # If the lane was skipped in the previous cycle, increment its waiting time
                if lane != self.last_active_lane:
                    self.waiting_times[lane] += elapsed
        else:
            # First cycle: initialize last timestamp
            self.last_timestamp = state.timestamp

        # 3. Calculate scores for all lanes
        scores = calculate_lane_scores(state, self.waiting_times, self.consecutive_skips, self.config)
        self.last_scores = scores

        # 4. Process Decision Tiers
        active_lane_str = self.config.DEFAULT_LANE
        priority = Priority.NORMAL
        reasons: List[str] = []

        # Tier 1: Emergency Vehicle Override
        emergency_override = check_emergency(state, scores)
        if emergency_override is not None:
            active_lane_str, priority_str, reasons = emergency_override
            priority = Priority.EMERGENCY if priority_str == "EMERGENCY" else Priority(priority_str)
            if warnings:
                reasons.append("Handled invalid input parameters via safe defaults")
        else:
            # Tier 2: Starvation Prevention Check
            starved_lanes = check_starvation(self.waiting_times, self.consecutive_skips, self.config)
            
            if starved_lanes:
                # Select the starved lane with the highest demand score
                # Tie-breaking: score descending, lane name ascending (alphabetical)
                sorted_starved = sorted(starved_lanes, key=lambda l: (-scores[l][0], l))
                active_lane_str = sorted_starved[0]
                priority = Priority.HIGH
                
                # Build detailed explainable reasons
                wait_t = self.waiting_times[active_lane_str]
                skips = self.consecutive_skips[active_lane_str]
                reasons = [
                    f"{active_lane_str.capitalize()} exceeded waiting threshold (waiting {wait_t:.1f}s, skips {skips})",
                    f"Starvation prevention increased {active_lane_str.capitalize()} priority"
                ]
            else:
                # Tier 3 & 4: Traffic Demand Score & Tie-breaker
                lane_keys_str = [lane.value for lane in state.lanes.keys()]
                sorted_lanes = sorted(lane_keys_str, key=lambda l: (-scores[l][0], l))
                active_lane_str = sorted_lanes[0]
                priority = Priority.NORMAL

                # Build detailed explainable reasons
                lane_state = state.lanes[Lane(active_lane_str)]
                score, breakdown = scores[active_lane_str]
                
                # Check for empty intersection
                total_vehicles = sum(l.vehicle_count for l in state.lanes.values())
                if total_vehicles == 0 and sum(l.occupancy for l in state.lanes.values()) == 0.0:
                    reasons = [
                        "Empty intersection detected",
                        f"Defaulting to {active_lane_str.capitalize()} approach"
                    ]
                else:
                    if breakdown.get("used_tracking", False):
                        reasons = [
                            f"Selected {active_lane_str.upper()} due to highest tracked demand:",
                            f"- {lane_state.queued_vehicle_count} queued vehicles",
                            f"- {lane_state.observed_average_wait:.1f}s average observed wait",
                            f"- Priority score: {score:.3f}"
                        ]
                    else:
                        reasons = [
                            f"Selected {active_lane_str.upper()} based on raw demand (tracking unavailable):",
                            f"- {lane_state.vehicle_count} total vehicles",
                            f"- {lane_state.occupancy * 100:.0f}% occupancy",
                            f"- Priority score: {score:.3f}"
                        ]

        # 5. Compute dynamic green duration
        lane_state = state.lanes[Lane(active_lane_str)]
        duration = calculate_green_time(lane_state, self.config, state)

        # 6. Update skips and reset the chosen active lane's metrics immediately
        for lane in self.config.VALID_LANES:
            if lane == active_lane_str:
                self.consecutive_skips[lane] = 0
                self.waiting_times[lane] = 0.0
            else:
                self.consecutive_skips[lane] += 1

        # Save decision parameters for the next cycle
        self.last_active_lane = active_lane_str
        self.last_duration = duration
        self.last_timestamp = state.timestamp
        # Build the score breakdown for visualization
        score_breakdown_out = {}
        for lane_key, (lane_score, lane_breakdown) in scores.items():
            score_breakdown_out[lane_key] = {
                "total_score": lane_score,
                **lane_breakdown
            }

        return SignalDecision(
            decision_id=f"dec-{uuid.uuid4().hex[:8]}",
            timestamp=state.timestamp,
            selected_lane=Lane(active_lane_str),
            duration=duration,
            priority=priority,
            reasons=reasons,
            score_breakdown=score_breakdown_out
        )
