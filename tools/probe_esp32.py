"""
AegisFlow — WP15 Manual Integration Probe
==========================================
Run this script ONLY when the real ESP32 is connected on COM4
and the Arduino Serial Monitor is closed.

Usage (from project root, with .venv active):

  Automatic (original behaviour, times out on each physical action):
      python tools/probe_esp32.py

  Interactive (gates every physical action behind ENTER — use for hardware validation):
      python tools/probe_esp32.py --interactive

WP15 Tests:
  1. 9 signal commands + ACKs                 (automatic in both modes)
  2. Heartbeat PING/PONG verification         (automatic in both modes)
  3. ESP32 soft reset detection + resync      (gated in --interactive)
  4. USB physical disconnect → FAULT/DEGRADED (gated in --interactive)
  5. USB reconnect → state recovery           (gated in --interactive)
"""

import argparse
import time
import logging
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from models import SignalState, SignalPhase, Lane, SignalColor
from hardware.adapter import PhysicalControllerAdapter
from hardware.serial_transport import PySerialTransport
from models.enums import PhysicalControllerStatus

logging.basicConfig(
    level=logging.DEBUG,   # WP15: DEBUG exposes all [HOST TX]/[HOST RX] diagnostics
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger("probe_esp32")

# ── signal-state helpers ──────────────────────────────────────────────────────

RED    = SignalColor.RED
YELLOW = SignalColor.YELLOW
GREEN  = SignalColor.GREEN


def _all_red(ts: float) -> SignalState:
    return SignalState(timestamp=ts, phase=SignalPhase.ALL_RED)


def _make_state(
    ts: float,
    phase: SignalPhase,
    green_lane: Lane,
    north: SignalColor,
    south: SignalColor,
    east: SignalColor,
    west: SignalColor,
) -> SignalState:
    return SignalState(
        timestamp=ts,
        phase=phase,
        active_lanes=[green_lane],
        north=north,
        south=south,
        east=east,
        west=west,
    )


STATES = [
    ("ALL_RED",      _all_red(1.0)),
    ("NORTH_GREEN",  _make_state(2.0, SignalPhase.GREEN,  Lane.NORTH, GREEN,  RED,    RED,    RED)),
    ("NORTH_YELLOW", _make_state(3.0, SignalPhase.YELLOW, Lane.NORTH, YELLOW, RED,    RED,    RED)),
    ("EAST_GREEN",   _make_state(4.0, SignalPhase.GREEN,  Lane.EAST,  RED,    RED,    GREEN,  RED)),
    ("EAST_YELLOW",  _make_state(5.0, SignalPhase.YELLOW, Lane.EAST,  RED,    RED,    YELLOW, RED)),
    ("SOUTH_GREEN",  _make_state(6.0, SignalPhase.GREEN,  Lane.SOUTH, RED,    GREEN,  RED,    RED)),
    ("SOUTH_YELLOW", _make_state(7.0, SignalPhase.YELLOW, Lane.SOUTH, RED,    YELLOW, RED,    RED)),
    ("WEST_GREEN",   _make_state(8.0, SignalPhase.GREEN,  Lane.WEST,  RED,    RED,    RED,    GREEN)),
    ("WEST_YELLOW",  _make_state(9.0, SignalPhase.YELLOW, Lane.WEST,  RED,    RED,    RED,    YELLOW)),
]

# ── polling helpers ───────────────────────────────────────────────────────────

def _wait_for_ack(
    adapter: PhysicalControllerAdapter,
    prev_acked,
    timeout: float = 5.0,
) -> bool:
    """Poll until last_acked_command_id changes AND matches last_sent_command_id."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if (
            adapter.last_acked_command_id != prev_acked
            and adapter.last_sent_command_id == adapter.last_acked_command_id
        ):
            return True
        time.sleep(0.05)
    return False


def _wait_for_mcu_resync(
    adapter: PhysicalControllerAdapter,
    pre_event_acked,
    timeout: float = 20.0,
) -> bool:
    """
    Poll until last_acked_command_id changes AND status == CONNECTED.
    Confirms: reset/reconnect detected, state resent, ACK received.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if (
            adapter.last_acked_command_id != pre_event_acked
            and adapter.status == PhysicalControllerStatus.CONNECTED
        ):
            return True
        time.sleep(0.1)
    return False


def _wait_for_fault_or_degraded(
    adapter: PhysicalControllerAdapter,
    timeout: float = 10.0,
) -> bool:
    """Poll until status is not CONNECTED (i.e. FAULT or DEGRADED)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if adapter.status not in (
            PhysicalControllerStatus.CONNECTED,
            PhysicalControllerStatus.CONNECTING,
        ):
            return True
        time.sleep(0.2)
    return False


# ── interactive UI helpers ────────────────────────────────────────────────────

def _banner(text: str) -> None:
    """Print a highly visible section banner to stdout (bypasses logging)."""
    width = 68
    line  = "=" * width
    print(f"\n{line}", flush=True)
    print(f"  {text}", flush=True)
    print(f"{line}", flush=True)


def _prompt(lines: list) -> None:
    """Print each line verbatim then wait for the user to press ENTER."""
    print(flush=True)
    for line in lines:
        print(f"  {line}", flush=True)
    print(flush=True)
    input("  >>> Press ENTER to continue... ")
    print(flush=True)


def _info(msg: str) -> None:
    """Dual-channel: log at INFO and also print directly so it stays above the prompt."""
    logger.info(msg)


# ── sections ──────────────────────────────────────────────────────────────────

def _section1(adapter: PhysicalControllerAdapter) -> bool:
    """9 signal commands + ACK verification. Fully automatic."""
    _banner("SECTION 1 — 9 signal commands + ACK verification")

    results = []
    for label, state in STATES:
        _info(f"── Sending {label} ──")
        prev_acked = adapter.last_acked_command_id

        adapter.update_signal_state(state)
        ok = _wait_for_ack(adapter, prev_acked, timeout=5.0)

        sent   = adapter.last_sent_command_id
        acked  = adapter.last_acked_command_id
        status = adapter.status

        ok = (
            ok
            and sent == acked
            and sent is not None
            and status == PhysicalControllerStatus.CONNECTED
        )

        _info(f"   SENT command_id={sent}")
        _info(f"   RX   ACK command_id={acked}")
        _info(f"   ACK MATCH = {'PASS' if ok else 'FAIL'}  (adapter status: {status})")
        _info("")
        results.append((label, status, "PASS" if ok else "FAIL"))
        time.sleep(0.3)

    sec_pass = all(r[2] == "PASS" for r in results)
    _info(f"SECTION 1 RESULT: {'PASS' if sec_pass else 'FAIL'}")
    for label, status, verdict in results:
        _info(f"  {verdict}  {label}  ({status})")
    _info("")
    return sec_pass


def _section2(adapter: PhysicalControllerAdapter) -> bool:
    """Heartbeat PING/PONG — observe DEBUG logs. Fully automatic."""
    _banner("SECTION 2 — Heartbeat PING/PONG")
    _info("Observe DEBUG logs for [HOST TX] PING and [HOST RX] PONG.")
    _info("Waiting 3 seconds for heartbeat cycles…")

    pre_status = adapter.status
    time.sleep(3.0)
    post_status = adapter.status

    sec_pass = post_status == PhysicalControllerStatus.CONNECTED
    _info(f"Status before: {pre_status}  →  after 3 s: {post_status}")
    _info(f"SECTION 2 RESULT: {'PASS' if sec_pass else 'FAIL'}")
    _info("")
    return sec_pass


def _section3(adapter: PhysicalControllerAdapter, interactive: bool) -> bool:
    """ESP32 soft reset detection + automatic state resynchronization."""
    _banner("SECTION 3 — ESP32 soft reset detection + resync")

    if interactive:
        _prompt([
            "SECTION 3 READY",
            "The ESP32 is connected.",
            "Press ENTER when you are physically ready.",
        ])

    # Set authoritative NORTH_GREEN and wait for ACK
    _info("Setting authoritative state to NORTH_GREEN…")
    north_green = _make_state(25.0, SignalPhase.GREEN, Lane.NORTH, GREEN, RED, RED, RED)
    prev_acked  = adapter.last_acked_command_id
    adapter.update_signal_state(north_green)

    ack_ok = _wait_for_ack(adapter, prev_acked, timeout=5.0)
    _info(
        f"NORTH_GREEN ACK: {'received' if ack_ok else 'TIMEOUT'}  "
        f"(command_id={adapter.last_acked_command_id}, status={adapter.status})"
    )
    if not ack_ok:
        _info("SECTION 3 RESULT: FAIL  (could not confirm NORTH_GREEN before reset)")
        return False

    pre_reset_acked = adapter.last_acked_command_id

    if interactive:
        _prompt([
            "RESET TEST READY",
            "Press EN/RST once NOW.",
            "After pressing, wait for the ESP32 to reboot (the LED may blink).",
            "Press ENTER ONLY AFTER you have pressed EN/RST.",
        ])
        monitor_seconds = 20.0
    else:
        _info(">>> NOW PRESS THE ESP32 EN/RST BUTTON <<<")
        monitor_seconds = 12.0

    _info(
        f"Monitoring PING/PONG for up to {monitor_seconds:.0f} seconds "
        "for PONG last_command_id=-1 → resync → ACK…"
    )
    _info("Expected sequence: PONG(-1) → SET_SIGNAL_STATE → ACK → CONNECTED")
    _info("")

    reset_detected = _wait_for_mcu_resync(adapter, pre_reset_acked, timeout=monitor_seconds)

    post_status = adapter.status
    post_acked  = adapter.last_acked_command_id

    if reset_detected:
        _info(f"  RESET DETECTED  new ACKed command_id={post_acked}")
        _info(f"  Adapter status:  {post_status}")
        _info("SECTION 3 RESULT: PASS")
        return True
    else:
        _info(f"  Reset NOT detected within {monitor_seconds:.0f} s.")
        _info(f"  Status: {post_status}  last_acked: {post_acked}")
        _info("  (Check DEBUG log for [HOST RX] PONG lines to see last_command_id values.)")
        _info("SECTION 3 RESULT: FAIL")
        return False


def _section4(adapter: PhysicalControllerAdapter, interactive: bool) -> bool:
    """Physical USB disconnect → adapter must leave CONNECTED and enter FAULT/DEGRADED."""
    _banner("SECTION 4 — USB physical disconnect → FAULT / DEGRADED")

    if interactive:
        _prompt([
            "USB DISCONNECT TEST READY",
            "Verify the USB cable is currently connected.",
            "Press ENTER when ready.",
        ])
        _prompt([
            "NOW UNPLUG THE USB CABLE FROM THE ESP32.",
            "Do not reconnect it until Section 5.",
            "Press ENTER AFTER COM4 HAS DISAPPEARED FROM WINDOWS DEVICE MANAGER.",
        ])
        monitor_seconds = 10.0
    else:
        _info(">>> PHYSICALLY UNPLUG THE USB CABLE NOW <<<")
        _info("Waiting 8 seconds…")
        time.sleep(8.0)
        monitor_seconds = 4.0

    _info(
        f"Monitoring adapter status for up to {monitor_seconds:.0f} s "
        "for FAULT or DEGRADED…"
    )
    _info("(The ghost-handle protection will force-disconnect after 3 consecutive I/O failures.)")

    fault_detected = _wait_for_fault_or_degraded(adapter, timeout=monitor_seconds)
    disconnect_status = adapter.status

    # If the fast poll didn't catch it yet, do one explicit write to provoke the error counter.
    if not fault_detected:
        _info("Status still CONNECTED — forcing a write attempt to accelerate I/O failure detection…")
        adapter.update_signal_state(_all_red(20.0))
        fault_detected = _wait_for_fault_or_degraded(adapter, timeout=6.0)
        disconnect_status = adapter.status

    sec_pass = disconnect_status in (
        PhysicalControllerStatus.FAULT,
        PhysicalControllerStatus.DEGRADED,
    )
    _info(f"Adapter status: {disconnect_status}")
    _info(f"Expected:       FAULT or DEGRADED")
    _info(f"SECTION 4 RESULT: {'PASS' if sec_pass else 'FAIL'}")
    _info("")
    return sec_pass


def _section5(adapter: PhysicalControllerAdapter, interactive: bool) -> bool:
    """USB reconnect → transport reconnects → liveness confirmed via PONG/ACK → CONNECTED."""
    _banner("SECTION 5 — USB reconnect → state recovery")

    if interactive:
        _prompt([
            "RECONNECT TEST",
            "Plug the USB cable back into the ESP32 now.",
            "Press ENTER after COM4 reappears in Windows Device Manager.",
        ])
        monitor_seconds = 15.0
    else:
        _info(">>> PLUG THE USB CABLE BACK IN NOW <<<")
        _info("Waiting 10 seconds for reconnection + PONG liveness + resync…")
        time.sleep(10.0)
        monitor_seconds = 5.0

    _info(
        f"Monitoring for up to {monitor_seconds:.0f} s for real PONG/ACK liveness "
        "before CONNECTED is declared…"
    )
    _info("(A PONG or ACK must arrive — is_connected() alone is not sufficient.)")

    pre_reconnect_acked = adapter.last_acked_command_id
    reconnect_ok = _wait_for_mcu_resync(adapter, pre_reconnect_acked, timeout=monitor_seconds)

    final_status = adapter.status
    final_acked  = adapter.last_acked_command_id

    _info(f"Adapter status after reconnect: {final_status}")
    _info(f"Last ACKed command_id:          {final_acked}")
    _info(f"SECTION 5 RESULT: {'PASS' if reconnect_ok else 'FAIL'}")
    _info("")
    return reconnect_ok


# ── entry point ───────────────────────────────────────────────────────────────

def run_probe(interactive: bool = False) -> None:
    mode_label = "INTERACTIVE" if interactive else "AUTOMATIC"
    _banner(f"AegisFlow WP15 — ESP32 Integration Probe  [{mode_label}]")
    _info("DEBUG level active: all PING/PONG/ACK/NACK messages will be logged.")
    if interactive:
        _info("Interactive mode: each physical action is gated behind an ENTER prompt.")
    else:
        _info("Automatic mode: physical actions use fixed time delays.")
    _info("")

    transport = PySerialTransport(port="COM4", baud_rate=115200)
    adapter   = PhysicalControllerAdapter(transport=transport, ack_timeout=3.0)

    adapter.start()
    time.sleep(1.5)

    if adapter.status not in (PhysicalControllerStatus.CONNECTED,):
        logger.error(f"Failed to connect. Adapter status: {adapter.status}")
        adapter.stop()
        sys.exit(1)

    sec1_pass      = _section1(adapter)
    hb_ok          = _section2(adapter)
    sec3_pass      = _section3(adapter, interactive)
    disconnect_ok  = _section4(adapter, interactive)
    reconnect_ok   = _section5(adapter, interactive)

    # ── final report ──────────────────────────────────────────────────
    _banner("WP15 PROBE SUMMARY")
    _info(f"  SECTION 1 (9 commands + ACKs):   {'PASS' if sec1_pass else 'FAIL'}")
    _info(f"  SECTION 2 (heartbeat PING/PONG):  {'PASS' if hb_ok else 'FAIL'}")
    _info(f"  SECTION 3 (MCU reset + resync):   {'PASS' if sec3_pass else 'FAIL'}")
    _info(f"  SECTION 4 (USB disconnect FAULT):  {'PASS' if disconnect_ok else 'FAIL'}")
    _info(f"  SECTION 5 (reconnect + recovery):  {'PASS' if reconnect_ok else 'FAIL'}")

    all_pass = sec1_pass and hb_ok and sec3_pass and disconnect_ok and reconnect_ok
    _info("")
    if all_pass:
        _info("WP15 HARDWARE VALIDATION PASS")
    else:
        _info("WP15 HARDWARE VALIDATION FAIL")

    adapter.stop()
    _info("Probe complete.")
    _info("")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "AegisFlow WP15 ESP32 integration probe.\n"
            "Run with --interactive to gate each physical action behind an ENTER prompt."
        )
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        default=False,
        help=(
            "Enable interactive mode. "
            "Each physical action (reset, disconnect, reconnect) is gated "
            "behind an ENTER prompt so you cannot miss the action."
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run_probe(interactive=args.interactive)
