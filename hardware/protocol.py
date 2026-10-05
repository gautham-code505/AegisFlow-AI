"""
AegisFlow AI - Hardware Protocol
Deterministic JSON-line protocol to serialize SignalState for the physical ESP32 actuator.
"""

import json
import logging
from typing import Optional, Dict, Any
from pydantic import BaseModel, ValidationError, Field
from models import SignalState, SignalPhase, Lane

logger = logging.getLogger(__name__)

PROTOCOL_VERSION = 1

class ProtocolMessage(BaseModel):
    version: int = Field(default=PROTOCOL_VERSION)
    type: str
    command_id: Optional[int] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    
class HardwareProtocol:
    """Serializes and deserializes messages between the backend and hardware."""
    
    @classmethod
    def serialize_signal_state(cls, state: SignalState, command_id: int) -> str:
        """
        Converts a canonical SignalState into a deterministic JSON-line payload.
        """
        lanes_state = {
            "north": state.north.value,
            "south": state.south.value,
            "east": state.east.value,
            "west": state.west.value
        }
            
        message = ProtocolMessage(
            version=PROTOCOL_VERSION,
            type="SET_SIGNAL_STATE",
            command_id=command_id,
            payload={
                "lanes": lanes_state,
                "timestamp": state.timestamp
            }
        )
        # Ensure we always end with a newline for framing
        return message.model_dump_json() + "\n"
        
    @classmethod
    def serialize_ping(cls) -> str:
        """Creates a PING message to check hardware health."""
        message = ProtocolMessage(
            version=PROTOCOL_VERSION,
            type="PING"
        )
        return message.model_dump_json() + "\n"
        
    @classmethod
    def parse_response(cls, line: str) -> Optional[ProtocolMessage]:
        """
        Parses a JSON line from the hardware into a ProtocolMessage.
        Returns None if malformed, unsupported, or invalid.
        """
        try:
            line = line.strip()
            if not line:
                return None
                
            if not line.startswith('{'):
                # Safely ignore non-JSON serial output (e.g., ESP32 boot logs)
                logger.debug(f"Ignoring non-JSON hardware data: {line}")
                return None
                
            data = json.loads(line)
            msg = ProtocolMessage(**data)
            
            if msg.version != PROTOCOL_VERSION:
                logger.error(f"Unsupported hardware protocol version: {msg.version}")
                return None
                
            return msg
        except json.JSONDecodeError as e:
            logger.error(f"Malformed JSON from hardware: {e}")
            return None
        except ValidationError as e:
            logger.error(f"Invalid hardware message structure: {e}")
            return None
