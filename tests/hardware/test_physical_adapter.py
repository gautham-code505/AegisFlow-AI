"""
PhysicalControllerAdapter comprehensive tests.
ALL tests use DummySerialTransport — no real COM port or ESP32 required.

WP15 additions cover:
  - PING/PONG heartbeat path
  - last_command_id = -1 detection (MCU reboot)
  - State resynchronization after simulated MCU reboot
  - Heartbeat timeout → DEGRADED
  - Serial disconnect → FAULT
  - Reconnect → liveness confirmation required
  - Latest-state preservation during physical failure
  - Adapter remains responsive (heartbeat does not block commands)
"""

import json
import time
import pytest
from models import SignalState, SignalPhase, Lane, SignalColor
from models.enums import PhysicalControllerStatus
from hardware.adapter import PhysicalControllerAdapter
from hardware.serial_transport import DummySerialTransport
from hardware.protocol import HardwareProtocol, PROTOCOL_VERSION


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def transport():
    return DummySerialTransport()


@pytest.fixture
def adapter(transport):
    a = PhysicalControllerAdapter(transport=transport, ack_timeout=0.15)
    yield a
    a.stop()


def _green(ts=1.0):
    return SignalState(
        timestamp=ts,
        phase=SignalPhase.GREEN,
        active_lanes=[Lane.NORTH],
        north=SignalColor.GREEN,
    )


def _yellow(ts=2.0):
    return SignalState(
        timestamp=ts,
        phase=SignalPhase.YELLOW,
        active_lanes=[Lane.NORTH],
        north=SignalColor.YELLOW,
    )


def _all_red(ts=3.0):
    return SignalState(timestamp=ts, phase=SignalPhase.ALL_RED)


def _ack(cmd_id: int) -> str:
    return f'{{"version": 1, "type": "ACK", "command_id": {cmd_id}, "payload": {{}}}}\n'


def _nack(cmd_id: int) -> str:
    return f'{{"version": 1, "type": "NACK", "command_id": {cmd_id}, "payload": {{"reason": "bad"}}}}\n'


def _pong(last_command_id: int) -> str:
    return (
        f'{{"version": {PROTOCOL_VERSION}, "type": "PONG", '
        f'"payload": {{"last_command_id": {last_command_id}}}}}\n'
    )


# ---------------------------------------------------------------------------
# 1. Startup / Shutdown
# ---------------------------------------------------------------------------

def test_adapter_initial_status_is_disconnected(adapter):
    assert adapter.status == PhysicalControllerStatus.DISCONNECTED


def test_adapter_start_connects_transport(adapter, transport):
    adapter.start()
    assert transport.is_connected()
    assert adapter.status == PhysicalControllerStatus.CONNECTED


def test_adapter_stop_disconnects_transport(adapter, transport):
    adapter.start()
    adapter.stop()
    assert not transport.is_connected()
    assert adapter.status == PhysicalControllerStatus.DISCONNECTED


def test_adapter_stop_when_not_started_does_not_raise(adapter):
    adapter.stop()  # must not raise


def test_adapter_double_start_is_safe(adapter):
    adapter.start()
    adapter.start()  # second start must be a no-op, not crash
    assert adapter.status == PhysicalControllerStatus.CONNECTED


# ---------------------------------------------------------------------------
# 2. Normal GREEN state — dispatch and ACK
# ---------------------------------------------------------------------------

def test_adapter_dispatches_green_state(adapter, transport):
    adapter.start()
    transport.mock_responses.append(_ack(1))
    adapter.update_signal_state(_green())
    time.sleep(0.1)
    assert transport.last_written is not None
    assert "SET_SIGNAL_STATE" in transport.last_written
    assert "GREEN" in transport.last_written
    assert adapter.status == PhysicalControllerStatus.CONNECTED


# ---------------------------------------------------------------------------
# 3. YELLOW state
# ---------------------------------------------------------------------------

def test_adapter_dispatches_yellow_state(adapter, transport):
    adapter.start()
    transport.mock_responses.append(_ack(1))
    adapter.update_signal_state(_yellow())
    time.sleep(0.1)
    assert "YELLOW" in transport.last_written


# ---------------------------------------------------------------------------
# 4. ALL_RED state
# ---------------------------------------------------------------------------

