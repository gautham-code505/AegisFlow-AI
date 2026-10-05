"""
WP13 Failure-Isolation and End-to-End Software Simulation Tests.

Proves:
  1. Physical layer faults do NOT affect the decision loop, SafetyValidator,
     VirtualSignalController, or SignalState authority.
  2. The full Decision → Safety → Controller → SignalState → Adapter pipeline
     works correctly against a DummySerialTransport.
  3. Backend operates correctly when no hardware is attached.

No real COM port, ESP32, USB cable, or GPIO is required.
"""

import asyncio
import time
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from models import TrafficState, LaneState, Lane, SignalState, SignalPhase, SignalColor
from models.enums import PhysicalControllerStatus
from hardware.adapter import PhysicalControllerAdapter
from hardware.serial_transport import DummySerialTransport
from hardware.protocol import HardwareProtocol
from backend.decision_adapter import DecisionEngineAdapter
from backend.orchestrator import Orchestrator
from backend.state_store import StateStore
from backend.websocket_manager import WebSocketManager
from safety import SafetyValidator, FallbackController
from controller import VirtualSignalController


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_orchestrator(physical_adapter=None):
    state_store = StateStore()
    decision_adapter = DecisionEngineAdapter()
    ws_manager = WebSocketManager()
    safety_validator = SafetyValidator()
    virtual_controller = VirtualSignalController()
    fallback_controller = FallbackController()

    orch = Orchestrator(
        state_store=state_store,
        decision_adapter=decision_adapter,
        websocket_manager=ws_manager,
        safety_validator=safety_validator,
        virtual_controller=virtual_controller,
        fallback_controller=fallback_controller,
        physical_adapter=physical_adapter,
    )
    return orch, state_store


def _heavy_north_state() -> TrafficState:
    return TrafficState(
        timestamp=time.time(),
        source="test",
        lanes={
            Lane.NORTH: LaneState(vehicle_count=20, occupancy=0.9),
            Lane.SOUTH: LaneState(vehicle_count=1, occupancy=0.05),
            Lane.EAST: LaneState(vehicle_count=1, occupancy=0.05),
            Lane.WEST: LaneState(vehicle_count=1, occupancy=0.05),
        },
    )


# ---------------------------------------------------------------------------
# Section A: Failure-isolation — decision loop is unaffected by hardware faults
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_decision_loop_continues_when_transport_write_fails():
    """Serial write failure must NOT crash or halt the decision loop."""
    transport = DummySerialTransport()
    transport.fail_writes = True  # all writes fail immediately

    adapter = PhysicalControllerAdapter(transport=transport, ack_timeout=0.1)
    adapter.start()

    orch, state_store = _build_orchestrator(physical_adapter=adapter)

    state = _heavy_north_state()
    decision = await orch.process_traffic_state(state)

    # Decision was still produced
    assert decision is not None
    assert decision.selected_lane is not None

    # SignalState is still authoritative in StateStore
    signal = state_store.get_signal_state()
    assert signal is not None

    # Physical layer is degraded/fault but DOES NOT corrupt logical state
    time.sleep(0.15)  # let background worker attempt the failing write
    assert adapter.status in (PhysicalControllerStatus.FAULT, PhysicalControllerStatus.DEGRADED)
    assert signal.phase in (SignalPhase.GREEN, SignalPhase.YELLOW, SignalPhase.ALL_RED)

    adapter.stop()


@pytest.mark.asyncio
async def test_signal_state_authority_preserved_on_transport_failure():
    """SignalState committed by VirtualSignalController must remain unchanged
    even when the physical adapter cannot deliver it."""
    transport = DummySerialTransport()
    transport.connect()
    transport.fail_writes = True

    adapter = PhysicalControllerAdapter(transport=transport, ack_timeout=0.1)
    adapter.start()

    orch, state_store = _build_orchestrator(physical_adapter=adapter)

    await orch.process_traffic_state(_heavy_north_state())

    committed = state_store.get_signal_state()
    assert committed is not None

    # Physical failure must not roll back or alter the committed state
    time.sleep(0.15)  # let adapter attempt and fail
    still_committed = state_store.get_signal_state()
    assert still_committed is not None
    assert still_committed.timestamp == committed.timestamp
    assert still_committed.phase == committed.phase

    adapter.stop()


@pytest.mark.asyncio
async def test_safety_validator_unaffected_by_transport_fault():
    """SafetyValidator results must be independent of hardware layer status."""
    transport = DummySerialTransport()
    transport.fail_writes = True

    adapter = PhysicalControllerAdapter(transport=transport, ack_timeout=0.1)
    adapter.start()

    orch, state_store = _build_orchestrator(physical_adapter=adapter)

    await orch.process_traffic_state(_heavy_north_state())

    safety_result = state_store.get_safety_result()
    assert safety_result is not None
    assert "approved" in safety_result

    adapter.stop()


