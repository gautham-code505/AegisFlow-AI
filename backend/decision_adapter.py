"""
AegisFlow AI - Decision Engine Adapter

Boundary adapter connecting canonical models.TrafficState to Jayasuriya's DecisionEngine,
and returning a canonical models.SignalDecision.
"""

import uuid
import logging
from typing import Optional
from models import TrafficState, SignalDecision, Lane, Priority
from decision_engine import DecisionEngine

logger = logging.getLogger(__name__)


class DecisionEngineAdapter:
    """Translation adapter isolating Jayasuriya's DecisionEngine from canonical models."""

    def __init__(self, engine: Optional[DecisionEngine] = None):
        self.engine = engine or DecisionEngine()

    def decide(self, canonical_state: TrafficState) -> SignalDecision:
        """
        Passes canonical TrafficState directly to the DecisionEngine and augments
        the returned SignalDecision with the score breakdown.
        """
        # 1. Invoke existing Decision Engine
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

