"""
AegisFlow AI - Physical Controller Adapter
Non-blocking software boundary linking the authoritative SignalState to the physical actuator.

WP15 Architecture Notes
========================

Worker-loop design
------------------
The worker loop separates signal-command dispatch from heartbeat with a
short idle timeout.  Key invariants:

1. HEARTBEAT CANNOT STARVE A COMMAND.
   The heartbeat is only sent when the worker is idle (no pending command
   and no ACK wait in progress).

2. A COMMAND CANNOT STARVE THE HEARTBEAT INDEFINITELY.
   The ACK wait is bounded by ack_timeout.  If no ACK arrives the state is
   retried up to MAX_RETRIES times before being abandoned, freeing the
   worker for heartbeat traffic.

3. PING/PONG DOES NOT DEADLOCK.
   _dispatch_heartbeat() is a separate code-path from _dispatch_state();
   it can only be entered when there is no pending command ACK wait.

USB disconnect detection (Windows ghost-handle problem)
-------------------------------------------------------
On Windows, physically unplugging a USB-UART adapter does NOT immediately
cause serial.Serial.is_open to return False.  The OS COM-port ghost can
linger for seconds.  write() may silently succeed (bytes go nowhere).

Fix: PySerialTransport counts consecutive I/O exceptions.  After
_MAX_IO_FAILURES failures it force-disconnects regardless of is_open.
The worker loop therefore sees transport.is_connected() == False, enters
the reconnect branch, and marks the adapter FAULT when reconnect fails.

MCU soft-reset detection (ESP32 EN/RST button)
-----------------------------------------------
The USB-UART chip (CP2102/CH340) stays enumerated when the ESP32 MCU
resets.  The COM port handle remains open on the host side.  We CANNOT
rely on is_connected() to detect MCU reboot.

Fix: The heartbeat PING asks the MCU for its last_command_id.  After a
cold reset the firmware initialises last_command_id = -1.  When the host
receives a PONG with last_command_id == -1 (and had previously ACKed at
least one command) it concludes the MCU has rebooted and immediately
resends the latest authoritative SignalState.

Reconnect / state resynchronisation
-------------------------------------
Reconnect is NOT considered complete merely because is_connected() returns
True.  The adapter must receive at least one successful PONG (heartbeat
round-trip) or ACK (command round-trip) before the status is promoted to
CONNECTED.
"""

import threading
import queue
import logging
import time
from typing import Optional

from models import SignalState
from models.enums import PhysicalControllerStatus
from .protocol import HardwareProtocol
from .serial_transport import SerialTransport

logger = logging.getLogger(__name__)

# Maximum number of consecutive dispatch failures before giving up on a state
_MAX_RETRIES = 3
# How long (seconds) to wait for a PONG response to a PING
_HEARTBEAT_TIMEOUT = 1.0
# How long (seconds) the idle loop pauses before sending the next heartbeat
_IDLE_POLL_INTERVAL = 0.5


