"""
AegisFlow AI - Central Backend Orchestrator

Coordinates processing pipeline:
Canonical TrafficState -> Decision Engine -> SignalDecision -> SafetyValidator -> VirtualSignalController -> SignalState -> StateStore -> Event -> WebSocketManager broadcast.
"""

import time
import uuid
import logging
from typing import Optional, List
from models import TrafficState, SignalDecision, SignalState, Event, EventSeverity, SystemStatus, Status, SystemMode, Lane, Priority
from safety import SafetyValidator, FallbackController, ValidationStatus, get_compatible_phase_for_lane
from controller import VirtualSignalController
from .state_store import StateStore
from .decision_adapter import DecisionEngineAdapter
from .websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)


class Orchestrator:
    """Central orchestration service coordinating data flow, safety validation, controller execution, and state updates."""

    def __init__(
        self,
        state_store: StateStore,
        decision_adapter: DecisionEngineAdapter,
        websocket_manager: WebSocketManager,
        safety_validator: Optional[SafetyValidator] = None,
        virtual_controller: Optional[VirtualSignalController] = None,
        fallback_controller: Optional[FallbackController] = None,
    ):
        self.state_store = state_store
        self.decision_adapter = decision_adapter
        self.websocket_manager = websocket_manager
        self.safety_validator = safety_validator or SafetyValidator()
        self.virtual_controller = virtual_controller or VirtualSignalController()
        self.fallback_controller = fallback_controller or FallbackController()
        self.active_override: Optional[SignalDecision] = None

    def get_current_signal_state(self, current_time: Optional[float] = None) -> SignalState:
        """
        Returns the dynamically evaluated current signal state based on elapsed time.
        Routes to the fallback controller if the system is in FALLBACK mode, 
        otherwise uses the primary virtual controller.
        """
        now = current_time if current_time is not None else time.time()
        status = self.state_store.get_system_status()
        
        if status.mode == SystemMode.FALLBACK:
            return self.fallback_controller.get_fallback_signal_state(now)
        
        return self.virtual_controller.get_current_signal_state(now)

    async def process_traffic_state(self, state: TrafficState) -> SignalDecision:
        """
        Main orchestration workflow:
        1. Store incoming TrafficState.
        2. Invoke DecisionEngineAdapter.
        3. Determine safe compatible phase group.
        4. Validate proposed decision through SafetyValidator.
        5. Execute decision through VirtualSignalController (or FallbackController if invalid/stale).
        6. Store SignalDecision and SignalState in StateStore.
        7. Record system events.
        8. Broadcast unified snapshot via WebSocket.
        """
        now = time.time()
        logger.info(f"Orchestrator processing TrafficState (timestamp={state.timestamp}, source={state.source})")
        self.state_store.set_traffic_state(state)

        decision: Optional[SignalDecision] = None
        signal_state: Optional[SignalState] = None

        try:
            # 1. Invoke Decision Engine or use Manual Override
            if self.active_override:
                decision = self.active_override
                logger.info(f"Applying manual override decision: {decision.selected_lane}")
            else:
                decision = self.decision_adapter.decide(state)
                
            self.state_store.set_decision(decision)

            # Update system status to normal
            current_status = self.state_store.get_system_status()
            self.state_store.set_system_status(
                SystemStatus(
                    timestamp=now,
                    mode=SystemMode.LOCAL,
                    internet=current_status.internet,
                    camera=current_status.camera,
                    vision=current_status.vision,
                    decision_engine=Status.ONLINE,
                    safety=Status.ONLINE,
                    controller=Status.ONLINE,
                )
            )

        except Exception as exc:
            logger.error(f"Decision Engine invocation failed: {exc}", exc_info=True)
            error_event = Event(
                event_id=f"ev-err-{uuid.uuid4().hex[:8]}",
                timestamp=now,
                type="SYSTEM_ERROR",
                severity=EventSeverity.ERROR,
                message=f"Decision engine failure: {str(exc)}. Switching to safe fallback mode.",
            )
            self.state_store.add_event(error_event)

            # Update system status to reflect error & fallback
            current_status = self.state_store.get_system_status()
            self.state_store.set_system_status(
                SystemStatus(
                    timestamp=now,
                    mode=SystemMode.FALLBACK,
                    internet=current_status.internet,
                    camera=current_status.camera,
                    vision=current_status.vision,
                    decision_engine=Status.ERROR,
                    safety=Status.ONLINE,
                    controller=Status.ONLINE,
                )
            )

            # Trigger Fallback Controller execution
            signal_state = self.fallback_controller.get_fallback_signal_state(now)
            self.state_store.set_signal_state(signal_state)
            await self.websocket_manager.broadcast_snapshot(
                traffic_state=self.state_store.get_traffic_state(),
                signal_decision=None,
                signal_state=signal_state,
                systemStatus=self.state_store.get_system_status(),
                events=self.state_store.get_events(),
            )
            raise exc

        # 2. Map primary decision lane to compatible safe phase group
        target_lanes: List[Lane]
        if decision.priority in (Priority.EMERGENCY, Priority.MANUAL):
            # Dedicated approach for emergency or manual override
            target_lanes = [decision.selected_lane]
        else:
            # Map to compatible concurrent corridor group (e.g. NORTH+SOUTH or EAST+WEST)
            phase_group = get_compatible_phase_for_lane(decision.selected_lane)
            target_lanes = sorted(list(phase_group.green_lanes), key=lambda l: l.value)

        # 3. Perform Safety Validation
        current_signal = self.state_store.get_signal_state()
        val_result = self.safety_validator.validate(
            current_signal_state=current_signal,
            proposed_decision=decision,
            traffic_state=state,
            current_time=now,
        )

        # 4. Virtual Signal Controller Execution based on Validation Result
        if val_result.status == ValidationStatus.APPROVED and decision:
            signal_state = self.virtual_controller.execute_decision(
                target_lane=target_lanes,
                duration=decision.duration,
                current_time=now,
            )
            self.state_store.set_signal_state(signal_state)

            lane_labels = "+".join([l.value.upper() for l in target_lanes])
            dec_event = Event(
                event_id=f"ev-dec-{uuid.uuid4().hex[:8]}",
                timestamp=now,
                type="SIGNAL_DECISION",
                severity=EventSeverity.INFO if decision.priority != Priority.EMERGENCY else EventSeverity.WARNING,
                message=f"Safety Validator approved concurrent phase [{lane_labels}] ({decision.duration}s)",
            )
            self.state_store.add_event(dec_event)

        elif val_result.status == ValidationStatus.FALLBACK:
            logger.warning("Safety Validation triggered FALLBACK mode.")
            
            current_status = self.state_store.get_system_status()
            current_status.mode = SystemMode.FALLBACK
            self.state_store.set_system_status(current_status)

            signal_state = self.fallback_controller.get_fallback_signal_state(now)
            self.state_store.set_signal_state(signal_state)

            fb_event = Event(
                event_id=f"ev-fb-{uuid.uuid4().hex[:8]}",
                timestamp=now,
                type="FALLBACK_ACTIVATED",
                severity=EventSeverity.WARNING,
                message=f"Safe fallback mode activated: {', '.join(val_result.reasons)}",
            )
            self.state_store.add_event(fb_event)

        else:
            # ValidationStatus.REJECTED
            logger.warning(f"Safety Validator REJECTED proposed decision: {val_result.reasons}")
            rej_event = Event(
                event_id=f"ev-rej-{uuid.uuid4().hex[:8]}",
                timestamp=now,
                type="SYSTEM_WARNING",
                severity=EventSeverity.WARNING,
                message=f"Proposed decision rejected by Safety Validator: {', '.join(val_result.reasons)}",
            )
            self.state_store.add_event(rej_event)

            # Advance current signal controller state safely
            signal_state = self.virtual_controller.advance_time(now)
            self.state_store.set_signal_state(signal_state)

        # 5. Broadcast updated unified snapshot via WebSocket
        await self.websocket_manager.broadcast_snapshot(
            traffic_state=self.state_store.get_traffic_state(),
            signal_decision=self.state_store.get_decision(),
            signal_state=self.state_store.get_signal_state(),
            system_status=self.state_store.get_system_status(),
            events=self.state_store.get_events(),
        )

        return decision