def test_adapter_dispatches_all_red_state(adapter, transport):
    adapter.start()
    transport.mock_responses.append(_ack(1))
    adapter.update_signal_state(_all_red())
    time.sleep(0.1)
    assert transport.last_written is not None
    assert "SET_SIGNAL_STATE" in transport.last_written


# ---------------------------------------------------------------------------
# 5. Command ID increments
# ---------------------------------------------------------------------------

def test_adapter_command_id_increments(adapter, transport):
    adapter.start()

    # Send first command
    transport.mock_responses.append(_ack(1))
    adapter.update_signal_state(_green(ts=1.0))
    time.sleep(0.1)
    first_cmd_id = json.loads(transport.last_written)["command_id"]

    # Send second command
    transport.mock_responses.append(_ack(2))
    adapter.update_signal_state(_all_red(ts=2.0))
    time.sleep(0.1)
    second_cmd_id = json.loads(transport.last_written)["command_id"]

    assert second_cmd_id == first_cmd_id + 1


# ---------------------------------------------------------------------------
# 6. NACK degrades status
# ---------------------------------------------------------------------------

def test_adapter_nack_sets_degraded_status(adapter, transport):
    adapter.start()
    transport.mock_responses.append(_nack(1))
    adapter.update_signal_state(_green())
    time.sleep(0.1)
    assert adapter.status == PhysicalControllerStatus.DEGRADED


# ---------------------------------------------------------------------------
# 7. ACK timeout degrades status
# ---------------------------------------------------------------------------

def test_adapter_ack_timeout_degrades_status(adapter, transport):
    # No ACK loaded — adapter will time out after 0.15s
    adapter.start()
    adapter.update_signal_state(_green())
    time.sleep(0.3)  # > ack_timeout
    assert adapter.status == PhysicalControllerStatus.DEGRADED


# ---------------------------------------------------------------------------
# 8. Write failure sets FAULT status
# ---------------------------------------------------------------------------

def test_adapter_write_failure_sets_fault(adapter, transport):
    adapter.start()
    transport.fail_writes = True
    adapter.update_signal_state(_green())
    time.sleep(0.1)
    assert adapter.status == PhysicalControllerStatus.FAULT


# ---------------------------------------------------------------------------
# 9. Latest-state semantics — stale state overwritten
# ---------------------------------------------------------------------------

def test_adapter_latest_state_semantics(adapter, transport):
    """Enqueue two states while worker is stopped; only latest must be sent."""
    # Don't start worker yet so queue fills synchronously
    adapter.stop()

    adapter.update_signal_state(_all_red(ts=1.0))    # stale
    adapter.update_signal_state(_green(ts=2.0))      # latest (must win)

    transport.mock_responses.append(_ack(1))
    adapter.start()
    time.sleep(0.2)

    assert transport.last_written is not None
    assert "GREEN" in transport.last_written
    # ALL_RED payload would have all "RED" values — make sure no ALL_RED-only write happened first
    sent = json.loads(transport.last_written)
    assert sent["payload"]["lanes"]["north"] == "GREEN"


# ---------------------------------------------------------------------------
# 10. Multiple transitions — command IDs are unique
# ---------------------------------------------------------------------------

def test_adapter_multiple_transitions_unique_command_ids(adapter, transport):
    adapter.start()
    ids_seen = set()

    for i, state in enumerate([_green(ts=1.0), _yellow(ts=2.0), _all_red(ts=3.0)], start=1):
        transport.mock_responses.append(_ack(i))
        adapter.update_signal_state(state)
        time.sleep(0.1)
        if transport.last_written:
            cmd_id = json.loads(transport.last_written)["command_id"]
            ids_seen.add(cmd_id)

    assert len(ids_seen) == 3


# ---------------------------------------------------------------------------
# 11. Transport disconnect mid-session sets FAULT
# ---------------------------------------------------------------------------

def test_adapter_transport_disconnect_sets_fault(adapter, transport):
    adapter.start()
    transport.mock_responses.append(_ack(1))
    adapter.update_signal_state(_green())
    time.sleep(0.1)
    assert adapter.status == PhysicalControllerStatus.CONNECTED

    # Simulate physical disconnection
    transport.disconnect()
    transport.fail_writes = True  # next write also fails

    adapter.update_signal_state(_all_red())
    time.sleep(0.1)
    assert adapter.status in (PhysicalControllerStatus.FAULT, PhysicalControllerStatus.DEGRADED)


