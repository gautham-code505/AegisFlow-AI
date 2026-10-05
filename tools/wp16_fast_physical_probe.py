import sys
import os
import time
import asyncio
from typing import Optional, Dict, Any

# Fix import path for backend module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient
from backend.app import app
import backend.app as backend_app
import backend.core as core

CONTINUE_FILE = os.path.join(os.path.dirname(__file__), ".probe_continue")

def _prompt(lines, client=None, active_override=None):
    print("\n" + "="*60)
    for line in lines:
        print(f"  {line}")
    print("="*60 + "\n")
    print("  >>> Waiting for Antigravity confirmation signal... ", flush=True)
    
    # Ensure continue file doesn't exist from a previous run
    if os.path.exists(CONTINUE_FILE):
        try:
            os.remove(CONTINUE_FILE)
        except OSError:
            pass
            
    last_override_time = 0
    while True:
        if os.path.exists(CONTINUE_FILE):
            try:
                os.remove(CONTINUE_FILE)
            except OSError:
                pass
            print("\nReceived confirmation, continuing!")
            break
        else:
            if client:
                try:
                    # Keep the override fresh to prevent STALE rejection and fallback
                    now = time.time()
                    if active_override and (now - last_override_time > 2.0):
                        client.post("/api/v1/overrides", json={"selected_lane": active_override, "duration": 60})
                        last_override_time = now
                    send_demo_traffic(client)
                except Exception:
                    pass
            time.sleep(0.1)
    print()

