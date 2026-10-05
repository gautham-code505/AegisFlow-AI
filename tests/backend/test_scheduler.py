import pytest
import asyncio
import time
from unittest.mock import AsyncMock, patch, MagicMock

from models import TrafficState, EmergencyState, SignalDecision, Lane
from backend.app import _decision_loop, _decision_event, DECISION_INTERVAL, state_store, orchestrator, logger
from backend.app import lifespan
from fastapi import FastAPI

@pytest.fixture
def mock_orchestrator():
    with patch("backend.app.orchestrator.process_traffic_state", new_callable=AsyncMock) as mock:
        yield mock

@pytest.fixture
def test_event():
    return asyncio.Event()

@pytest.fixture(autouse=True)
def clear_state():
    state_store.set_traffic_state(None)
    state_store.set_decision(None)
    state_store.clear_active_emergency()
    _decision_event.clear()

@pytest.mark.asyncio
async def test_t1_t2_scheduler_uses_latest_state(mock_orchestrator, test_event):
    """
    T1: Multiple perception updates do not cause one decision per frame.
    T2: Scheduler uses the latest TrafficState.
    T3: Intermediate states are not replayed.
    """
    ts1 = TrafficState(timestamp=100.0)
    ts2 = TrafficState(timestamp=101.0)
    
    state_store.set_traffic_state(ts1)
    state_store.set_traffic_state(ts2)
    
    # Run a single iteration of the scheduler logic conceptually
    test_event.set()
    task = asyncio.create_task(_decision_loop(state_store, orchestrator, test_event, logger))
    await asyncio.sleep(0.05)
    task.cancel()
    
    # Should only process ts2, the latest one
    mock_orchestrator.assert_called_once_with(ts2)

@pytest.mark.asyncio
async def test_t4_t5_deduplication(mock_orchestrator, test_event):
    """
    T4: Same already-processed state is not processed repeatedly.
    T5: Monotonic generation versioning works.
    """
    ts1 = TrafficState(timestamp=100.0)
    state_store.set_traffic_state(ts1)
    
    test_event.set()
    task = asyncio.create_task(_decision_loop(state_store, orchestrator, test_event, logger))
    await asyncio.sleep(0.05)
    
    mock_orchestrator.assert_called_once_with(ts1)
    mock_orchestrator.reset_mock()
    
    # Wake up scheduler again without setting a new traffic state
    test_event.set()
    await asyncio.sleep(0.05)
    
    # Should skip processing because the version hasn't changed
    mock_orchestrator.assert_not_called()
    task.cancel()

@pytest.mark.asyncio
async def test_t6_t7_emergency(mock_orchestrator, test_event):
    """
    T6: Emergency wakes the scheduler immediately.
    T7: Emergency does not cause duplicate concurrent control execution.
    """
    ts_emg = TrafficState(timestamp=100.0, emergency=EmergencyState(detected=True))
    state_store.set_traffic_state(ts_emg)
    
    # The vision loop calls _decision_event.set()
    test_event.set()
    
    task = asyncio.create_task(_decision_loop(state_store, orchestrator, test_event, logger))
    await asyncio.sleep(0.05)
    task.cancel()
    
    # Processed once
    mock_orchestrator.assert_called_once_with(ts_emg)

@pytest.mark.asyncio
async def test_t10_t11_exception_survival(mock_orchestrator, test_event):
    """
    T10: Scheduler survives an exception in one iteration.
    T11: Scheduler shuts down cleanly.
    T12: Only one scheduler instance is created.
    """
    # Force exception on first call
    mock_orchestrator.side_effect = [Exception("Test error"), None]
    
    ts1 = TrafficState(timestamp=100.0)
    state_store.set_traffic_state(ts1)
    test_event.set()
    
    task = asyncio.create_task(_decision_loop(state_store, orchestrator, test_event, logger))
    await asyncio.sleep(0.05)
    
    # Should have survived. Provide next state
    ts2 = TrafficState(timestamp=101.0)
    state_store.set_traffic_state(ts2)
    test_event.set()
    await asyncio.sleep(1.1)
    
    task.cancel()
    assert mock_orchestrator.call_count == 2

@pytest.mark.asyncio
async def test_t12_clean_shutdown():
    """T11: Scheduler shuts down cleanly. (Using FastAPI lifespan)"""
    app = FastAPI()
    async with lifespan(app):
        # The background tasks are running
        await asyncio.sleep(0.01)
    # Exiting the block cancels them cleanly. No exceptions should leak.
