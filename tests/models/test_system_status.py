"""
Unit tests for SystemStatus contract model.
"""

from models import SystemStatus, SystemMode, Status


def test_system_status_validation():
    """10. Test SystemStatus initialization and defaults."""
    sys_status = SystemStatus(
        timestamp=50.0,
        mode=SystemMode.LOCAL,
        internet=Status.OFFLINE,
        camera=Status.ONLINE,
        vision=Status.ONLINE,
        decision_engine=Status.ONLINE,
        safety=Status.ONLINE,
        controller=Status.ONLINE,
    )
    assert sys_status.timestamp == 50.0
    assert sys_status.mode == SystemMode.LOCAL
    assert sys_status.internet == Status.OFFLINE
    assert sys_status.camera == Status.ONLINE
    assert sys_status.vision == Status.ONLINE
    assert sys_status.decision_engine == Status.ONLINE
    assert sys_status.safety == Status.ONLINE
    assert sys_status.controller == Status.ONLINE
