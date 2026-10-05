"""
AegisFlow AI - Core Singletons and Shared State
"""

import logging
import asyncio
import json

from .state_store import StateStore
from .frame_store import LatestFrameStore
from .decision_adapter import DecisionEngineAdapter
from .websocket_manager import WebSocketManager
from safety import SafetyValidator, FallbackController
from controller import VirtualSignalController
from .orchestrator import Orchestrator
from vision.adapter import VisionAdapter

logger = logging.getLogger("aegisflow.backend")

# Instantiate core singleton services
state_store = StateStore()
frame_store = LatestFrameStore()

cfg: dict = {}
try:
    with open("vision/config.json", "r", encoding="utf-8") as f:
        cfg = json.load(f)
        state_store.emergency_latch_timeout_seconds = cfg.get("emergency", {}).get("latch_timeout_seconds", 5.0)
except Exception:
    pass

decision_adapter = DecisionEngineAdapter()
ws_manager = WebSocketManager()
safety_validator = SafetyValidator()
virtual_controller = VirtualSignalController()
fallback_controller = FallbackController()

from hardware.adapter import PhysicalControllerAdapter
from hardware.serial_transport import DummySerialTransport, PySerialTransport

# Resolve hardware transport from config — no COM port is hard-coded here.
_hw_cfg = cfg.get("hardware", {})
if _hw_cfg.get("enabled", False):
    _transport = PySerialTransport(
        port=_hw_cfg["port"],
        baud_rate=_hw_cfg.get("baud_rate", 115200),
    )
    _ack_timeout = _hw_cfg.get("ack_timeout", 2.0)
    logger.info(
        f"Hardware transport: PySerialTransport on {_hw_cfg['port']} "
        f"@ {_hw_cfg.get('baud_rate', 115200)} bps"
    )
else:
    _transport = DummySerialTransport()
    _ack_timeout = 2.0
    logger.info("Hardware transport: DummySerialTransport (hardware.enabled=false or config absent)")

physical_adapter = PhysicalControllerAdapter(transport=_transport, ack_timeout=_ack_timeout)

orchestrator = Orchestrator(
    state_store=state_store,
    decision_adapter=decision_adapter,
    websocket_manager=ws_manager,
    safety_validator=safety_validator,
    virtual_controller=virtual_controller,
    fallback_controller=fallback_controller,
    physical_adapter=physical_adapter,
)

vision_adapter = VisionAdapter()

# Global primitives shared across modules
simulated_emergency = None
_decision_event = asyncio.Event()
