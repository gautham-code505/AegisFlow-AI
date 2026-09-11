"""
AegisFlow AI - Central Backend Orchestrator

Coordinates processing pipeline:
Canonical TrafficState -> Decision Engine -> SignalDecision -> SafetyValidator -> VirtualSignalController -> SignalState -> StateStore -> Event -> WebSocketManager broadcast.
"""

import time
import uuid
import logging
from typing import Optional, List
from models import TrafficState, SignalDecision, SignalState, Event, EventSeverity, EventCategory, SystemStatus, Status, SystemMode, Lane, Priority, SignalPhase, ServiceMeasurement
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
        self._last_signal_state: Optional[SignalState] = None
        self._active_measurement: Optional[ServiceMeasurement] = None

    def _update_signal_state(self, new_state: SignalState, current_time: float) -> SignalState:
        old_state = self._last_signal_state
        self._check_and_record_measurements(old_state, new_state, current_time)
        
        if not old_state or old_state.phase != new_state.phase:
            lanes = list(new_state.active_lanes)
            lane_str = "+".join([l.value.upper() for l in lanes]) if lanes else "ALL"
            if old_state and old_state.phase == SignalPhase.GREEN and new_state.phase != SignalPhase.GREEN:
                msg = f"{lane_str} GREEN END -> {new_state.phase.value} START"
            else:
                msg = f"{lane_str} {new_state.phase.value} START"
                
            sig_evt = Event(
                event_id=f"ev-sig-{uuid.uuid4().hex[:8]}",
                timestamp=current_time,
                type="SIGNAL_TRANSITION",
                category=EventCategory.SIGNAL,
                severity=EventSeverity.INFO,
                message=msg,
                source="VirtualSignalController",
                target_lanes=lanes
            )
            self.state_store.add_event(sig_evt)
            
        self._last_signal_state = new_state
        self.state_store.set_signal_state(new_state)
        return new_state

    def _check_and_record_measurements(self, old_state: Optional[SignalState], new_state: SignalState, current_time: float) -> None:
        old_phase = old_state.phase if old_state else SignalPhase.ALL_RED
            
        # Transition: NOT GREEN -> GREEN (Green Start)
        if old_phase != SignalPhase.GREEN and new_state.phase == SignalPhase.GREEN:
            t_state = self.state_store.get_traffic_state()
            decision = self.state_store.get_decision()
            
            queue_before = None
            wait_avg_before = None
            wait_max_before = None
            has_tracking = False
            
            if t_state and t_state.has_tracking_data:
                has_tracking = True
                queue_before = 0
                wait_avg_before = 0.0
                wait_max_before = 0.0
                waits = []
                for lane in new_state.active_lanes:
                    ls = t_state.lanes.get(lane)
                    if ls:
                        queue_before += ls.queued_vehicle_count
                        waits.append(ls.observed_average_wait)
                        if ls.observed_max_wait > wait_max_before:
                            wait_max_before = ls.observed_max_wait
                if waits:
                    wait_avg_before = sum(waits) / len(waits)
                
            priority = Priority.NORMAL
            reason = None
            dec_time = None
            if decision:
                priority = decision.priority
                reason = " | ".join(decision.reasons) if decision.reasons else "Adaptive"
                dec_time = decision.timestamp
                
            self._active_measurement = ServiceMeasurement(
                measurement_id=f"meas-{uuid.uuid4().hex[:8]}",
                target_lanes=list(new_state.active_lanes),
                start_timestamp=current_time,
                queue_before=queue_before,
                wait_avg_before=wait_avg_before,
                wait_max_before=wait_max_before,
                has_tracking_data=has_tracking,
                priority_type=priority,
                decision_reason=reason,
                decision_timestamp=dec_time
            )
            
            msg = "Service interval started" if has_tracking else "Measurement unavailable (no tracking data)"
            meas_evt = Event(
                event_id=f"ev-meas-{uuid.uuid4().hex[:8]}",
                timestamp=current_time,
                type="MEASUREMENT_STARTED",
                category=EventCategory.MEASUREMENT,
                severity=EventSeverity.INFO if has_tracking else EventSeverity.WARNING,
                message=msg,
                source="Orchestrator",
                target_lanes=list(new_state.active_lanes),
                measurement_id=self._active_measurement.measurement_id,
                decision_id=decision.decision_id if decision else None
            )
            self.state_store.add_event(meas_evt)

        # Transition: GREEN -> NOT GREEN (Green End)
        elif old_state.phase == SignalPhase.GREEN and new_state.phase != SignalPhase.GREEN:
            if self._active_measurement:
                t_state = self.state_store.get_traffic_state()
                queue_after = None
                wait_avg_after = None
                wait_max_after = None
                
                if t_state and self._active_measurement.has_tracking_data and t_state.has_tracking_data:
                    queue_after = 0
                    wait_avg_after = 0.0
                    wait_max_after = 0.0
                    waits = []
                    for lane in self._active_measurement.target_lanes:
                        ls = t_state.lanes.get(lane)
                        if ls:
                            queue_after += ls.queued_vehicle_count
                            waits.append(ls.observed_average_wait)
                            if ls.observed_max_wait > wait_max_after:
                                wait_max_after = ls.observed_max_wait
                    if waits:
                        wait_avg_after = sum(waits) / len(waits)
                
                self._active_measurement.end_timestamp = current_time
                self._active_measurement.green_duration = round(current_time - self._active_measurement.start_timestamp, 3)
                self._active_measurement.queue_after = queue_after
                self._active_measurement.wait_avg_after = wait_avg_after
                self._active_measurement.wait_max_after = wait_max_after
                
                self.state_store.add_measurement(self._active_measurement)
                
                msg = f"Service interval completed. Queue: {self._active_measurement.queue_before} -> {queue_after}" if self._active_measurement.has_tracking_data else "Measurement completed (unavailable)"
                meas_evt = Event(
                    event_id=f"ev-meas-{uuid.uuid4().hex[:8]}",
                    timestamp=current_time,
                    type="MEASUREMENT_COMPLETED",
                    category=EventCategory.MEASUREMENT,
                    severity=EventSeverity.INFO,
                    message=msg,
                    source="Orchestrator",
                    target_lanes=self._active_measurement.target_lanes,
                    measurement_id=self._active_measurement.measurement_id
                )
                self.state_store.add_event(meas_evt)
                
                self._active_measurement = None

    def get_current_signal_state(self, current_time: Optional[float] = None) -> SignalState:
        """
        Returns the dynamically evaluated current signal state based on elapsed time.
        Routes to the fallback controller if the system is in FALLBACK mode, 
        otherwise uses the primary virtual controller.
        """
        now = current_time if current_time is not None else time.time()
        status = self.state_store.get_system_status()
        
        if status.mode == SystemMode.FALLBACK:
            new_state = self.fallback_controller.get_fallback_signal_state(now)
        else:
            new_state = self.virtual_controller.get_current_signal_state(now)
            
        return self._update_signal_state(new_state, now)

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
            
            if decision:
                reason_str = " | ".join(decision.reasons) if decision.reasons else "Adaptive"
                dec_event = Event(
                    event_id=f"ev-dec-{uuid.uuid4().hex[:8]}",
                    timestamp=now,
                    type="SIGNAL_DECISION",
                    category=EventCategory.DECISION,
                    severity=EventSeverity.WARNING if decision.priority in (Priority.EMERGENCY, Priority.MANUAL) else EventSeverity.INFO,
                    message=f"{decision.selected_lane.value.upper()} selected ({decision.priority.value}). Reason: {reason_str}",
                    source="DecisionEngine",
                    target_lanes=[decision.selected_lane],
                    decision_id=decision.decision_id
                )
                self.state_store.add_event(dec_event)

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
                category=EventCategory.ERROR,
                severity=EventSeverity.CRITICAL,
                message=f"Decision engine failure: {str(exc)}. Switching to safe fallback mode.",
                source="Orchestrator"
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
            self._update_signal_state(signal_state, now)
            await self.websocket_manager.broadcast_snapshot(
                traffic_state=self.state_store.get_traffic_state(),
                signal_decision=None,
                signal_state=signal_state,
                system_status=self.state_store.get_system_status(),
                events=self.state_store.get_events(),
                measurements=self.state_store.get_measurements(),
                approach_statuses=self.state_store.get_all_approach_statuses(),
                safety_result=self.state_store.get_safety_result(),
                analytics=self.state_store.get_analytics(),
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
            target_lanes=target_lanes,
        )

        # Store safety result for frontend display
        self.state_store.set_safety_result({
            "status": val_result.status.value if hasattr(val_result.status, 'value') else str(val_result.status),
            "approved": val_result.approved,
            "reasons": val_result.reasons,
            "proposed_lane": val_result.proposed_lane.value if val_result.proposed_lane else None,
            "proposed_duration": val_result.proposed_duration,
        })

        # Safety Event
        is_approved = val_result.status == ValidationStatus.APPROVED
        safe_msg = f"Permitted: {', '.join(val_result.reasons)}" if is_approved else f"Rejected: {', '.join(val_result.reasons)}"
        safe_evt = Event(
            event_id=f"ev-safe-{uuid.uuid4().hex[:8]}",
            timestamp=now,
            type="SAFETY_VALIDATION",
            category=EventCategory.SAFETY,
            severity=EventSeverity.INFO if is_approved else EventSeverity.WARNING,
            message=safe_msg,
            source="SafetyValidator",
            target_lanes=target_lanes,
            decision_id=decision.decision_id if decision else None
        )
        self.state_store.add_event(safe_evt)

        # 4. Virtual Signal Controller Execution based on Validation Result
        if is_approved and decision:
            signal_state = self.virtual_controller.execute_decision(
                target_lane=target_lanes,
                duration=decision.duration,
                current_time=now,
            )
            self._update_signal_state(signal_state, now)

        elif val_result.status == ValidationStatus.FALLBACK:
            logger.warning("Safety Validation triggered FALLBACK mode.")
            
            current_status = self.state_store.get_system_status()
            current_status.mode = SystemMode.FALLBACK
            self.state_store.set_system_status(current_status)

            signal_state = self.fallback_controller.get_fallback_signal_state(now)
            self._update_signal_state(signal_state, now)

            fb_event = Event(
                event_id=f"ev-fb-{uuid.uuid4().hex[:8]}",
                timestamp=now,
                type="FALLBACK_ACTIVATED",
                category=EventCategory.SYSTEM,
                severity=EventSeverity.WARNING,
                message=f"Safe fallback mode activated: {', '.join(val_result.reasons)}",
                source="Orchestrator"
            )
            self.state_store.add_event(fb_event)

        else:
            # ValidationStatus.REJECTED
            logger.warning(f"Safety Validator REJECTED proposed decision: {val_result.reasons}")
            
            # Note: We already recorded a SAFETY rejection event above.
            
            # Advance current signal controller state safely
            signal_state = self.virtual_controller.advance_time(now)
            self._update_signal_state(signal_state, now)

        # 5. Broadcast updated unified snapshot via WebSocket
        await self.websocket_manager.broadcast_snapshot(
            traffic_state=self.state_store.get_traffic_state(),
            signal_decision=self.state_store.get_decision(),
            signal_state=self.state_store.get_signal_state(),
            system_status=self.state_store.get_system_status(),
            events=self.state_store.get_events(),
            measurements=self.state_store.get_measurements(),
            approach_detections=self.state_store.get_approach_detections(),
            approach_statuses=self.state_store.get_all_approach_statuses(),
            safety_result=self.state_store.get_safety_result(),
            analytics=self.state_store.get_analytics(),
        )

        return decision
