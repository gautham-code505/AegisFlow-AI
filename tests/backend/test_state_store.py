"""
Unit tests for in-memory StateStore.
"""

from models import TrafficState, SignalDecision, Event, EventSeverity, Lane
from backend.state_store import StateStore


def test_state_store_setters_and_getters():
    """Verify storing and retrieving TrafficState and SignalDecision."""
    store = StateStore(max_events=5)

    ts = TrafficState(timestamp=1.0)
    store.set_traffic_state(ts)
    assert store.get_traffic_state() == ts

    dec = SignalDecision(
        decision_id="dec-1",
        timestamp=1.0,
        selected_lane=Lane.NORTH,
        duration=15,
    )
    store.set_decision(dec)
    assert store.get_decision() == dec


def test_state_store_bounded_event_history():
    """Verify event history remains bounded to max_events limit."""
    store = StateStore(max_events=3)

    for i in range(10):
        ev = Event(
            event_id=f"ev-{i}",
            timestamp=float(i),
            type="TEST_EVENT",
            severity=EventSeverity.INFO,
            message=f"Event {i}",
        )
        store.add_event(ev)

    events = store.get_events()
    assert len(events) == 3
    assert events[0].event_id == "ev-7"
    assert events[-1].event_id == "ev-9"
