import logging
from typing import Dict, Union, Any, List

from .models import TrafficState, SignalDecision, LaneState
from .config import DecisionEngineConfig, DEFAULT_CONFIG
from .validator import validate_traffic_state
from .emergency import check_emergency
from .starvation import check_starvation
from .scorer import calculate_lane_scores
from .timing import calculate_green_time

logger = logging.getLogger(__name__)

class DecisionEngine:
    def __init__(self, config: DecisionEngineConfig = DEFAULT_CONFIG):
        """
        Initializes the DecisionEngine with configurations and sets up
        the internal state tracker for waiting times and skips.
        """
        self.config = config
        
        # Internal state tracking
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
        active_lane = self.config.DEFAULT_LANE
        priority = "normal"
        reasons: List[str] = []

        # Tier 1: Emergency Vehicle Override
        emergency_override = check_emergency(state)
        if emergency_override is not None:
            active_lane, priority, reasons = emergency_override
            if warnings:
                reasons.append("Handled invalid input parameters via safe defaults")
        else:
            # Tier 2: Starvation Prevention Check
            starved_lanes = check_starvation(self.waiting_times, self.consecutive_skips, self.config)
            
            if starved_lanes:
                # Select the starved lane with the highest demand score
                # Tie-breaking: score descending, lane name ascending (alphabetical)
                sorted_starved = sorted(starved_lanes, key=lambda l: (-scores[l][0], l))
                active_lane = sorted_starved[0]
                priority = "high"
                
                # Build detailed explainable reasons
                wait_t = self.waiting_times[active_lane]
                skips = self.consecutive_skips[active_lane]
                reasons = [
                    f"{active_lane.capitalize()} exceeded waiting threshold (waiting {wait_t:.1f}s, skips {skips})",
                    f"Starvation prevention increased {active_lane.capitalize()} priority"
                ]
            else:
                # Tier 3 & 4: Traffic Demand Score & Tie-breaker
                sorted_lanes = sorted(state.lanes.keys(), key=lambda l: (-scores[l][0], l))
                active_lane = sorted_lanes[0]
                priority = "normal"

                # Build detailed explainable reasons
                lane_state = state.lanes[active_lane]
                score, breakdown = scores[active_lane]
                
                # Check for empty intersection
                total_vehicles = sum(l.vehicle_count for l in state.lanes.values())
                if total_vehicles == 0 and sum(l.occupancy for l in state.lanes.values()) == 0.0:
                    reasons = [
                        "Empty intersection detected",
                        f"Defaulting to {active_lane.capitalize()} approach"
                    ]
                else:
                    reasons = [
                        f"{active_lane.capitalize()} has highest occupancy at {lane_state.occupancy * 100:.0f}%",
                        f"{active_lane.capitalize()} has {lane_state.vehicle_count} detected vehicles",
                        f"{active_lane.capitalize()} received highest priority score ({score:.3f})"
                    ]

        # 5. Compute dynamic green duration
        lane_state = state.lanes[active_lane]
        duration = calculate_green_time(lane_state, self.config)

        # 6. Update skips and reset the chosen active lane's metrics immediately
        for lane in self.config.VALID_LANES:
            if lane == active_lane:
                self.consecutive_skips[lane] = 0
                self.waiting_times[lane] = 0.0
            else:
                self.consecutive_skips[lane] += 1

        # Save decision parameters for the next cycle
        self.last_active_lane = active_lane
        self.last_duration = duration
        self.last_timestamp = state.timestamp

        return SignalDecision(
            active_lane=active_lane,
            duration=duration,
            priority=priority,
            reason=reasons
        )
