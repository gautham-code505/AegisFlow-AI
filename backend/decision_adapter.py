"""
AegisFlow AI - Decision Engine Adapter

Boundary adapter connecting canonical models.TrafficState to Jayasuriya's DecisionEngine,
and returning a canonical models.SignalDecision.
"""

import copy
import uuid
import logging
from typing import Optional, Any, Dict
from models import TrafficState, SignalDecision, Lane, Priority
from decision_engine import DecisionEngine

logger = logging.getLogger(__name__)


class DecisionEngineAdapter:
    """Translation adapter isolating Jayasuriya's DecisionEngine from canonical models."""

    # Engine bookkeeping that a decision updates as if it were already served
    _ENGINE_STATE_FIELDS = (
        "waiting_times", "consecutive_skips", "last_timestamp", "last_active_lane", "last_duration",
    )

    def __init__(self, engine: Optional[DecisionEngine] = None):
        self.engine = engine or DecisionEngine()
        self._state_before_last_decision: Optional[Dict[str, Any]] = None

    def decide(self, canonical_state: TrafficState) -> SignalDecision:
        """
        Passes canonical TrafficState directly to the DecisionEngine and augments
        the returned SignalDecision with the score breakdown.
        """
        # 1. Invoke existing Decision Engine (keeping its prior bookkeeping, see discard_last_decision)
        self._state_before_last_decision = {
            field: copy.deepcopy(getattr(self.engine, field))
            for field in self._ENGINE_STATE_FIELDS
            if hasattr(self.engine, field)
        }
        decision = self.engine.decide(canonical_state)

        # 2. Extract score breakdown from engine
        score_breakdown = None
        if hasattr(self.engine, 'last_scores') and self.engine.last_scores:
            score_breakdown = {}
            for lane_name, (total_score, breakdown) in self.engine.last_scores.items():
                score_breakdown[lane_name] = {
                    "total_score": round(total_score, 4),
                    **{k: round(v, 4) if isinstance(v, float) else v for k, v in breakdown.items()}
                }

        # The engine returned a fully compliant Pydantic SignalDecision
        # Just attach the score breakdown for frontend observability.
        decision.score_breakdown = score_breakdown
        
        return decision

    def discard_last_decision(self) -> None:
        """
        Restores the engine's waiting-time and skip bookkeeping to before the last decide().

        The engine resets the chosen lane's wait as soon as it decides, assuming the lane is
        served. When safety rejects the decision or the controller keeps a committed clearance
        target, the lane was NOT served; without this rollback the engine believes every lane
        is being served in turn and genuinely waiting approaches can starve.
        """
        if self._state_before_last_decision is None:
            return
        for field, value in self._state_before_last_decision.items():
            setattr(self.engine, field, value)
        self._state_before_last_decision = None

