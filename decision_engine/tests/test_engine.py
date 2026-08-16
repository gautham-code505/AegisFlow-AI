import unittest
from dataclasses import FrozenInstanceError
import uuid

from decision_engine import (
    DecisionEngine,
    DecisionConfig,
    TrafficState,
    LaneState,
    EmergencyState,
    SignalDecision,
    Priority
)
from decision_engine.validator import parse_boolean

class TestDecisionEngine(unittest.TestCase):
    def setUp(self):
        # Clean config for testing
        self.config = DecisionConfig(
            MIN_GREEN_TIME=10,
            MAX_GREEN_TIME=45,
            STARVATION_THRESHOLD=30.0,  # lower for testing
            MAX_CONSECUTIVE_SKIPS=3,     # lower for testing
            OCCUPANCY_WEIGHT=0.4,
            VEHICLE_WEIGHT=0.3,
            WAITING_WEIGHT=0.1,
            PEDESTRIAN_WEIGHT=0.1,
            STARVATION_WEIGHT=0.1,
            MAX_EXPECTED_VEHICLES=20,
            MAX_EXPECTED_PEDESTRIANS=10
        )
        self.engine = DecisionEngine(config=self.config)

    def test_highest_occupancy_selection(self):
        # North has high occupancy, others have 0
        state = {
            "timestamp": 0.0,
            "lanes": {
                "north": {"vehicle_count": 0, "occupancy": 0.8},
                "south": {"vehicle_count": 0, "occupancy": 0.1},
                "east": {"vehicle_count": 0, "occupancy": 0.2},
                "west": {"vehicle_count": 0, "occupancy": 0.1}
            },
            "emergency": {"detected": False, "lane": None}
        }
        decision = self.engine.decide(state)
        self.assertEqual(decision.selected_lane, "north")
        self.assertEqual(decision.priority, Priority.NORMAL)
        self.assertTrue(any("occupancy" in r.lower() for r in decision.reasons))

    def test_vehicle_demand(self):
        # East has more vehicles, same occupancies
        state = {
            "timestamp": 0.0,
            "lanes": {
                "north": {"vehicle_count": 2, "occupancy": 0.2},
                "south": {"vehicle_count": 2, "occupancy": 0.2},
                "east": {"vehicle_count": 10, "occupancy": 0.2},
                "west": {"vehicle_count": 1, "occupancy": 0.2}
            },
            "emergency": {"detected": False, "lane": None}
        }
        decision = self.engine.decide(state)
        self.assertEqual(decision.selected_lane, "east")
        self.assertTrue(any("vehicles" in r.lower() for r in decision.reasons))

    def test_emergency_priority(self):
        # Emergency detected on West lane
        state = {
            "timestamp": 0.0,
            "lanes": {
                "north": {"vehicle_count": 15, "occupancy": 0.9},
                "south": {"vehicle_count": 2, "occupancy": 0.1},
                "east": {"vehicle_count": 2, "occupancy": 0.1},
                "west": {"vehicle_count": 0, "occupancy": 0.0}
            },
            "emergency": {"detected": True, "lane": "west"}
        }
        decision = self.engine.decide(state)
        self.assertEqual(decision.selected_lane, "west")
        self.assertEqual(decision.priority, Priority.EMERGENCY)
        self.assertTrue(any("emergency" in r.lower() for r in decision.reasons))

    def test_invalid_emergency(self):
        # Emergency detected but lane is invalid
        state = {
            "timestamp": 0.0,
            "lanes": {
                "north": {"vehicle_count": 15, "occupancy": 0.9},
                "south": {"vehicle_count": 2, "occupancy": 0.1},
                "east": {"vehicle_count": 2, "occupancy": 0.1},
                "west": {"vehicle_count": 0, "occupancy": 0.0}
            },
            "emergency": {"detected": True, "lane": "invalid_lane_name"}
        }
        decision = self.engine.decide(state)
        # Should ignore emergency and select north (highest demand)
        self.assertEqual(decision.selected_lane, "north")
        self.assertEqual(decision.priority, Priority.NORMAL)

    def test_waiting_time(self):
        # Track that waiting times increase for skipped lanes
        state1 = {
            "timestamp": 10.0,
            "lanes": {
                "north": {"vehicle_count": 15, "occupancy": 0.9},
                "south": {"vehicle_count": 2, "occupancy": 0.1},
                "east": {"vehicle_count": 2, "occupancy": 0.1},
                "west": {"vehicle_count": 2, "occupancy": 0.1}
            },
            "emergency": {"detected": False, "lane": None}
        }
        decision1 = self.engine.decide(state1)
        self.assertEqual(decision1.selected_lane, "north")
        
        # South, East, West should have been skipped, waiting times should start tracking
        # Let's run a second decision with timestamp 20.0 (delta = 10.0)
        state2 = {
            "timestamp": 20.0,
            "lanes": {
                "north": {"vehicle_count": 15, "occupancy": 0.9},
                "south": {"vehicle_count": 2, "occupancy": 0.1},
                "east": {"vehicle_count": 2, "occupancy": 0.1},
                "west": {"vehicle_count": 2, "occupancy": 0.1}
            },
            "emergency": {"detected": False, "lane": None}
        }
        decision2 = self.engine.decide(state2)
        # South's waiting time should be 10.0
        self.assertEqual(self.engine.waiting_times["south"], 10.0)
        self.assertEqual(self.engine.consecutive_skips["south"], 2)
        # North was selected again, so its wait time is 0.0
        self.assertEqual(self.engine.waiting_times["north"], 0.0)
        self.assertEqual(self.engine.consecutive_skips["north"], 0)

    def test_starvation_prevention(self):
        # Keep greening north, south is skipped until skips exceed threshold
        # config has MAX_CONSECUTIVE_SKIPS = 3
        # Decision 1: North selected
        self.engine.decide({
            "timestamp": 10.0,
            "lanes": {
                "north": {"vehicle_count": 10, "occupancy": 0.8},
                "south": {"vehicle_count": 1, "occupancy": 0.1},
                "east": {"vehicle_count": 0, "occupancy": 0.0},
                "west": {"vehicle_count": 0, "occupancy": 0.0}
            },
            "emergency": {"detected": False, "lane": None}
        })
        
        # Decision 2: North selected again (skips: south=1)
        self.engine.decide({
            "timestamp": 20.0,
            "lanes": {
                "north": {"vehicle_count": 10, "occupancy": 0.8},
                "south": {"vehicle_count": 1, "occupancy": 0.1},
                "east": {"vehicle_count": 0, "occupancy": 0.0},
                "west": {"vehicle_count": 0, "occupancy": 0.0}
            },
            "emergency": {"detected": False, "lane": None}
        })
        
        # Decision 3: North selected again (skips: south=2)
        self.engine.decide({
            "timestamp": 30.0,
            "lanes": {
                "north": {"vehicle_count": 10, "occupancy": 0.8},
                "south": {"vehicle_count": 1, "occupancy": 0.1},
                "east": {"vehicle_count": 0, "occupancy": 0.0},
                "west": {"vehicle_count": 0, "occupancy": 0.0}
            },
            "emergency": {"detected": False, "lane": None}
        })
        
        # Now skips for south = 3 (MAX_CONSECUTIVE_SKIPS is 3).
        # Next decision should trigger starvation override for South!
        decision = self.engine.decide({
            "timestamp": 40.0,
            "lanes": {
                "north": {"vehicle_count": 10, "occupancy": 0.8},
                "south": {"vehicle_count": 1, "occupancy": 0.1},
                "east": {"vehicle_count": 0, "occupancy": 0.0},
                "west": {"vehicle_count": 0, "occupancy": 0.0}
            },
            "emergency": {"detected": False, "lane": None}
        })
        
        self.assertEqual(decision.selected_lane, "south")
        self.assertEqual(decision.priority, Priority.STARVATION_PREVENTION)
        self.assertTrue(any("starvation" in r.lower() or "waiting threshold" in r.lower() for r in decision.reasons))

    def test_green_time_limits(self):
        # 1. Very busy lane should reach MAX_GREEN_TIME
        state_busy = {
            "timestamp": 0.0,
            "lanes": {
                "north": {"vehicle_count": 30, "occupancy": 1.0},
                "south": {"vehicle_count": 0, "occupancy": 0.0},
                "east": {"vehicle_count": 0, "occupancy": 0.0},
                "west": {"vehicle_count": 0, "occupancy": 0.0}
            },
            "emergency": {"detected": False, "lane": None}
        }
        decision_busy = self.engine.decide(state_busy)
        self.assertEqual(decision_busy.duration, self.config.MAX_GREEN_TIME)

        # 2. Completely empty lane should trigger MIN_GREEN_TIME
        state_empty = {
            "timestamp": 10.0,
            "lanes": {
                "north": {"vehicle_count": 0, "occupancy": 0.0},
                "south": {"vehicle_count": 0, "occupancy": 0.0},
                "east": {"vehicle_count": 0, "occupancy": 0.0},
                "west": {"vehicle_count": 0, "occupancy": 0.0}
            },
            "emergency": {"detected": False, "lane": None}
        }
        decision_empty = self.engine.decide(state_empty)
        self.assertEqual(decision_empty.duration, self.config.MIN_GREEN_TIME)

    def test_empty_intersection(self):
        # Handles empty intersection gracefully
        state = {
            "timestamp": 0.0,
            "lanes": {
                "north": {"vehicle_count": 0, "occupancy": 0.0},
                "south": {"vehicle_count": 0, "occupancy": 0.0},
                "east": {"vehicle_count": 0, "occupancy": 0.0},
                "west": {"vehicle_count": 0, "occupancy": 0.0}
            },
            "emergency": {"detected": False, "lane": None}
        }
        decision = self.engine.decide(state)
        self.assertIn(decision.selected_lane, self.config.VALID_LANES)
        self.assertEqual(decision.priority, Priority.NORMAL)
        self.assertTrue(any("empty" in r.lower() for r in decision.reasons))

    def test_invalid_occupancy_range_and_missing_data(self):
        # Malformed / missing parameters should be validation-repaired
        state = {
            "timestamp": -5.0,  # Negative timestamp
            "lanes": {
                "north": {"vehicle_count": -10, "occupancy": 2.5},  # Invalid count and occupancy
                "south": {"vehicle_count": 5},  # Missing occupancy
            },
        }
        decision = self.engine.decide(state)
        # Should not crash, and make a deterministic choice
        self.assertIn(decision.selected_lane, self.config.VALID_LANES)
        self.assertTrue(self.config.MIN_GREEN_TIME <= decision.duration <= self.config.MAX_GREEN_TIME)

    def test_deterministic_tie_breaking(self):
        # Identical lanes should tie-break alphabetically (e.g. east, north, south, west)
        # Since east is first alphabetically, it should win!
        state = {
            "timestamp": 0.0,
            "lanes": {
                "north": {"vehicle_count": 5, "occupancy": 0.5},
                "south": {"vehicle_count": 5, "occupancy": 0.5},
                "east": {"vehicle_count": 5, "occupancy": 0.5},
                "west": {"vehicle_count": 5, "occupancy": 0.5}
            },
            "emergency": {"detected": False, "lane": None}
        }
        decision = self.engine.decide(state)
        self.assertEqual(decision.selected_lane, "east")

    def test_only_one_active_lane(self):
        # Ensure only one lane is selected as active
        state = {
            "timestamp": 0.0,
            "lanes": {
                "north": {"vehicle_count": 12, "occupancy": 0.6},
                "south": {"vehicle_count": 8, "occupancy": 0.4},
                "east": {"vehicle_count": 18, "occupancy": 0.8},
                "west": {"vehicle_count": 3, "occupancy": 0.15}
            },
            "emergency": {"detected": False, "lane": None}
        }
        decision = self.engine.decide(state)
        self.assertIsInstance(decision.selected_lane, str)
        self.assertIn(decision.selected_lane, self.config.VALID_LANES)

    def test_signal_decision_fields(self):
        state = {
            "timestamp": 12.4,
            "lanes": {
                "north": {"vehicle_count": 15, "occupancy": 0.78},
                "south": {"vehicle_count": 5, "occupancy": 0.24},
                "east": {"vehicle_count": 9, "occupancy": 0.51},
                "west": {"vehicle_count": 3, "occupancy": 0.16}
            },
            "emergency": {"detected": False, "lane": None}
        }
        dec = self.engine.decide(state)
        # Verify required fields
        self.assertTrue(uuid.UUID(dec.decision_id))
        self.assertEqual(dec.timestamp, 12.4)
        self.assertEqual(dec.selected_lane, "north")
        self.assertTrue(dec.duration >= self.config.MIN_GREEN_TIME)
        self.assertEqual(dec.priority, Priority.NORMAL)
        self.assertIsInstance(dec.reasons, list)
        self.assertGreater(len(dec.reasons), 0)
        self.assertIsInstance(dec.score_breakdown, dict)
        self.assertIn("north", dec.score_breakdown)
        self.assertIsInstance(dec.confidence, float)

        # Verify compatibility properties
        self.assertEqual(dec.active_lane, dec.selected_lane)
        self.assertEqual(dec.reason, dec.reasons)

    def test_priority_enum(self):
        self.assertEqual(Priority.NORMAL, "NORMAL")
        self.assertEqual(Priority.EMERGENCY, "EMERGENCY")
        self.assertEqual(Priority.STARVATION_PREVENTION, "STARVATION_PREVENTION")

    def test_configuration_isolation_and_immutability(self):
        config = DecisionConfig()
        # Verify immutability (frozen dataclass)
        with self.assertRaises(FrozenInstanceError):
            config.MIN_GREEN_TIME = 20 # type: ignore

        # Verify isolation
        engine1 = DecisionEngine(config=DecisionConfig(MIN_GREEN_TIME=12))
        engine2 = DecisionEngine(config=DecisionConfig(MIN_GREEN_TIME=18))
        self.assertEqual(engine1.config.MIN_GREEN_TIME, 12)
        self.assertEqual(engine2.config.MIN_GREEN_TIME, 18)

    def test_timestamp_handling_repeated(self):
        # 1st cycle: timestamp 10.0
        self.engine.decide({
            "timestamp": 10.0,
            "lanes": {
                "north": {"vehicle_count": 10, "occupancy": 0.5},
                "south": {"vehicle_count": 1, "occupancy": 0.05},
                "east": {"vehicle_count": 1, "occupancy": 0.05},
                "west": {"vehicle_count": 1, "occupancy": 0.05}
            },
            "emergency": {"detected": False, "lane": None}
        })

        # 2nd cycle: timestamp 10.0 (repeated)
        self.engine.decide({
            "timestamp": 10.0,
            "lanes": {
                "north": {"vehicle_count": 10, "occupancy": 0.5},
                "south": {"vehicle_count": 1, "occupancy": 0.05},
                "east": {"vehicle_count": 1, "occupancy": 0.05},
                "west": {"vehicle_count": 1, "occupancy": 0.05}
            },
            "emergency": {"detected": False, "lane": None}
        })
        # Waiting times for skipped lanes should not have increased
        self.assertEqual(self.engine.waiting_times["south"], 0.0)

    def test_timestamp_handling_stale(self):
        # 1st cycle: timestamp 10.0
        self.engine.decide({
            "timestamp": 10.0,
            "lanes": {
                "north": {"vehicle_count": 10, "occupancy": 0.5},
                "south": {"vehicle_count": 1, "occupancy": 0.05},
                "east": {"vehicle_count": 1, "occupancy": 0.05},
                "west": {"vehicle_count": 1, "occupancy": 0.05}
            },
            "emergency": {"detected": False, "lane": None}
        })

        # 2nd cycle: timestamp 5.0 (stale/older)
        self.engine.decide({
            "timestamp": 5.0,
            "lanes": {
                "north": {"vehicle_count": 10, "occupancy": 0.5},
                "south": {"vehicle_count": 1, "occupancy": 0.05},
                "east": {"vehicle_count": 1, "occupancy": 0.05},
                "west": {"vehicle_count": 1, "occupancy": 0.05}
            },
            "emergency": {"detected": False, "lane": None}
        })
        # Waiting times for skipped lanes should not have increased (no negative time created)
        self.assertEqual(self.engine.waiting_times["south"], 0.0)

    def test_timestamp_handling_normal(self):
        # 1st cycle: timestamp 10.0
        self.engine.decide({
            "timestamp": 10.0,
            "lanes": {
                "north": {"vehicle_count": 10, "occupancy": 0.5},
                "south": {"vehicle_count": 1, "occupancy": 0.05},
                "east": {"vehicle_count": 1, "occupancy": 0.05},
                "west": {"vehicle_count": 1, "occupancy": 0.05}
            },
            "emergency": {"detected": False, "lane": None}
        })

        # 2nd cycle: timestamp 25.0 (newer, +15s elapsed)
        self.engine.decide({
            "timestamp": 25.0,
            "lanes": {
                "north": {"vehicle_count": 10, "occupancy": 0.5},
                "south": {"vehicle_count": 1, "occupancy": 0.05},
                "east": {"vehicle_count": 1, "occupancy": 0.05},
                "west": {"vehicle_count": 1, "occupancy": 0.05}
            },
            "emergency": {"detected": False, "lane": None}
        })
        self.assertEqual(self.engine.waiting_times["south"], 15.0)

    def test_no_vehicle_starvation(self):
        # 1. Check all roads empty
        state_all_empty = {
            "timestamp": 10.0,
            "lanes": {
                "north": {"vehicle_count": 0, "occupancy": 0.0},
                "south": {"vehicle_count": 0, "occupancy": 0.0},
                "east": {"vehicle_count": 0, "occupancy": 0.0},
                "west": {"vehicle_count": 0, "occupancy": 0.0}
            },
            "emergency": {"detected": False, "lane": None}
        }
        dec_all_empty = self.engine.decide(state_all_empty)
        # Should fallback to a valid lane (e.g., 'east' due to alphabetical tie-breaking of 0 scores) and not fail
        self.assertEqual(dec_all_empty.selected_lane, "east")

        # 2. One empty road with very large waiting time, but active traffic on other roads
        # We manually force the waiting time and skip counter for South to trigger starvation thresholds
        self.engine.waiting_times["south"] = 100.0
        self.engine.consecutive_skips["south"] = 10

        state_active_north = {
            "timestamp": 20.0,
            "lanes": {
                "north": {"vehicle_count": 5, "occupancy": 0.4},
                "south": {"vehicle_count": 0, "occupancy": 0.0}, # empty
                "east": {"vehicle_count": 0, "occupancy": 0.0},
                "west": {"vehicle_count": 0, "occupancy": 0.0}
            },
            "emergency": {"detected": False, "lane": None}
        }
        dec_active_north = self.engine.decide(state_active_north)
        # Should NOT choose south despite it having exceeded starvation threshold, because south is empty.
        # It must give green to the active lane (north).
        self.assertEqual(dec_active_north.selected_lane, "north")

    def test_emergency_transition_separation(self):
        # 1. State with emergency detected on East lane
        state = {
            "timestamp": 10.0,
            "lanes": {
                "north": {"vehicle_count": 10, "occupancy": 0.5},
                "south": {"vehicle_count": 2, "occupancy": 0.1},
                "east": {"vehicle_count": 1, "occupancy": 0.05},
                "west": {"vehicle_count": 1, "occupancy": 0.05}
            },
            "emergency": {"detected": True, "lane": "east"}
        }
        decision = self.engine.decide(state)
        # Decision engine should recommend east with EMERGENCY priority
        self.assertEqual(decision.selected_lane, "east")
        self.assertEqual(decision.priority, Priority.EMERGENCY)

        # 2. Mock Controller / Safety Layer owns transitions and commands
        class MockController:
            def __init__(self, current_signal: str):
                self.current_signal = current_signal

            def process_decision(self, dec: SignalDecision) -> str:
                # Controller transitions to the selected lane unless it's currently unsafe.
                # Here, mock rule: transition from north directly to east is unsafe/restricted
                if self.current_signal == "north" and dec.selected_lane == "east":
                    return "north" # Transition restricted, keep north
                return dec.selected_lane

        controller = MockController(current_signal="north")
        final_signal = controller.process_decision(decision)
        # Decision recommends "east", but Controller safety rules restrict it to "north"
        self.assertEqual(final_signal, "north")

    def test_boolean_parsing(self):
        # Test valid booleans
        self.assertTrue(parse_boolean(True))
        self.assertFalse(parse_boolean(False))
        self.assertTrue(parse_boolean("true"))
        self.assertFalse(parse_boolean("false"))
        self.assertTrue(parse_boolean("True"))
        self.assertFalse(parse_boolean("False"))
        self.assertTrue(parse_boolean("  true  "))
        
        # Test invalid values (should raise ValueError)
        with self.assertRaises(ValueError):
            parse_boolean("abc")
        with self.assertRaises(ValueError):
            parse_boolean("maybe")
        with self.assertRaises(ValueError):
            parse_boolean(None)
        with self.assertRaises(ValueError):
            parse_boolean(123)

if __name__ == "__main__":
    unittest.main()