@pytest.mark.asyncio
async def test_traffic_state_not_modified_by_transport_fault():
    """TrafficState must remain unmodified regardless of physical layer health."""
    transport = DummySerialTransport()
    transport.fail_writes = True

    adapter = PhysicalControllerAdapter(transport=transport, ack_timeout=0.1)
    adapter.start()

    orch, state_store = _build_orchestrator(physical_adapter=adapter)

    ts = _heavy_north_state()
    await orch.process_traffic_state(ts)

    stored_ts = state_store.get_traffic_state()
    assert stored_ts is not None
    assert stored_ts.timestamp == ts.timestamp
    assert stored_ts.lanes[Lane.NORTH].vehicle_count == 20

    adapter.stop()


# ---------------------------------------------------------------------------
# Section B: End-to-end software simulation
# Decision → Safety → Controller → SignalState → Adapter → MockTransport
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_e2e_signal_state_reaches_mock_transport():
    """Full pipeline: TrafficState → orchestrator → SignalState → mock transport."""
    transport = DummySerialTransport()

    adapter = PhysicalControllerAdapter(transport=transport, ack_timeout=0.2)
    adapter.start()

    orch, state_store = _build_orchestrator(physical_adapter=adapter)

    # Pre-load an ACK so the adapter considers it confirmed
    transport.mock_responses.append(
        '{"version": 1, "type": "ACK", "command_id": 1, "payload": {}}\n'
    )

    await orch.process_traffic_state(_heavy_north_state())

    # Give the background worker time to dispatch
    time.sleep(0.15)

    # The mock transport must have received the serialized signal state
    assert transport.last_written is not None, "No data was sent to the mock transport"
    import json
    msg = json.loads(transport.last_written)
    assert msg["version"] == 1
    assert msg["type"] == "SET_SIGNAL_STATE"
    assert "lanes" in msg["payload"]

    # Logical state authority is unchanged
    committed = state_store.get_signal_state()
    assert committed is not None

    adapter.stop()


@pytest.mark.asyncio
async def test_e2e_adapter_status_connected_after_ack():
    """After a successful ACK, adapter status must be CONNECTED."""
    transport = DummySerialTransport()
    adapter = PhysicalControllerAdapter(transport=transport, ack_timeout=0.2)
    adapter.start()

    orch, _ = _build_orchestrator(physical_adapter=adapter)

    transport.mock_responses.append(
        '{"version": 1, "type": "ACK", "command_id": 1, "payload": {}}\n'
    )
    await orch.process_traffic_state(_heavy_north_state())
    time.sleep(0.15)

    assert adapter.status == PhysicalControllerStatus.CONNECTED

    adapter.stop()


# ---------------------------------------------------------------------------
# Section C: Offline / no-hardware startup
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_backend_operates_without_physical_adapter():
    """Orchestrator must work correctly when physical_adapter=None."""
    orch, state_store = _build_orchestrator(physical_adapter=None)
    decision = await orch.process_traffic_state(_heavy_north_state())
    assert decision is not None
    assert state_store.get_signal_state() is not None


@pytest.mark.asyncio
async def test_backend_operates_with_failed_transport():
    """Backend must work even if the transport cannot connect."""

    class FailingTransport(DummySerialTransport):
        def connect(self):
            return False  # always fails

    transport = FailingTransport()
    adapter = PhysicalControllerAdapter(transport=transport, ack_timeout=0.1)
    adapter.start()  # adapter itself must not crash even when connect() fails

    orch, state_store = _build_orchestrator(physical_adapter=adapter)
    decision = await orch.process_traffic_state(_heavy_north_state())

    assert decision is not None
    assert state_store.get_signal_state() is not None

    adapter.stop()


# ---------------------------------------------------------------------------
# Section D: Clean shutdown
# ---------------------------------------------------------------------------

def test_adapter_shutdown_is_clean_no_hang():
    """stop() must return within a reasonable timeout in all transport states."""
    transport = DummySerialTransport()
    adapter = PhysicalControllerAdapter(transport=transport, ack_timeout=2.0)
    adapter.start()

    state = SignalState(timestamp=time.time(), phase=SignalPhase.GREEN,
                        active_lanes=[Lane.NORTH], north=SignalColor.GREEN)
    adapter.update_signal_state(state)
    time.sleep(0.02)

    start = time.time()
    adapter.stop()
    elapsed = time.time() - start
    assert elapsed < 5.0, f"stop() hung for {elapsed:.1f}s"


def test_adapter_shutdown_with_disconnected_transport():
    transport = DummySerialTransport()
    adapter = PhysicalControllerAdapter(transport=transport, ack_timeout=0.1)
    adapter.start()
    transport.disconnect()  # simulate mid-session disconnection

    start = time.time()
    adapter.stop()
    assert time.time() - start < 5.0


def test_adapter_shutdown_with_failing_transport():
    transport = DummySerialTransport()
    adapter = PhysicalControllerAdapter(transport=transport, ack_timeout=0.1)
    adapter.start()
    transport.fail_writes = True

    start = time.time()
    adapter.stop()
    assert time.time() - start < 5.0
