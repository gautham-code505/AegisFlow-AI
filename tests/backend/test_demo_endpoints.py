"""
Tests for demo endpoints POST /api/v1/demo/{scenario} and POST /api/v1/demo/traffic.
"""

import time
from fastapi.testclient import TestClient
from backend.app import app


def test_demo_balanced_scenario():
    """Verify POST /api/v1/demo/balanced executes and invokes real engine."""
    client = TestClient(app)
    response = client.post("/api/v1/demo/balanced")
    assert response.status_code == 200
    data = response.json()
    assert "decision_id" in data
    assert "selected_lane" in data
    assert data["duration"] > 0


def test_demo_heavy_north_scenario():
    """Verify POST /api/v1/demo/heavy-north selects NORTH approach."""
    client = TestClient(app)
    response = client.post("/api/v1/demo/heavy-north")
    assert response.status_code == 200
    data = response.json()
    assert data["selected_lane"] == "north"


def test_demo_heavy_east_scenario():
    """Verify POST /api/v1/demo/heavy-east selects EAST approach."""
    client = TestClient(app)
    response = client.post("/api/v1/demo/heavy-east")
    assert response.status_code == 200
    data = response.json()
    assert data["selected_lane"] == "east"


def test_demo_emergency_scenario():
    """Verify POST /api/v1/demo/emergency-east selects EAST with EMERGENCY priority."""
    client = TestClient(app)
    response = client.post("/api/v1/demo/emergency-east")
    assert response.status_code == 200
    data = response.json()
    assert data["selected_lane"] == "east"
    assert data["priority"] == "EMERGENCY"


def test_demo_invalid_scenario():
    """Verify invalid demo scenario returns 400."""
    client = TestClient(app)
    response = client.post("/api/v1/demo/unknown-scenario")
    assert response.status_code == 400
    assert "Unknown demo scenario" in response.json()["detail"]


def test_demo_custom_traffic_payload():
    """Verify POST /api/v1/demo/traffic accepts custom fresh TrafficState JSON."""
    client = TestClient(app)
    payload = {
        "timestamp": time.time(),
        "source": "custom-payload-test",
        "lanes": {
            "north": {"vehicle_count": 2, "occupancy": 0.1},
            "south": {"vehicle_count": 25, "occupancy": 0.9},
            "east": {"vehicle_count": 1, "occupancy": 0.05},
            "west": {"vehicle_count": 0, "occupancy": 0.0},
        },
        "emergency": {"detected": False, "lane": None},
    }
    response = client.post("/api/v1/demo/traffic", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["selected_lane"] == "south"


def test_demo_simulated_emergency_endpoints():
    """Verify POST /api/v1/demo/emergency/{lane} overrides traffic states, and clear removes it."""
    client = TestClient(app)
    
    # 1. Clear any existing state
    client.post("/api/v1/demo/emergency/clear")
    
    # 2. Activate simulated emergency on EAST
    response = client.post("/api/v1/demo/emergency/east")
    assert response.status_code == 200
    assert "Simulated emergency activated" in response.json()["message"]
    
    # 3. Submit normal traffic (e.g. heavy north)
    payload = {
        "timestamp": time.time(),
        "source": "sim-emergency-test",
        "lanes": {
            "north": {"vehicle_count": 25, "occupancy": 0.9},
            "south": {"vehicle_count": 2, "occupancy": 0.1},
            "east": {"vehicle_count": 0, "occupancy": 0.0},
            "west": {"vehicle_count": 0, "occupancy": 0.0},
        },
        "emergency": {"detected": False, "lane": None},
    }
    # Because of simulated emergency on EAST, the decision must be EAST and priority EMERGENCY
    response = client.post("/api/v1/demo/traffic", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["selected_lane"] == "east"
    assert data["priority"] == "EMERGENCY"
    
    # 4. Clear the simulated emergency
    response = client.post("/api/v1/demo/emergency/clear")
    assert response.status_code == 200
    
    # 5. Submit the same traffic again, it should return to normal priority (or high due to starvation)
    payload["timestamp"] = time.time()
    response = client.post("/api/v1/demo/traffic", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["selected_lane"] in ["north", "south", "east", "west"]
    assert data["priority"] != "emergency"


def test_demo_simulated_emergency_invalid_lane():
    """Verify invalid lane on simulated emergency returns 400."""
    client = TestClient(app)
    response = client.post("/api/v1/demo/emergency/unknown")
    assert response.status_code == 400
    assert "Invalid lane" in response.json()["detail"]
