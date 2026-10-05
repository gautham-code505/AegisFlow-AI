"""
Tests for SystemStatus REST endpoint GET /api/v1/status.
"""

from fastapi.testclient import TestClient
from backend.app import app


def test_health_status_endpoint():
    """Verify GET /api/v1/status returns accurate SystemStatus JSON."""
    from backend.core import state_store
    from models import SystemStatus, SystemMode, Status, SourceType, VisionStatus
    import time
    
    state_store.set_system_status(SystemStatus(
        timestamp=time.time(),
        mode=SystemMode.LOCAL,
        internet=Status.OFFLINE,
        camera=SourceType.NO_INPUT,
        vision=VisionStatus.STOPPED,
        decision_engine=Status.ONLINE,
        safety=Status.ONLINE,
        controller=Status.ONLINE,
    ))

    client = TestClient(app)
    response = client.get("/api/v1/status")
    assert response.status_code == 200

    data = response.json()
    assert data["mode"] == "LOCAL"
    assert data["decision_engine"] == "ONLINE"
    assert data["safety"] == "ONLINE"
    assert data["controller"] == "ONLINE"
    assert data["vision"] == "STOPPED"
    assert data["camera"] == "NO INPUT"
    assert data["internet"] == "OFFLINE"