# ---------------------------------------------------------------------------
# 12. Shutdown while idle — no hang
# ---------------------------------------------------------------------------

def test_adapter_shutdown_while_idle(transport):
    a = PhysicalControllerAdapter(transport=transport, ack_timeout=0.1)
    a.start()
    start = time.time()
    a.stop()
    elapsed = time.time() - start
    assert elapsed < 5.0  # must not hang


# ---------------------------------------------------------------------------
# 13. Shutdown while sending — no hang
# ---------------------------------------------------------------------------

def test_adapter_shutdown_while_sending(transport):
    a = PhysicalControllerAdapter(transport=transport, ack_timeout=2.0)  # long timeout
    a.start()
    a.update_signal_state(_green())
    time.sleep(0.02)  # let worker begin its ACK wait
    start = time.time()
    a.stop()  # must interrupt gracefully
    elapsed = time.time() - start
    assert elapsed < 5.0


# ---------------------------------------------------------------------------
# 14. SignalState NOT modified by physical failure
# ---------------------------------------------------------------------------

def test_signal_state_unmodified_by_physical_failure(adapter, transport):
    adapter.start()
    state = _green(ts=99.0)
    transport.fail_writes = True
    adapter.update_signal_state(state)
    time.sleep(0.1)

    # The original state object must be unchanged
    assert state.phase == SignalPhase.GREEN
    assert state.timestamp == 99.0
    assert state.north == SignalColor.GREEN
    assert adapter.status == PhysicalControllerStatus.FAULT


# ---------------------------------------------------------------------------
# WP15 — 15. Heartbeat PING is transmitted
# ---------------------------------------------------------------------------

def test_heartbeat_ping_transmitted(transport):
    """
    When idle, the adapter must write a PING to the transport.
    We confirm by checking transport.last_written after a PONG is injected
    so the worker completes the heartbeat cycle and returns the status CONNECTED.
    """
    # Pre-load a PONG so heartbeat cycle completes quickly
    transport.mock_responses.append(_pong(-1))
    a = PhysicalControllerAdapter(transport=transport, ack_timeout=0.15)
    a.start()
    time.sleep(0.7)  # idle poll interval is 0.5s, give it time

    assert transport.last_written is not None
    msg = json.loads(transport.last_written)
    assert msg["type"] == "PING", (
        f"Expected PING but got {msg['type']!r}; full payload: {transport.last_written!r}"
    )
    a.stop()


# ---------------------------------------------------------------------------
# WP15 — 16. Heartbeat PONG is parsed — CONNECTED
# ---------------------------------------------------------------------------

def test_heartbeat_pong_sets_connected(transport):
    """A valid PONG (last_command_id != -1) must set status CONNECTED."""
    a = PhysicalControllerAdapter(transport=transport, ack_timeout=0.15)
    a.start()

    # Inject PONG response so heartbeat loop completes
    transport.mock_responses.append(_pong(5))
    time.sleep(0.8)

    assert a.status == PhysicalControllerStatus.CONNECTED
    a.stop()


# ---------------------------------------------------------------------------
# WP15 — 17. Heartbeat timeout → DEGRADED
# ---------------------------------------------------------------------------

def test_heartbeat_timeout_sets_degraded(transport):
    """If no PONG arrives within the heartbeat timeout, status must become DEGRADED."""
    a = PhysicalControllerAdapter(transport=transport, ack_timeout=0.15)
    a.start()
    # No PONG loaded — heartbeat will time out
    time.sleep(2.5)  # idle poll (0.5) + heartbeat timeout (1.5) + margin

    assert a.status in (PhysicalControllerStatus.DEGRADED, PhysicalControllerStatus.FAULT)
    a.stop()


# ---------------------------------------------------------------------------
# WP15 — 18. MCU reboot detected via PONG last_command_id = -1
# ---------------------------------------------------------------------------

