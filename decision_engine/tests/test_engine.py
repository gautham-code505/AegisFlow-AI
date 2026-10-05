import unittest
from decision_engine import DecisionEngine, DecisionEngineConfig, TrafficState, LaneState, EmergencyState

class TestDecisionEngine(unittest.TestCase):
    def setUp(self):
        # Clean config for testing
        self.config = DecisionEngineConfig(
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
        self.assertEqual(decision.selected_lane.value, "north")
        self.assertEqual(decision.priority.value, "NORMAL")
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
        self.assertEqual(decision.selected_lane.value, "east")
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
        self.assertEqual(decision.selected_lane.value, "west")
        self.assertEqual(decision.priority.value, "EMERGENCY")
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
        self.assertEqual(decision.selected_lane.value, "north")
        self.assertEqual(decision.priority.value, "NORMAL")

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
        self.assertEqual(decision1.selected_lane.value, "north")
        
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
        
        self.assertEqual(decision.selected_lane.value, "south")
        self.assertEqual(decision.priority.value, "HIGH")
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
        self.assertIn(decision.selected_lane.value, self.config.VALID_LANES)
        self.assertEqual(decision.priority.value, "NORMAL")
        self.assertTrue(any("empty" in r.lower() for r in decision.reasons))

    def test_invalid_occupancy_range_and_missing_data(self):
        # Malformed / missing parameters should be validation-repaired
        state = {
            "timestamp": -5.0,  # Negative timestamp
            "lanes": {
                "north": {"vehicle_count": -10, "occupancy": 2.5},  # Invalid count and occupancy
                "south": {"vehicle_count": 5},  # Missing occupancy
                # east and west missing entirely
            },
            # emergency and pedestrians missing entirely
        }
        decision = self.engine.decide(state)
        # Should not crash, and make a deterministic choice
        self.assertIn(decision.selected_lane.value, self.config.VALID_LANES)
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
        self.assertEqual(decision.selected_lane.value, "east")

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
        self.assertIsInstance(decision.selected_lane.value, str)
        self.assertIn(decision.selected_lane.value, self.config.VALID_LANES)

if __name__ == "__main__":
    unittest.main()
