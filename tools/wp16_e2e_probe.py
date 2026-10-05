"""
AegisFlow — WP16 End-to-End System Integration Validation Probe
================================================================
This script validates the complete AegisFlow chain against the real backend,
running on COM4 with the physical ESP32 connected.

Usage:
  python tools/wp16_e2e_probe.py
"""

import time
import threading
import sys
import os
import json
import logging
from typing import Optional, Dict, Any
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app import app
from backend import core

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(name)s %(message)s")
logger = logging.getLogger("wp16_probe")

def make_demo_traffic(lanes: Optional[Dict[str, Any]] = None, emergency: Optional[Dict[str, Any]] = None, source: str = "wp16-probe") -> dict:
    """
    Constructs a fresh TrafficState dictionary with wall-clock time at invocation.
    Generates timestamp = current wall-clock time at the exact moment called.
    """
    now = time.time()
    return {
        "timestamp": now,
        "source": source,
        "lanes": lanes or {
            "north": {"vehicle_count": 0, "occupancy": 0.0},
            "south": {"vehicle_count": 0, "occupancy": 0.0},
            "east": {"vehicle_count": 0, "occupancy": 0.0},
            "west": {"vehicle_count": 0, "occupancy": 0.0},
        },
        "emergency": emergency or {"detected": False, "lane": None}
    }

def send_demo_traffic(client: TestClient, payload: Optional[dict] = None) -> dict:
    """
    Sends a fresh demo traffic payload to /api/v1/demo/traffic.
    Asserts probe-side that the payload timestamp is within the 5.0s freshness window.
    """
    if payload is None:
        payload = make_demo_traffic()
    
    now = time.time()
    ts = payload.get("timestamp", 0.0)
    age = now - ts
    if not (-1.0 <= age <= 5.0):
        raise AssertionError(
            f"PROBE ERROR: TrafficState timestamp is not fresh! "
            f"current_time={now:.3f}, timestamp={ts:.3f}, age={age:.3f}s "
            f"(must be within 5.0s threshold)"
        )
    
    resp = client.post("/api/v1/demo/traffic", json=payload)
    if resp.status_code != 200:
        raise RuntimeError(f"POST /api/v1/demo/traffic returned status {resp.status_code}: {resp.text}")
    return resp.json()

def _wait_for_ack(prev_ack, timeout=5.0):
    start = time.time()
    while time.time() - start < timeout:
        if core.physical_adapter.last_acked_command_id != prev_ack:
            return core.physical_adapter.last_acked_command_id
        time.sleep(0.1)
    return None

import msvcrt

def _prompt(lines, client=None):
    print("\n" + "="*60)
    for line in lines:
        print(f"  {line}")
    print("="*60 + "\n")
    print("  >>> Press ENTER to continue... ", end="", flush=True)
    
    while True:
        if msvcrt.kbhit():
            ch = msvcrt.getch()
            if ch == b'\r':
                print()
                break
        else:
            if client:
                try:
                    send_demo_traffic(client)
                except Exception:
                    pass
            time.sleep(0.1)
    print()