def test_mcu_reboot_detected_via_pong_minus_one(transport):
    """
    Simulate: adapter ACKs cmd 1, then MCU reboots (last_command_id resets to -1).
    The heartbeat must detect the -1 and trigger resync.
    """
    a = PhysicalControllerAdapter(transport=transport, ack_timeout=0.15)
    a.start()

    # Step 1: send a command and ACK it so last_acked_command_id is set
    transport.mock_responses.append(_ack(1))
    a.update_signal_state(_green())
    time.sleep(0.2)
    assert a.last_acked_command_id == 1, "Pre-condition: command must be ACKed"

    # Step 2: set authoritative state (so resync has something to send)
    north_green = _green(ts=50.0)
    a._latest_committed_state = north_green

    # Step 3: simulate MCU reboot → next PONG carries -1
    # Also pre-load an ACK so the resync command is confirmed
    transport.mock_responses.append(_pong(-1))
    transport.mock_responses.append(_ack(2))

    # Wait for idle heartbeat to fire (0.5s poll) and resync to dispatch
    time.sleep(1.5)

    # last_acked_command_id should have been reset and then re-set by resync ACK
    assert a.last_acked_command_id == 2, (
        f"Resync ACK not received. last_acked_command_id={a.last_acked_command_id}"
    )
    assert a.status == PhysicalControllerStatus.CONNECTED
    a.stop()


# ---------------------------------------------------------------------------
# WP15 — 19. State resynchronization: correct state is re-sent after reset
# ---------------------------------------------------------------------------

def test_state_resync_sends_latest_committed_state(transport):
    """
    After MCU-reset (PONG -1), the resent command must carry the same signal
    phase as the authoritative state, not a default or stale one.
    We verify by confirming the resync ACK (cmd_id=2) is received and that
    the last written SET_SIGNAL_STATE payload contained north=GREEN.
    """
    a = PhysicalControllerAdapter(transport=transport, ack_timeout=0.15)
    a.start()

    # ACK an initial command
    transport.mock_responses.append(_ack(1))
    a.update_signal_state(_green(ts=1.0))
    time.sleep(0.2)
    assert a.last_acked_command_id == 1, "Pre-condition: command must be ACKed"

    # Store NORTH_GREEN as the authoritative state
    north_green = SignalState(
        timestamp=99.0,
        phase=SignalPhase.GREEN,
        active_lanes=[Lane.NORTH],
        north=SignalColor.GREEN,
    )
    a._latest_committed_state = north_green

    # Collect all writes via a custom DummyTransport so we see the SET_SIGNAL_STATE
    # even if a subsequent PING overwrites last_written.
    written_payloads: list = []
    original_write = transport.write_line
    def tracking_write(data: str) -> bool:
        written_payloads.append(data)
        return original_write(data)
    transport.write_line = tracking_write

    # Simulate MCU reboot
    transport.mock_responses.append(_pong(-1))
    transport.mock_responses.append(_ack(2))
    time.sleep(1.5)

    # Resync ACK must have been received
    assert a.last_acked_command_id == 2, (
        f"Resync ACK not received. last_acked_command_id={a.last_acked_command_id}"
    )
    assert a.status == PhysicalControllerStatus.CONNECTED

    # Confirm the SET_SIGNAL_STATE payload had north=GREEN
    set_state_payloads = [
        json.loads(p) for p in written_payloads
        if p.strip().startswith('{') and json.loads(p).get('type') == 'SET_SIGNAL_STATE'
    ]
    assert len(set_state_payloads) >= 1, "No SET_SIGNAL_STATE was written during resync"
    resent = set_state_payloads[-1]
    assert resent["payload"]["lanes"]["north"] == "GREEN", (
        f"Expected GREEN but got {resent['payload']['lanes']['north']!r}"
    )
    a.stop()


# ---------------------------------------------------------------------------
# WP15 — 20. MCU reset with no prior ACKed command still triggers resync
# ---------------------------------------------------------------------------

def test_mcu_cold_start_pong_triggers_resync_when_state_available(transport):
    """
    Even if no command has been ACKed (first connection), a PONG with -1
    must trigger resync if an authoritative state is available.
    Verified by confirming the resync ACK (cmd_id=1) is received.
    """
    a = PhysicalControllerAdapter(transport=transport, ack_timeout=0.15)
    a._latest_committed_state = _green(ts=10.0)
    a.start()

    # Immediately inject PONG -1 and an ACK for the resync
    transport.mock_responses.append(_pong(-1))
    transport.mock_responses.append(_ack(1))
    time.sleep(1.5)

    # Resync ACK must have been received
    assert a.last_acked_command_id == 1, (
        f"Resync ACK not received. last_acked_command_id={a.last_acked_command_id}"
    )
    assert a.status == PhysicalControllerStatus.CONNECTED
    a.stop()


