"""
Comprehensive HardwareProtocol tests.
Covers serialization, deserialization, all signal phases,
version rejection, malformed-input handling,
PING/PONG serialization and parsing, and last_command_id semantics.
No hardware required.
"""

import json
import pytest
from models import SignalState, SignalPhase, Lane, SignalColor
from hardware.protocol import HardwareProtocol, ProtocolMessage, PROTOCOL_VERSION


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _all_red_state(ts: float = 1.0) -> SignalState:
    return SignalState(timestamp=ts, phase=SignalPhase.ALL_RED)


def _green_state(ts: float = 2.0) -> SignalState:
    return SignalState(
        timestamp=ts,
        phase=SignalPhase.GREEN,
        active_lanes=[Lane.NORTH, Lane.SOUTH],
        north=SignalColor.GREEN,
        south=SignalColor.GREEN,
        east=SignalColor.RED,
        west=SignalColor.RED,
        remaining_seconds=20,
    )


def _yellow_state(ts: float = 3.0) -> SignalState:
    return SignalState(
        timestamp=ts,
        phase=SignalPhase.YELLOW,
        active_lanes=[Lane.NORTH, Lane.SOUTH],
        north=SignalColor.YELLOW,
        south=SignalColor.YELLOW,
        east=SignalColor.RED,
        west=SignalColor.RED,
        remaining_seconds=3,
    )


# ---------------------------------------------------------------------------
# Serialization — structure
# ---------------------------------------------------------------------------

def test_protocol_serialize_returns_newline_terminated():
    line = HardwareProtocol.serialize_signal_state(_all_red_state(), command_id=1)
    assert line.endswith("\n")


def test_protocol_serialize_version():
    data = json.loads(HardwareProtocol.serialize_signal_state(_all_red_state(), command_id=1))
    assert data["version"] == PROTOCOL_VERSION


def test_protocol_serialize_type():
    data = json.loads(HardwareProtocol.serialize_signal_state(_all_red_state(), command_id=1))
    assert data["type"] == "SET_SIGNAL_STATE"


def test_protocol_serialize_command_id():
    data = json.loads(HardwareProtocol.serialize_signal_state(_all_red_state(), command_id=99))
    assert data["command_id"] == 99


def test_protocol_serialize_timestamp():
    data = json.loads(HardwareProtocol.serialize_signal_state(_all_red_state(ts=42.5), command_id=1))
    assert data["payload"]["timestamp"] == 42.5


# ---------------------------------------------------------------------------
# Serialization — ALL_RED phase
# ---------------------------------------------------------------------------

def test_protocol_serialize_all_red():
    data = json.loads(HardwareProtocol.serialize_signal_state(_all_red_state(), command_id=1))
    lanes = data["payload"]["lanes"]
    assert lanes["north"] == "RED"
    assert lanes["south"] == "RED"
    assert lanes["east"] == "RED"
    assert lanes["west"] == "RED"


# ---------------------------------------------------------------------------
# Serialization — GREEN phase
# ---------------------------------------------------------------------------

def test_protocol_serialize_green():
    data = json.loads(HardwareProtocol.serialize_signal_state(_green_state(), command_id=2))
    lanes = data["payload"]["lanes"]
    assert lanes["north"] == "GREEN"
    assert lanes["south"] == "GREEN"
    assert lanes["east"] == "RED"
    assert lanes["west"] == "RED"


# ---------------------------------------------------------------------------
# Serialization — YELLOW phase
# ---------------------------------------------------------------------------

def test_protocol_serialize_yellow():
    data = json.loads(HardwareProtocol.serialize_signal_state(_yellow_state(), command_id=3))
    lanes = data["payload"]["lanes"]
    assert lanes["north"] == "YELLOW"
    assert lanes["south"] == "YELLOW"
    assert lanes["east"] == "RED"
    assert lanes["west"] == "RED"


# ---------------------------------------------------------------------------
# Serialization — determinism (two calls produce identical output)
# ---------------------------------------------------------------------------

def test_protocol_serialize_is_deterministic():
    state = _green_state()
    out1 = HardwareProtocol.serialize_signal_state(state, command_id=7)
    out2 = HardwareProtocol.serialize_signal_state(state, command_id=7)
    assert out1 == out2


# ---------------------------------------------------------------------------
# WP15 — PING serialization
# ---------------------------------------------------------------------------

def test_protocol_ping_returns_newline_terminated():
    """PING payload must be newline-terminated for serial framing."""
    line = HardwareProtocol.serialize_ping()
    assert line.endswith("\n")


def test_protocol_ping_version():
    """PING must carry the correct protocol version."""
    data = json.loads(HardwareProtocol.serialize_ping())
    assert data["version"] == PROTOCOL_VERSION


def test_protocol_ping_type():
    """PING type field must be exactly 'PING'."""
    data = json.loads(HardwareProtocol.serialize_ping())
    assert data["type"] == "PING"


def test_protocol_ping_is_valid_json():
    """PING must be parseable as valid JSON."""
    raw = HardwareProtocol.serialize_ping()
    parsed = json.loads(raw)
    assert isinstance(parsed, dict)