def run_probe():
    print("Starting WP16 E2E Validation Probe...")
    print("Initializing TestClient (spins up backend and PhysicalControllerAdapter)...")
    
    # Isolate the test harness by pausing the background decision loop.
    # This prevents the autonomous scheduler from injecting normal decisions
    # while we are trying to manually test transitions and safety holds.
    import backend.app as backend_app
    import asyncio
    
    async def mock_decision_loop(*args, **kwargs):
        while True:
            await asyncio.sleep(3600)
            
    # Apply monkey-patch before TestClient spawns it
    original_loop = backend_app._decision_loop
    backend_app._decision_loop = mock_decision_loop
    
    with TestClient(app) as client:
        # Wait for connection
        for _ in range(30):
            if core.physical_adapter.status.value == "CONNECTED":
                print("Hardware CONNECTED via backend adapter.")
                break
            time.sleep(0.1)
        else:
            print("Failed to connect to ESP32. Ensure it's plugged in on COM4.")
            return

        # ---------------------------------------------------------------------
        # WP16.1 & WP16.2 — MULTI-STATE E2E
        # ---------------------------------------------------------------------
        _prompt([
            "WP16.1 & WP16.2 — BACKEND -> ESP32 E2E & MULTI-STATE",
            "This will drive scenarios through the real backend API:",
            "  /api/v1/demo/traffic",
            "and verify the Decision, Safety, SignalState, and hardware ACK."
        ], client=client)
        
        lanes = ["north", "east", "south", "west"]
        for lane in lanes:
            print(f"\n--- Forcing {lane.upper()} via /api/v1/overrides ---")
            prev_ack = core.physical_adapter.last_acked_command_id
            
            resp = client.post("/api/v1/overrides", json={"selected_lane": lane, "duration": 5})
            assert resp.status_code == 200
            
            # Send fresh traffic to trigger orchestrator processing
            send_demo_traffic(client)
            
            # Wait for ACK for the new phase
            new_ack = _wait_for_ack(prev_ack, timeout=5.0)
            print(f"[{lane.upper()}_GREEN] ACK received: {new_ack}")
            
            # Now clear override to let it transition to YELLOW
            client.delete("/api/v1/overrides/current")
            prev_ack = core.physical_adapter.last_acked_command_id
            send_demo_traffic(client)
            
            new_ack = _wait_for_ack(prev_ack, timeout=5.0)
            print(f"[{lane.upper()}_YELLOW] ACK received: {new_ack}")
            
            # Advance to ALL_RED by sending traffic again after YELLOW duration (3s)
            time.sleep(3.2)
            prev_ack = core.physical_adapter.last_acked_command_id
            send_demo_traffic(client)
            
            new_ack = _wait_for_ack(prev_ack, timeout=5.0)
            print(f"[ALL_RED] ACK received: {new_ack}")
            time.sleep(2.2) # ALL_RED duration
            
        print("\nWP16.1 & WP16.2 Complete.\n")
        
        # ---------------------------------------------------------------------
        # WP16.3 — SAFETY INTEGRATION
        # ---------------------------------------------------------------------
        _prompt([
            "WP16.3 — SAFETY INTEGRATION",
            "This will establish NORTH as active GREEN,",
            "then immediately attempt to preempt to EAST to verify",
            "SafetyValidator rejects the unsafe transition due to minimum-green hold",
            "(without falling back to FALLBACK mode)."
        ], client=client)
        
        # 1. Establish NORTH active GREEN
        resp = client.post("/api/v1/overrides", json={"selected_lane": "north", "duration": 15})
        assert resp.status_code == 200
        send_demo_traffic(client)
        _wait_for_ack(core.physical_adapter.last_acked_command_id) # Wait for NORTH GREEN
        
        north_traffic = {
            "north": {"vehicle_count": 20, "occupancy": 0.8},
            "south": {"vehicle_count": 20, "occupancy": 0.8},
            "east": {"vehicle_count": 0, "occupancy": 0.0},
            "west": {"vehicle_count": 0, "occupancy": 0.0},
        }
        
        print("Waiting for NORTH GREEN transition to complete...")
        start_poll = time.time()
        while time.time() - start_poll < 15.0: # increase timeout to outlast min-green hold (10s)
            # Must keep re-posting the override to refresh the SignalDecision timestamp
            client.post("/api/v1/overrides", json={"selected_lane": "north", "duration": 15})
            # Send deterministic traffic aligned with NORTH to suppress competing background decisions
            send_demo_traffic(client, payload=make_demo_traffic(lanes=north_traffic))
            
            snap_north = client.get("/api/v1/snapshot").json()
            if "north" in snap_north["signalState"]["active_lanes"] and snap_north["signalState"]["phase"] == "GREEN":
                break
            time.sleep(0.2)
        else:
            raise AssertionError(f"Timeout waiting for NORTH GREEN. Active lanes: {snap_north['signalState']['active_lanes']}, Phase: {snap_north['signalState']['phase']}")

        # Verify NORTH is active GREEN, approved, and mode is not FALLBACK
        assert "north" in snap_north["signalState"]["active_lanes"], "NORTH must be active green"
        assert snap_north["signalState"]["phase"] == "GREEN", "Phase must be GREEN"
        assert snap_north["safetyResult"]["status"] == "APPROVED", "NORTH must be approved"
        assert snap_north["systemStatus"]["mode"] != "FALLBACK", "Must not be in FALLBACK"
        print(f"NORTH established as active GREEN. Active lanes: {snap_north['signalState']['active_lanes']}")
        
        # 2. Immediately attempt EAST preemption (violating NORTH's minimum-green window)
        print("Now attempting to preempt immediately to EAST (must be REJECTED by min-green hold)...")
        resp = client.post("/api/v1/overrides", json={"selected_lane": "east", "duration": 15})
        assert resp.status_code == 200
        
        east_traffic = {
            "north": {"vehicle_count": 0, "occupancy": 0.0},
            "south": {"vehicle_count": 0, "occupancy": 0.0},
            "east": {"vehicle_count": 20, "occupancy": 0.8},
            "west": {"vehicle_count": 20, "occupancy": 0.8},
        }
        # Send deterministic traffic aligned with EAST override
        send_demo_traffic(client, payload=make_demo_traffic(lanes=east_traffic))
        
        # 3. Verify SafetyValidator REJECTED EAST, mode is NOT fallback, and active lane remains NORTH
        snap_reject = client.get("/api/v1/snapshot").json()
        assert snap_reject["safetyResult"]["status"] == "REJECTED", (
            f"Expected safetyResult status REJECTED, but got {snap_reject['safetyResult']['status']}"
        )
        assert snap_reject["systemStatus"]["mode"] != "FALLBACK", (
            f"System switched to FALLBACK mode! Reasons: {snap_reject['safetyResult']['reasons']}"
        )
        assert any("Minimum green hold" in r for r in snap_reject["safetyResult"]["reasons"]), (
            f"Expected Minimum green hold rejection reason, got: {snap_reject['safetyResult']['reasons']}"
        )
        assert "north" in snap_reject["signalState"]["active_lanes"], (
            f"Active lane should remain NORTH, but got: {snap_reject['signalState']['active_lanes']}"
        )
        print(f"Safety successfully enforced: {snap_reject['safetyResult']['reasons']}")
        print(f"Authoritative active lanes remain: {snap_reject['signalState']['active_lanes']}")
        
        client.delete("/api/v1/overrides/current")
        time.sleep(3) # Wait for it to cycle out naturally
        
        print("\nWP16.3 Complete.\n")

        # ---------------------------------------------------------------------
        # WP16.5 — DASHBOARD SYNCHRONIZATION (WEBSOCKET)
        # ---------------------------------------------------------------------
        _prompt([
            "WP16.5 — DASHBOARD SYNCHRONIZATION (WEBSOCKET)",
            "Connecting to /ws/traffic to verify telemetry broadcast."
        ], client=client)
        with client.websocket_connect("/ws/traffic") as websocket:
            print("WebSocket connected!")
            
            # Trigger a state change with fresh traffic
            send_demo_traffic(client)
            
            data = websocket.receive_json()
            print("WebSocket Snapshot Received!")
            print(f"  SignalState Active Lanes: {data['signalState']['active_lanes']}")
            print(f"  SystemStatus Controller: {data['systemStatus']['controller']}")
        
        print("\nWP16.5 Complete.\n")

        # ---------------------------------------------------------------------
        # WP16.6 — FULL FAILURE ISOLATION
        # ---------------------------------------------------------------------
        _prompt([
            "WP16.6 — FULL FAILURE ISOLATION",
            "Verify the USB cable is connected, then UNPLUG it from the ESP32.",
            "Do not reconnect it yet."
        ], client=client)
        
        print("Waiting for FAULT/DEGRADED...")
        # Force a write to trigger failures quickly, each with fresh traffic
        for _ in range(5):
            send_demo_traffic(client)
            time.sleep(1)
            
        for _ in range(10):
            if core.physical_adapter.status.value in ("FAULT", "DEGRADED", "DISCONNECTED"):
                print(f"Hardware adapter status: {core.physical_adapter.status.value}")
                break
            send_demo_traffic(client) # Keep traffic fresh while waiting
            time.sleep(1)
            
        print("Backend is still alive. Fetching status...")
        resp = client.get("/api/v1/status")
        print(f"Backend API Status: {resp.json()}")
        
        _prompt([
            "Now RECONNECT the USB cable.",
            "Wait for COM4 to reappear in Device Manager."
        ], client=client)
        
        print("Waiting for CONNECTED and real ACK...")
        for _ in range(15):
            if core.physical_adapter.status.value == "CONNECTED":
                print(f"Hardware adapter reconnected! Status: {core.physical_adapter.status.value}")
                print(f"Last ACKed: {core.physical_adapter.last_acked_command_id}")
                break
            send_demo_traffic(client) # Keep traffic fresh while waiting
            time.sleep(1)
            
        print("\nWP16.6 Complete.\n")

if __name__ == "__main__":
    run_probe()