class PhysicalControllerAdapter:
    """
    Non-blocking adapter that bridges the authoritative SignalState to the
    physical ESP32 actuator via a SerialTransport.

    All serial I/O runs in a dedicated daemon thread.  The caller is never
    blocked; it simply calls update_signal_state() and the worker takes care
    of serialisation, dispatch, and ACK handling.
    """

    def __init__(self, transport: SerialTransport, ack_timeout: float = 2.0):
        self.transport = transport
        self.ack_timeout = ack_timeout

        self.status = PhysicalControllerStatus.DISCONNECTED
        self._command_id_counter = 0
        self.last_sent_command_id: Optional[int] = None
        self.last_acked_command_id: Optional[int] = None

        # Bounded queue (size 1 for latest-state semantics)
        self._command_queue: queue.Queue = queue.Queue(maxsize=1)
        self._shutdown_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._latest_committed_state: Optional[SignalState] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self):
        """Starts the asynchronous worker thread for non-blocking serial dispatch."""
        if self._worker_thread and self._worker_thread.is_alive():
            logger.warning("Adapter already running.")
            return

        self._shutdown_event.clear()
        self.status = PhysicalControllerStatus.CONNECTING
        if self.transport.connect():
            self.status = PhysicalControllerStatus.CONNECTED
        else:
            self.status = PhysicalControllerStatus.FAULT

        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name="PhysicalAdapterThread",
        )
        self._worker_thread.start()
        logger.info("PhysicalControllerAdapter started.")

    def stop(self):
        """Signals the worker thread to stop and closes transport."""
        self._shutdown_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=3.0)
        self.transport.disconnect()
        self.status = PhysicalControllerStatus.DISCONNECTED
        logger.info("PhysicalControllerAdapter stopped.")

    def update_signal_state(self, state: SignalState):
        """
        Non-blocking intake of the latest authoritative SignalState.
        Maintains latest-state semantics by overwriting any pending command.
        Does NOT modify the logical SignalState object.
        """
        self._latest_committed_state = state

        # Flush the queue so only the latest state is sent
        try:
            self._command_queue.get_nowait()
        except queue.Empty:
            pass

        try:
            self._command_queue.put_nowait(state)
        except queue.Full:
            pass  # Should never happen since we just flushed

    # ------------------------------------------------------------------
    # Worker loop
    # ------------------------------------------------------------------

    def _worker_loop(self):
        """
        Background loop handling serial I/O, heartbeat, and retries.

        State machine:
          - If transport is disconnected → try to reconnect.
          - If a new state arrives → dispatch it (send + wait for ACK).
          - If idle → send a heartbeat PING and process the PONG.
        """
        was_connected = self.transport.is_connected()
        current_state: Optional[SignalState] = None
        retry_count = 0

        while not self._shutdown_event.is_set():
            is_connected = self.transport.is_connected()

            # ----------------------------------------------------------
            # Detect reconnect (transport came back after being gone)
            # ----------------------------------------------------------
            if is_connected and not was_connected:
                logger.info("PhysicalControllerAdapter: transport reconnected.")
                # Do NOT promote to CONNECTED yet — wait for a real PONG/ACK.
                if self._latest_committed_state:
                    self.update_signal_state(self._latest_committed_state)

            # ----------------------------------------------------------
            # Proactive reconnect when transport is absent
            # ----------------------------------------------------------
            if not is_connected:
                self.status = PhysicalControllerStatus.FAULT
                time.sleep(0.5)
                if self._shutdown_event.is_set():
                    break
                logger.debug("PhysicalControllerAdapter: attempting reconnect…")
                if self.transport.connect():
                    is_connected = True
                    # Do NOT set CONNECTED here; liveness must be confirmed via PONG/ACK.
                    logger.info(
                        "PhysicalControllerAdapter: transport reconnected (liveness pending)."
                    )
                    if self._latest_committed_state:
                        self.update_signal_state(self._latest_committed_state)
                else:
                    self.status = PhysicalControllerStatus.FAULT
                    was_connected = False
                    continue

            was_connected = is_connected

            if not is_connected:
                continue

            # ----------------------------------------------------------
            # Drain the command queue (latest-state semantics)
            # ----------------------------------------------------------
            try:
                timeout = _IDLE_POLL_INTERVAL if current_state is None else 0.05
                new_state: SignalState = self._command_queue.get(timeout=timeout)
                current_state = new_state
                retry_count = 0
            except queue.Empty:
                pass
            except Exception as e:
                logger.error(f"Error in adapter worker loop: {e}")
                self.status = PhysicalControllerStatus.FAULT
                time.sleep(1.0)
                continue

            # ----------------------------------------------------------
            # Dispatch pending state  OR  send heartbeat
            # ----------------------------------------------------------
            if current_state is not None:
                success = self._dispatch_state(current_state)
                if success:
                    current_state = None
                    retry_count = 0
                else:
                    retry_count += 1
                    if retry_count > _MAX_RETRIES:
                        logger.error("Max retries exceeded for command — discarding.")
                        current_state = None
                        retry_count = 0
                    else:
                        time.sleep(0.5)  # backoff before retry
            else:
                # Idle — send heartbeat to confirm MCU liveness
                self._dispatch_heartbeat()

    # ------------------------------------------------------------------
    # Heartbeat — PING / PONG
    # ------------------------------------------------------------------

    def _dispatch_heartbeat(self):
        """
        Send a PING and process the PONG response.

        Side effects:
          - CONNECTED : PONG received with expected (or acceptable) last_command_id.
          - DEGRADED  : PONG not received within _HEARTBEAT_TIMEOUT.
          - Triggers state resync when PONG carries last_command_id == -1
            (MCU cold-started / was reset).
        """
        if not self.transport.is_connected():
            return

        ping_payload = HardwareProtocol.serialize_ping()
        logger.debug("[HOST TX] PING")
        if not self.transport.write_line(ping_payload):
            logger.warning("Heartbeat PING: write failed — marking FAULT.")
            self.status = PhysicalControllerStatus.FAULT
            return

        deadline = time.time() + _HEARTBEAT_TIMEOUT
        while time.time() < deadline:
            if self._shutdown_event.is_set():
                return

            response_line = self.transport.read_line()
            if response_line:
                # Log any non-JSON lines for diagnostics
                stripped = response_line.strip()
                if not stripped.startswith('{'):
                    logger.info(f"[HOST RX] non-JSON line: {stripped!r}")
                    continue

                msg = HardwareProtocol.parse_response(response_line)
                if msg is None:
                    logger.warning(f"[HOST RX] unparseable line: {stripped!r}")
                    continue

                if msg.type == "PONG":
                    mcu_last_cmd = msg.payload.get("last_command_id")
                    logger.debug(
                        f"[HOST RX] PONG last_command_id={mcu_last_cmd} "
                        f"(host last_acked={self.last_acked_command_id})"
                    )
                    self.status = PhysicalControllerStatus.CONNECTED

                    # MCU reset detection — firmware initialises last_command_id to -1
                    # We trigger resync whenever mcu_last_cmd is -1, regardless of
                    # whether the host had a previous acked command.  This handles the
                    # case where the first power-on heartbeat fires before any command
                    # has been sent.
                    if mcu_last_cmd == -1:
                        if self.last_acked_command_id is not None:
                            logger.warning(
                                "MCU reset detected via PONG (last_command_id=-1, "
                                f"host had acked cmd={self.last_acked_command_id}). "
                                "Resynchronizing authoritative state…"
                            )
                        else:
                            logger.info(
                                "PONG last_command_id=-1 (MCU cold start or no prior "
                                "commands). Will resync if authoritative state exists."
                            )
                        self.last_acked_command_id = None
                        if self._latest_committed_state is not None:
                            self.update_signal_state(self._latest_committed_state)
                    return

                elif msg.type == "ACK":
                    logger.debug(f"[HOST RX] ACK command_id={msg.command_id} (during heartbeat window)")
                    # Stale ACK from a previous command — update tracking but do not
                    # treat as a heartbeat PONG.
                    if msg.command_id is not None:
                        self.last_acked_command_id = msg.command_id
                        self.status = PhysicalControllerStatus.CONNECTED
                    # Keep waiting for the PONG in the remaining timeout window.

                elif msg.type == "NACK":
                    logger.warning(f"[HOST RX] NACK command_id={msg.command_id} payload={msg.payload}")

                else:
                    logger.debug(f"[HOST RX] {msg.type} (unexpected during heartbeat)")

            time.sleep(0.01)

        logger.warning("Heartbeat PING timed out — marking DEGRADED.")
        self.status = PhysicalControllerStatus.DEGRADED

    # ------------------------------------------------------------------
    # Command dispatch — SET_SIGNAL_STATE / ACK wait
    # ------------------------------------------------------------------

    def _dispatch_state(self, state: SignalState) -> bool:
        """
        Serialize and write the state to hardware, then wait for ACK.
        Returns True on confirmed ACK, False on failure / timeout.
        Does NOT modify the logical SignalState object.
        """
        if not self.transport.is_connected():
            if not self.transport.connect():
                self.status = PhysicalControllerStatus.FAULT
                return False
            # Liveness not yet confirmed — do not set CONNECTED until ACK arrives.

        self._command_id_counter += 1
        cmd_id = self._command_id_counter
        self.last_sent_command_id = cmd_id

        payload_str = HardwareProtocol.serialize_signal_state(state, cmd_id)
        logger.debug(f"[HOST TX] SET_SIGNAL_STATE command_id={cmd_id}")

        if not self.transport.write_line(payload_str):
            logger.error(f"Failed to write SET_SIGNAL_STATE command_id={cmd_id} to serial transport.")
            self.status = PhysicalControllerStatus.FAULT
            return False

        # Wait for ACK
        deadline = time.time() + self.ack_timeout
        while time.time() < deadline:
            if self._shutdown_event.is_set():
                return False

            response_line = self.transport.read_line()
            if response_line:
                stripped = response_line.strip()
                if not stripped.startswith('{'):
                    logger.info(f"[HOST RX] non-JSON line: {stripped!r}")
                    continue

                msg = HardwareProtocol.parse_response(response_line)
                if msg is None:
                    logger.warning(f"[HOST RX] unparseable line: {stripped!r}")
                    continue

                if msg.type == "ACK":
                    logger.debug(f"[HOST RX] ACK command_id={msg.command_id}")
                    if msg.command_id == cmd_id:
                        self.last_acked_command_id = cmd_id
                        self.status = PhysicalControllerStatus.CONNECTED
                        return True
                    else:
                        logger.debug(
                            f"[HOST RX] ACK command_id={msg.command_id} "
                            f"(expected {cmd_id}) — stale, ignoring"
                        )

                elif msg.type == "NACK":
                    logger.error(f"[HOST RX] NACK command_id={msg.command_id} payload={msg.payload}")
                    if msg.command_id == cmd_id:
                        self.status = PhysicalControllerStatus.DEGRADED
                        return False

                elif msg.type == "PONG":
                    mcu_last_cmd = msg.payload.get("last_command_id")
                    logger.debug(
                        f"[HOST RX] PONG last_command_id={mcu_last_cmd} "
                        "(received during ACK wait — MCU may have reset)"
                    )
                    if mcu_last_cmd == -1:
                        logger.warning(
                            "MCU reset detected during ACK wait "
                            f"(waiting for cmd_id={cmd_id}). "
                            "Aborting wait; resync will be triggered by next heartbeat."
                        )
                        self.last_acked_command_id = None
                        return False

                elif msg.type == "ERROR":
                    logger.error(f"[HOST RX] ERROR payload={msg.payload}")

                else:
                    logger.debug(f"[HOST RX] unknown type={msg.type!r}")

            time.sleep(0.01)  # small sleep to prevent busy spin

        logger.error(f"Timeout waiting for ACK for command_id={cmd_id}")
        self.status = PhysicalControllerStatus.DEGRADED
        return False