def test_protocol_ping_is_deterministic():
    """Two consecutive PING calls must produce identical output."""
    assert HardwareProtocol.serialize_ping() == HardwareProtocol.serialize_ping()


# ---------------------------------------------------------------------------
# WP15 — PONG serialization and parsing
# ---------------------------------------------------------------------------

def _make_pong(last_command_id: int) -> str:
    """Build the PONG JSON that the ESP32 firmware would emit."""
    return (
        f'{{"version": {PROTOCOL_VERSION}, "type": "PONG", '
        f'"payload": {{"last_command_id": {last_command_id}}}}}\n'
    )


def test_protocol_pong_parsed_correctly():
    """PONG with last_command_id=5 must parse to a PONG ProtocolMessage."""
    msg = HardwareProtocol.parse_response(_make_pong(5))
    assert msg is not None
    assert msg.type == "PONG"
    assert msg.payload["last_command_id"] == 5


def test_protocol_pong_last_command_id_negative_one():
    """PONG with last_command_id=-1 (MCU cold start) must parse correctly."""
    msg = HardwareProtocol.parse_response(_make_pong(-1))
    assert msg is not None
    assert msg.type == "PONG"
    assert msg.payload["last_command_id"] == -1


def test_protocol_pong_last_command_id_zero():
    """PONG with last_command_id=0 must parse correctly."""
    msg = HardwareProtocol.parse_response(_make_pong(0))
    assert msg is not None
    assert msg.payload["last_command_id"] == 0


def test_protocol_pong_returned_from_serialize_ping_roundtrip():
    """A PING serialize → firmware PONG response parse round-trip must work."""
    ping = HardwareProtocol.serialize_ping()
    # Verify PING is well-formed
    data = json.loads(ping)
    assert data["type"] == "PING"
    # Simulate firmware response
    pong = _make_pong(last_command_id=7)
    msg = HardwareProtocol.parse_response(pong)
    assert msg is not None
    assert msg.type == "PONG"
    assert msg.payload["last_command_id"] == 7


# ---------------------------------------------------------------------------
# Deserialization — ACK
# ---------------------------------------------------------------------------

def test_protocol_parse_ack():
    raw = '{"version": 1, "type": "ACK", "command_id": 42, "payload": {}}\n'
    msg = HardwareProtocol.parse_response(raw)
    assert msg is not None
    assert msg.type == "ACK"
    assert msg.command_id == 42


# ---------------------------------------------------------------------------
# Deserialization — NACK / ERROR
# ---------------------------------------------------------------------------

def test_protocol_parse_nack():
    raw = '{"version": 1, "type": "NACK", "command_id": 5, "payload": {"reason": "invalid lane"}}\n'
    msg = HardwareProtocol.parse_response(raw)
    assert msg is not None
    assert msg.type == "NACK"
    assert msg.command_id == 5


def test_protocol_parse_error_type():
    raw = '{"version": 1, "type": "ERROR", "command_id": 10, "payload": {}}\n'
    msg = HardwareProtocol.parse_response(raw)
    assert msg is not None
    assert msg.type == "ERROR"


# ---------------------------------------------------------------------------
# Deserialization — unsupported version
# ---------------------------------------------------------------------------

def test_protocol_parse_unsupported_version():
    raw = '{"version": 99, "type": "ACK", "command_id": 1, "payload": {}}\n'
    msg = HardwareProtocol.parse_response(raw)
    assert msg is None


# ---------------------------------------------------------------------------
# Deserialization — malformed JSON
# ---------------------------------------------------------------------------

def test_protocol_parse_malformed_json():
    raw = '{"version": 1, "type": "ACK" \n'  # missing closing brace
    msg = HardwareProtocol.parse_response(raw)
    assert msg is None


# ---------------------------------------------------------------------------
# Deserialization — missing required field
# ---------------------------------------------------------------------------

def test_protocol_parse_missing_type_field():
    raw = '{"version": 1, "command_id": 1, "payload": {}}\n'
    msg = HardwareProtocol.parse_response(raw)
    assert msg is None


# ---------------------------------------------------------------------------
# Deserialization — empty / whitespace line
# ---------------------------------------------------------------------------

def test_protocol_parse_empty_line():
    assert HardwareProtocol.parse_response("") is None
    assert HardwareProtocol.parse_response("   \n") is None


# ---------------------------------------------------------------------------
# Non-JSON line (ESP32 boot log noise) must return None, not crash
# ---------------------------------------------------------------------------

def test_protocol_parse_non_json_line():
    assert HardwareProtocol.parse_response("ets Jun  8 2016 00:22:57\r\n") is None
    assert HardwareProtocol.parse_response("rst:0x1 (POWERON_RESET),boot:0x13\r\n") is None


# ---------------------------------------------------------------------------
# Command ID increments across multiple calls (adapter responsibility, sanity)
# ---------------------------------------------------------------------------

def test_protocol_command_id_type():
    line = HardwareProtocol.serialize_signal_state(_all_red_state(), command_id=1)
    data = json.loads(line)
    assert isinstance(data["command_id"], int)