# ---------------------------------------------------------------------------
# WP15 — 21. USB disconnect: serial disconnect → FAULT without reconnect
# ---------------------------------------------------------------------------

def test_serial_disconnect_sets_fault_when_reconnect_fails(transport):
    """
    Simulate: transport disconnects and cannot reconnect (write fails).
    Adapter must reach FAULT, not stay CONNECTED.
    """
    class UnreconnectableTransport(DummySerialTransport):
        def connect(self):
            return False  # always fails after initial connect

    t = UnreconnectableTransport()
    t.connect()  # manually set connected for initial start
    a = PhysicalControllerAdapter(transport=t, ack_timeout=0.15)
    a.status = PhysicalControllerStatus.CONNECTED
    a._shutdown_event.clear()

    import threading
    a._worker_thread = threading.Thread(
        target=a._worker_loop, daemon=True, name="PhysicalAdapterThread"
    )
    a._worker_thread.start()

    # Disconnect transport
    t.disconnect()
    time.sleep(1.5)  # worker loop retry + reconnect attempt

    assert a.status == PhysicalControllerStatus.FAULT
    a.stop()


# ---------------------------------------------------------------------------
# WP15 — 22. Latest-state preserved through physical failure
# ---------------------------------------------------------------------------

def test_latest_state_preserved_through_physical_failure(adapter, transport):
    """
    Even when the adapter is in FAULT, the authoritative SignalState stored
    in _latest_committed_state must remain unmodified.
    """
    north_green = _green(ts=77.0)
    adapter.update_signal_state(north_green)
    transport.fail_writes = True
    adapter.start()
    time.sleep(0.3)

    assert adapter.status == PhysicalControllerStatus.FAULT
    # Authoritative state must be unchanged
    assert adapter._latest_committed_state is not None
    assert adapter._latest_committed_state.timestamp == 77.0
    assert adapter._latest_committed_state.phase == SignalPhase.GREEN
    assert adapter._latest_committed_state.north == SignalColor.GREEN


# ---------------------------------------------------------------------------
# WP15 — 23. Adapter remains responsive: heartbeat cannot permanently block commands
# ---------------------------------------------------------------------------

def test_adapter_responsive_command_after_heartbeat(transport):
    """
    After a heartbeat cycle the adapter must accept and dispatch new commands
    without deadlock.
    """
    a = PhysicalControllerAdapter(transport=transport, ack_timeout=0.15)
    a.start()

    # Let heartbeat time out (no PONG) — DEGRADED
    time.sleep(2.5)
    assert a.status in (PhysicalControllerStatus.DEGRADED, PhysicalControllerStatus.FAULT)

    # Now inject an ACK and send a new command — must succeed
    transport.mock_responses.append(_ack(1))
    a.update_signal_state(_green())
    time.sleep(0.4)

    assert a.last_acked_command_id == 1
    assert a.status == PhysicalControllerStatus.CONNECTED
    a.stop()


# ---------------------------------------------------------------------------
# WP15 — 24. Reconnect: status requires real liveness confirmation
# ---------------------------------------------------------------------------

def test_reconnect_requires_liveness_confirmation(transport):
    """
    After reconnect, status should only be CONNECTED once a PONG or ACK
    is received — not merely because is_connected() returns True.
    """
    a = PhysicalControllerAdapter(transport=transport, ack_timeout=0.15)
    a.start()

    # Force a disconnect
    transport.disconnect()
    time.sleep(0.7)  # let worker detect and set FAULT

    # Reconnect (DummySerialTransport.connect() always returns True)
    # But we do NOT load any PONG — no liveness yet
    # Worker will reconnect and try heartbeat which will timeout → DEGRADED
    time.sleep(2.5)

    # After reconnect + heartbeat timeout the adapter must NOT be CONNECTED
    assert a.status in (
        PhysicalControllerStatus.FAULT,
        PhysicalControllerStatus.DEGRADED,
    ), f"Unexpected status after reconnect without liveness: {a.status}"
    a.stop()