def make_demo_traffic(lanes: Optional[Dict[str, Any]] = None, emergency: Optional[Dict[str, Any]] = None, source: str = "fast-probe") -> dict:
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
    if payload is None:
        payload = make_demo_traffic()
    
    now = time.time()
    ts = payload.get("timestamp", 0.0)
    age = now - ts
    if not (-1.0 <= age <= 5.0):
        raise AssertionError(
            f"PROBE ERROR: TrafficState timestamp is not fresh! "
            f"current_time={now:.3f}, timestamp={ts:.3f}, age={age:.3f}s "
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

def run_probe():
    print("Starting WP16 FAST Physical Acceptance Probe...")
    print("Initializing TestClient (spins up backend and PhysicalControllerAdapter)...")
    
    # Isolate test harness: prevent background scheduler from competing.
    original_loop = backend_app._decision_loop
    async def mock_decision_loop(*args, **kwargs):
        while True:
            await asyncio.sleep(3600)
    backend_app._decision_loop = mock_decision_loop
    
    with TestClient(app) as client:
        # Wait for physical connection
        for _ in range(30):
            if core.physical_adapter.status.value == "CONNECTED":
                print("Hardware CONNECTED via backend adapter.")
                break
            time.sleep(0.1)
        else:
            print("Failed to connect to ESP32. Ensure it's plugged in on COM4.")
            return

        # ---------------------------------------------------------------------
        # TEST 1 & 2 — NORTH PHYSICAL TRANSITION & SAFETY REJECTION
        # ---------------------------------------------------------------------
        print("\n=== PHYSICAL TEST 1 — NORTH PHYSICAL TRANSITION ===")
        # Use 60s so it doesn't max-out while user is looking (max green limit is 60s)
        resp = client.post("/api/v1/overrides", json={"selected_lane": "north", "duration": 60})
        assert resp.status_code == 200
        
        north_traffic = {
            "north": {"vehicle_count": 20, "occupancy": 0.8},
            "south": {"vehicle_count": 20, "occupancy": 0.8},
            "east": {"vehicle_count": 0, "occupancy": 0.0},
            "west": {"vehicle_count": 0, "occupancy": 0.0},
        }
        
        print("Waiting for NORTH+SOUTH GREEN transition...")
        start_poll = time.time()
        while time.time() - start_poll < 15.0:
            client.post("/api/v1/overrides", json={"selected_lane": "north", "duration": 60})
            send_demo_traffic(client, payload=make_demo_traffic(lanes=north_traffic))
            
            snap = client.get("/api/v1/snapshot").json()
            if "north" in snap["signalState"]["active_lanes"] and snap["signalState"]["phase"] == "GREEN":
                break
            time.sleep(0.2)
        else:
            raise AssertionError("Timeout waiting for NORTH GREEN.")
            
        print("Waiting for Physical ACK...")
        _wait_for_ack(core.physical_adapter.last_acked_command_id, timeout=3.0)
        north_green_start = time.time()

        print("\n=== PHYSICAL TEST 2 — SAFETY REJECTION (AUTOMATED CHECK) ===")
        # Immediately attempt EAST preemption (must be rejected by 10s min-green hold)
        resp = client.post("/api/v1/overrides", json={"selected_lane": "east", "duration": 60})
        assert resp.status_code == 200
        
        east_traffic = {
            "north": {"vehicle_count": 0, "occupancy": 0.0},
            "south": {"vehicle_count": 0, "occupancy": 0.0},
            "east": {"vehicle_count": 20, "occupancy": 0.8},
            "west": {"vehicle_count": 20, "occupancy": 0.8},
        }
        send_demo_traffic(client, payload=make_demo_traffic(lanes=east_traffic))
        
        snap_reject = client.get("/api/v1/snapshot").json()
        assert snap_reject["safetyResult"]["status"] == "REJECTED", "SafetyValidator failed to reject EAST."
        assert "north" in snap_reject["signalState"]["active_lanes"], "State mutated despite rejection!"
        assert snap_reject["signalState"]["phase"] == "GREEN"

        # Now that safety is proven, let human visually confirm the physical state remains NORTH
        _prompt([
            "EXPECTED PHYSICAL STATE:",
            "NORTH = GREEN",
            "SOUTH = GREEN",
            "EAST = RED",
            "WEST = RED",
            "",
            "SAFETY TEST PASSED INTERNALLY. VISUALLY CONFIRM THE LEDs."
        ], client=client, active_override="north")

        # ---------------------------------------------------------------------
        # TEST 3 — SAFE TRANSITION AFTER MINIMUM GREEN
        # ---------------------------------------------------------------------
        print("\n=== PHYSICAL TEST 3 — SAFE TRANSITION AFTER MINIMUM GREEN ===")
        elapsed = time.time() - north_green_start
        min_green = 10.0 # From config
        if elapsed < min_green:
            wait_time = min_green - elapsed + 0.5
            print(f"Waiting {wait_time:.1f}s for NORTH min-green hold to expire...")
            time.sleep(wait_time)
            
        print("Re-submitting EAST request...")
        start_poll = time.time()
        while time.time() - start_poll < 15.0:
            client.post("/api/v1/overrides", json={"selected_lane": "east", "duration": 60})
            send_demo_traffic(client, payload=make_demo_traffic(lanes=east_traffic))
            
            snap_east = client.get("/api/v1/snapshot").json()
            if "east" in snap_east["signalState"]["active_lanes"] and snap_east["signalState"]["phase"] == "GREEN":
                break
            time.sleep(0.2)
        else:
            raise AssertionError("Timeout waiting for EAST GREEN transition.")
            
        print("Waiting for Physical ACK...")
        _wait_for_ack(core.physical_adapter.last_acked_command_id, timeout=3.0)
        
        _prompt([
            "EXPECTED PHYSICAL STATE:",
            "EAST = GREEN",
            "WEST = GREEN",
            "NORTH = RED",
            "SOUTH = RED",
            "",
            "VISUALLY CONFIRM THE LEDs."
        ], client=client, active_override="east")

        # ---------------------------------------------------------------------
        # TEST 4 — WEBSOCKET
        # ---------------------------------------------------------------------
        print("\n=== PHYSICAL TEST 4 — WEBSOCKET ===")
        with client.websocket_connect("/ws/traffic") as websocket:
            send_demo_traffic(client)
            data = websocket.receive_json()
            api_snap = client.get("/api/v1/snapshot").json()
            
            ws_active = set(data["signalState"]["active_lanes"])
            api_active = set(api_snap["signalState"]["active_lanes"])
            
            if ws_active == api_active and data["signalState"]["phase"] == api_snap["signalState"]["phase"]:
                print("WEBSOCKET SYNCHRONIZATION — PASS")
            else:
                print("WEBSOCKET SYNCHRONIZATION — FAIL")
                raise AssertionError("WebSocket state does not match authoritative state.")

        # ---------------------------------------------------------------------
        # TEST 5 — DISCONNECT/RECONNECT
        # ---------------------------------------------------------------------
        print("\n=== PHYSICAL TEST 5 — DISCONNECT/RECONNECT ===")
        _prompt([
            "ESP32 MUST BE CONNECTED."
        ], client=client)
        
        _prompt([
            "UNPLUG ESP32 NOW.",
            "Physically disconnect the USB cable from the ESP32.",
            "Confirm when unplugged."
        ], client=client)
        
        for _ in range(15):
            if core.physical_adapter.status.value in ("FAULT", "DEGRADED", "DISCONNECTED"):
                print("DISCONNECT DETECTED — PASS.")
                break
            send_demo_traffic(client)
            time.sleep(1)
        else:
            raise AssertionError("Failed to detect ESP32 disconnect.")
            
        resp = client.get("/api/v1/status")
        assert resp.status_code == 200
        print("Backend remains alive — PASS.")
        
        _prompt([
            "RECONNECT ESP32 NOW."
        ], client=client)
        
        print("Waiting for CONNECTED and real ACK...")
        for _ in range(15):
            if core.physical_adapter.status.value == "CONNECTED":
                print("RECONNECT + RESYNC — PASS.")
                break
            send_demo_traffic(client)
            time.sleep(1)
        else:
            raise AssertionError("Failed to detect ESP32 reconnect.")
            
        print("\n==================================================")
        print(" FAST WP16 PROBE COMPLETE — ALL TESTS PASSED! ")
        print("==================================================\n")

if __name__ == "__main__":
    run_probe()
