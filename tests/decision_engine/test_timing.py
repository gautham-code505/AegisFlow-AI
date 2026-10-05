import pytest
import time
from models import TrafficState, LaneState, Lane, EmergencyState
from decision_engine.timing import calculate_green_time
from decision_engine.config import DecisionEngineConfig
from decision_engine.engine import DecisionEngine

@pytest.fixture
def base_config():
    return DecisionEngineConfig()

def create_mock_state(has_tracking=False, **lane_kwargs):
    lanes = {
        Lane.NORTH: LaneState(),
        Lane.SOUTH: LaneState(),
        Lane.EAST: LaneState(),
        Lane.WEST: LaneState()
    }
    
    for lane, kwargs in lane_kwargs.items():
        if isinstance(lane, str):
            lane = Lane(lane)
        lanes[lane] = LaneState(**kwargs)
        
    return TrafficState(
        timestamp=time.time(),
        has_tracking_data=has_tracking,
        lanes=lanes
    )

def test_timing_tracking_unavailable_legacy_behavior(base_config):
    # When tracking is unavailable, vehicle_count = 15 -> norm = 0.5
    # occupancy = 0.5
    # demand_factor = (0.5 + 0.5) / 2 = 0.5
    # duration = 10 + (45 - 10) * 0.5 = 27.5 -> 28
    state = create_mock_state(has_tracking=False)
    lane_state = LaneState(vehicle_count=15, occupancy=0.5)
    
    duration = calculate_green_time(lane_state, base_config, state)
    
    assert duration == 28
    
    # Also test backward compatibility (caller does not provide state)
    duration_legacy = calculate_green_time(lane_state, base_config)
    assert duration_legacy == 28

def test_timing_tracking_available_queued_zero(base_config):
    # Tracking available, queued = 0 -> norm = 0
    # occupancy = 0.5
    # demand_factor = (0.5 + 0) / 2 = 0.25
    # duration = 10 + (35 * 0.25) = 18.75 -> 19
    state = create_mock_state(has_tracking=True)
    lane_state = LaneState(vehicle_count=30, queued_vehicle_count=0, occupancy=0.5)
    
    duration = calculate_green_time(lane_state, base_config, state)
    
    assert duration == 19

def test_timing_tracking_available_nonzero_queue(base_config):
    # Tracking available, queued = 7.5 (max is 15) -> norm = 0.5
    # occupancy = 0.5
    # demand_factor = (0.5 + 0.5) / 2 = 0.5
    # duration = 28
    state = create_mock_state(has_tracking=True)
    lane_state = LaneState(vehicle_count=10, queued_vehicle_count=7, occupancy=0.5)
    
    # norm = 7 / 15 = 0.466
    # demand = (0.5 + 0.466) / 2 = 0.4833
    # dur = 10 + 35 * 0.4833 = 26.9 -> 27
    duration = calculate_green_time(lane_state, base_config, state)
    
    assert duration == 27

def test_timing_high_occupancy_zero_queue(base_config):
    # Tracking available, queued = 0 -> norm = 0
    # occupancy = 1.0
    # demand = (1.0 + 0) / 2 = 0.5
    # dur = 28
    state = create_mock_state(has_tracking=True)
    lane_state = LaneState(vehicle_count=30, queued_vehicle_count=0, occupancy=1.0)
    
    duration = calculate_green_time(lane_state, base_config, state)
    assert duration == 28

def test_timing_maximum_queue_normalization(base_config):
    # Queue is 30 (max is 15) -> norm = 1.0
    # occupancy = 1.0
    # demand = 1.0
    # dur = 45
    state = create_mock_state(has_tracking=True)
    lane_state = LaneState(queued_vehicle_count=30, occupancy=1.0)
    
    duration = calculate_green_time(lane_state, base_config, state)
    assert duration == 45

def test_timing_duration_never_below_min(base_config):
    state = create_mock_state(has_tracking=True)
    # Zero traffic -> demand = 0 -> duration should be MIN_GREEN_TIME
    lane_state = LaneState(queued_vehicle_count=0, occupancy=0.0)
    
    duration = calculate_green_time(lane_state, base_config, state)
    assert duration == base_config.MIN_GREEN_TIME

def test_timing_duration_never_above_max(base_config):
    state = create_mock_state(has_tracking=True)
    # Huge traffic -> demand = 1.0 -> duration should be MAX_GREEN_TIME
    lane_state = LaneState(queued_vehicle_count=100, occupancy=1.0)
    
    duration = calculate_green_time(lane_state, base_config, state)
    assert duration == base_config.MAX_GREEN_TIME

def test_timing_emergency_decision_receives_valid_duration(base_config):
    state = create_mock_state(
        has_tracking=True,
        north={"queued_vehicle_count": 0, "occupancy": 0.0}
    )
    state.emergency = EmergencyState(detected=True, lane=Lane.NORTH, vehicle_type="FIRE")
    
    engine = DecisionEngine(base_config)
    decision = engine.decide(state)
    
    assert decision.selected_lane == Lane.NORTH
    assert decision.priority.value == "EMERGENCY"
    # Should receive min green since no other demand
    assert decision.duration == base_config.MIN_GREEN_TIME

def test_timing_starvation_decision_receives_valid_duration(base_config):
    state = create_mock_state(
        has_tracking=True,
        north={"queued_vehicle_count": 15, "occupancy": 1.0}, # high demand
        south={"queued_vehicle_count": 0, "occupancy": 0.0}   # low demand but starving
    )
    
    engine = DecisionEngine(base_config)
    # Force south to be starving
    engine.consecutive_skips["south"] = 6
    
    decision = engine.decide(state)
    
    assert decision.selected_lane == Lane.SOUTH
    # Because south was selected and has no demand, duration is MIN_GREEN_TIME
    assert decision.duration == base_config.MIN_GREEN_TIME
