"""
Unit tests for Orchestrator workflow.
"""

import time
import asyncio
from models import TrafficState, LaneState, Lane
from backend.state_store import StateStore
from backend.decision_adapter import DecisionEngineAdapter
from backend.websocket_manager import WebSocketManager
from backend.orchestrator import Orchestrator


def test_orchestrator_process_traffic_state():
    """Verify orchestrator updates state store and returns canonical SignalDecision."""
    async def _run_test():
        store = StateStore()
        adapter = DecisionEngineAdapter()
        ws = WebSocketManager()
        orchestrator = Orchestrator(store, adapter, ws)

        state = TrafficState(
            timestamp=time.time(),
            lanes={
                Lane.NORTH: LaneState(vehicle_count=2, occupancy=0.1),
                Lane.SOUTH: LaneState(vehicle_count=15, occupancy=0.75),
                Lane.EAST: LaneState(vehicle_count=3, occupancy=0.15),
                Lane.WEST: LaneState(vehicle_count=1, occupancy=0.05),
            },
        )

        decision = await orchestrator.process_traffic_state(state)

        assert decision.selected_lane == Lane.SOUTH
        assert store.get_traffic_state() == state
        assert store.get_decision() == decision
        assert len(store.get_events()) >= 1

    asyncio.run(_run_test())
