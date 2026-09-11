import pytest
import time
from models import TrafficState, LaneState, Lane, EmergencyState
from decision_engine.scorer import calculate_lane_scores
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

def test_tracking_unavailable_uses_fallback(base_config):
    """Scenario F, D, E: Fallback mode uses intended signals, tracking modes do not"""
    state = create_mock_state(
        has_tracking=False,
        north={"vehicle_count": 10, "occupancy": 0.5, "queued_vehicle_count": 5},
        south={"vehicle_count": 5, "occupancy": 0.2, "queued_vehicle_count": 5}
    )
    
    scores = calculate_lane_scores(state, {}, {}, base_config)
    
    # North score vehicle component: 10/30 * 0.50 = 0.166...
    assert scores["north"][1]["vehicle_component"] == pytest.approx(10/30 * base_config.FALLBACK_VEHICLE_WEIGHT)
    assert scores["north"][1]["occupancy_component"] == pytest.approx(0.5 * base_config.FALLBACK_OCCUPANCY_WEIGHT)
    assert scores["north"][1]["queue_component"] == 0.0
    assert scores["north"][1]["delay_component"] == 0.0
    assert not scores["north"][1]["used_tracking"]
    
def test_tracking_available_queue_and_delay_are_used(base_config):
    """Scenario D, E: Tracking uses only queue and delay, no raw vehicles or occupancy"""
    state = create_mock_state(
        has_tracking=True,
        north={"vehicle_count": 10, "occupancy": 0.5, "queued_vehicle_count": 6, "observed_average_wait": 30.0},
        south={"vehicle_count": 10, "occupancy": 0.5, "queued_vehicle_count": 3, "observed_average_wait": 10.0}
    )
    
    scores = calculate_lane_scores(state, {}, {}, base_config)
    
    # North queue component: 6 / 15 * 0.6 = 0.24
    # North delay component: 30 / 60 * 0.4 = 0.20
    assert scores["north"][1]["queue_component"] == pytest.approx(0.24)
    assert scores["north"][1]["delay_component"] == pytest.approx(0.20)
    assert scores["north"][1]["vehicle_component"] == 0.0
    assert scores["north"][1]["occupancy_component"] == 0.0
    assert scores["north"][1]["used_tracking"]
    
def test_higher_queue_produces_higher_score(base_config):
    """Scenario A"""
    state = create_mock_state(
        has_tracking=True,
        north={"queued_vehicle_count": 10, "observed_average_wait": 20.0},
        south={"queued_vehicle_count": 5, "observed_average_wait": 20.0}
    )
    scores = calculate_lane_scores(state, {}, {}, base_config)
    
    assert scores["north"][0] > scores["south"][0]

def test_higher_wait_produces_higher_score(base_config):
    """Scenario B"""
    state = create_mock_state(
        has_tracking=True,
        north={"queued_vehicle_count": 5, "observed_average_wait": 50.0},
        south={"queued_vehicle_count": 5, "observed_average_wait": 10.0}
    )
    scores = calculate_lane_scores(state, {}, {}, base_config)
    
    assert scores["north"][0] > scores["south"][0]

def test_observed_wait_can_overcome_moderate_queue_difference(base_config):
    """Scenario C"""
    state = create_mock_state(
        has_tracking=True,
        north={"queued_vehicle_count": 8, "observed_average_wait": 10.0, "vehicle_count": 10},
        south={"queued_vehicle_count": 5, "observed_average_wait": 50.0, "vehicle_count": 10}
    )
    
    scores = calculate_lane_scores(state, {}, {}, base_config)
    
    # North queue: 8/15 * 0.6 = 0.32, delay: 10/60 * 0.4 = 0.066 -> 0.386
    # South queue: 5/15 * 0.6 = 0.20, delay: 50/60 * 0.4 = 0.333 -> 0.533
    assert scores["south"][0] > scores["north"][0]
    
    engine = DecisionEngine(base_config)
    decision = engine.decide(state)
    
    assert decision.selected_lane == Lane.SOUTH
    assert any("due to highest tracked demand" in r for r in decision.reasons)

def test_emergency_behavior_remains_unchanged(base_config):
    """Scenario G"""
    state = create_mock_state(
        has_tracking=True,
        north={"queued_vehicle_count": 10, "observed_average_wait": 30.0, "vehicle_count": 10},
        south={"queued_vehicle_count": 0, "observed_average_wait": 0.0, "vehicle_count": 0}
    )
    state.emergency = EmergencyState(detected=True, lane=Lane.SOUTH, vehicle_type="FIRE")
    
    engine = DecisionEngine(base_config)
    decision = engine.decide(state)
    
    assert decision.selected_lane == Lane.SOUTH
    assert decision.priority.value == "EMERGENCY"

def test_starvation_behavior_remains_unchanged(base_config):
    """Scenario H and I: Starvation overrides but isn't part of normal score"""
    state = create_mock_state(
        has_tracking=True,
        north={"queued_vehicle_count": 10, "observed_average_wait": 30.0, "vehicle_count": 10},
        south={"queued_vehicle_count": 0, "observed_average_wait": 0.0, "vehicle_count": 0}
    )
    
    # South is starving
    waiting_times = {"south": 100.0, "north": 0.0, "east": 0.0, "west": 0.0}
    consecutive_skips = {"south": 6, "north": 0, "east": 0, "west": 0}
    
    # Note: engine calculates scores first, then checks starvation
    scores = calculate_lane_scores(state, waiting_times, consecutive_skips, base_config)
    
    # Scenario I: Starvation is NOT part of the normal score (total_score relies on queue+delay)
    assert "starvation_component" not in scores["south"][1]
    assert scores["south"][0] == 0.0
    
    # Engine will decide to override
    engine = DecisionEngine(base_config)
    engine.waiting_times = waiting_times
    engine.consecutive_skips = consecutive_skips
    engine.last_timestamp = state.timestamp
    engine.last_active_lane = "north"
    
    decision = engine.decide(state)
    assert decision.selected_lane == Lane.SOUTH
    assert decision.priority.value == "HIGH"

def test_deterministic_tie_breaking(base_config):
    """Scenario J"""
    state = create_mock_state(
        has_tracking=True,
        north={"queued_vehicle_count": 5, "observed_average_wait": 10.0},
        east={"queued_vehicle_count": 5, "observed_average_wait": 10.0} # same score
    )
    
    engine = DecisionEngine(base_config)
    decision = engine.decide(state)
    
    # Alphabetical tie break: 'east' < 'north'
    assert decision.selected_lane == Lane.EAST
