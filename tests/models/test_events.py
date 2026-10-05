"""
Unit tests for Event contract model.
"""

import json
from models import Event, EventSeverity


def test_event_serialization():
    """11. Test Event model initialization and JSON serialization."""
    event = Event(
        event_id="ev-101",
        timestamp=100.5,
        type="SIGNAL_DECISION",
        severity=EventSeverity.INFO,
        message="North lane allocated 30s green phase",
    )
    assert event.event_id == "ev-101"
    assert event.timestamp == 100.5
    assert event.type == "SIGNAL_DECISION"
    assert event.severity == EventSeverity.INFO

    # Test serialization to JSON
    json_str = event.model_dump_json()
    data = json.loads(json_str)

    assert data["event_id"] == "ev-101"
    assert data["timestamp"] == 100.5
    assert data["type"] == "SIGNAL_DECISION"
    assert data["severity"] == "INFO"

    # Test deserialization back to model
    deserialized = Event.model_validate_json(json_str)
    assert deserialized == event
