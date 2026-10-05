import pytest
import time
import json
from models import SignalState, SignalPhase
from models.enums import PhysicalControllerStatus
from hardware.adapter import PhysicalControllerAdapter
from hardware.serial_transport import DummySerialTransport

def _create_state(ts=1.0):
    return SignalState(timestamp=ts, phase=SignalPhase.ALL_RED)

@pytest.fixture
def dummy_transport():
    transport = DummySerialTransport()
    # Override connect to default True
    transport.connected = False
    return transport

@pytest.fixture
def adapter(dummy_transport):
    adapter = PhysicalControllerAdapter(transport=dummy_transport, ack_timeout=0.2)
    yield adapter
    adapter.stop()

def test_heartbeat_success(adapter, dummy_transport):
    adapter.start()
    time.sleep(0.1) # Let it connect
    
    # Send PONG in response to heartbeat
    pong_json = json.dumps({"version": 1, "type": "PONG", "payload": {"last_command_id": 5}})
    dummy_transport.mock_responses.append(pong_json + "\n")
    
    # Wait for heartbeat cycle
    time.sleep(0.6)
    assert adapter.status == PhysicalControllerStatus.CONNECTED

def test_heartbeat_timeout(adapter, dummy_transport):
    adapter.start()
    time.sleep(0.1) # Let it connect
    
    # Do NOT send PONG, let it timeout (0.5s idle + 1.0s heartbeat wait = 1.5s total)
    time.sleep(1.8)
    # Heartbeat timeout transitions to DEGRADED
    assert adapter.status == PhysicalControllerStatus.DEGRADED

def test_simulated_mcu_reboot_and_resync(adapter, dummy_transport):
    adapter.start()
    time.sleep(0.1)
    
    # 1. Send authoritative state
    state = _create_state(1.0)
    adapter.update_signal_state(state)
    
    # 2. Mock ACK for the state
    ack_json = json.dumps({"version": 1, "type": "ACK", "command_id": 1})
    dummy_transport.mock_responses.append(ack_json + "\n")
    
    time.sleep(0.3)
    assert adapter.status == PhysicalControllerStatus.CONNECTED
    assert adapter.last_acked_command_id == 1
    
    # 3. MCU reboots! It replies to the next PING with last_command_id = -1
    pong_json = json.dumps({"version": 1, "type": "PONG", "payload": {"last_command_id": -1}})
    dummy_transport.mock_responses.append(pong_json + "\n")
    
    # Mock the ACK for the resynchronized state that the adapter will automatically send
    ack2_json = json.dumps({"version": 1, "type": "ACK", "command_id": 2})
    dummy_transport.mock_responses.append(ack2_json + "\n")
    
    time.sleep(0.7) # Wait for PING cycle + resync
    
    assert adapter.status == PhysicalControllerStatus.CONNECTED
    assert adapter.last_acked_command_id == 2 # Proves resynchronization sent command 2 and received ACK 2
    assert adapter.last_sent_command_id == 2

def test_nack_retry_and_bounded(adapter, dummy_transport):
    adapter.start()
    time.sleep(0.1)
    
    state = _create_state(1.0)
    adapter.update_signal_state(state)
    
    # Mock NACKs for retries
    nack_json = json.dumps({"version": 1, "type": "NACK", "command_id": 1, "payload": {"reason": "Busy"}})
    
    # It will try 1 initial + 3 retries = 4 times.
    for i in range(1, 5):
        nack_json = json.dumps({"version": 1, "type": "NACK", "command_id": i, "payload": {"reason": "Busy"}})
        dummy_transport.mock_responses.append(nack_json + "\n")
        
    time.sleep(2.5) # Wait for all retries (0.5s backoff each)
    
    # After max retries, it gives up and drops the state.
    # The adapter is DEGRADED because of NACKs.
    assert adapter.status == PhysicalControllerStatus.DEGRADED
    
    # Send a PONG so the subsequent heartbeat doesn't timeout and ruin the recovery test
    pong_json = json.dumps({"version": 1, "type": "PONG", "payload": {"last_command_id": 4}})
    dummy_transport.mock_responses.append(pong_json + "\n")
    
    # Immediately enqueue state2 so it preempts the next heartbeat
    state2 = _create_state(2.0)
    adapter.update_signal_state(state2)
    
    ack_json = json.dumps({"version": 1, "type": "ACK", "command_id": 5})
    dummy_transport.mock_responses.append(ack_json + "\n")
    
    time.sleep(0.3)
    assert adapter.status == PhysicalControllerStatus.CONNECTED
    assert adapter.last_acked_command_id == 5

def test_serial_disconnect_reconnect(adapter, dummy_transport):
    adapter.start()
    time.sleep(0.1)
    
    state = _create_state(1.0)
    adapter.update_signal_state(state)
    
    ack_json = json.dumps({"version": 1, "type": "ACK", "command_id": 1})
    dummy_transport.mock_responses.append(ack_json + "\n")
    time.sleep(0.2)
    assert adapter.status == PhysicalControllerStatus.CONNECTED
    
    # Disconnect
    dummy_transport.connected = False
    
    # Wait for the worker loop to notice during heartbeat
    time.sleep(0.6)
    
    # Reconnect
    dummy_transport.connected = True
    
    # Provide ACK for the sync-on-connect
    ack2_json = json.dumps({"version": 1, "type": "ACK", "command_id": 2})
    dummy_transport.mock_responses.append(ack2_json + "\n")
    
    time.sleep(0.7)
    assert adapter.status == PhysicalControllerStatus.CONNECTED
    assert adapter.last_acked_command_id == 2
