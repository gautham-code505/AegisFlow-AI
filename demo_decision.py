import json
from decision_engine import DecisionEngine

def print_decision(step_name, state_payload, decision_output):
    print("=" * 60)
    print(f"STEP: {step_name}")
    print("=" * 60)
    print("INPUT STATE:")
    print(json.dumps(state_payload, indent=2))
    print("\nDECISION OUTPUT:")
    print(json.dumps({
        "active_lane": decision_output.active_lane,
        "duration": decision_output.duration,
        "priority": decision_output.priority,
        "reason": decision_output.reason
    }, indent=2))
    print("\nEXPLAINABILITY:")
    for reason in decision_output.reason:
        print(f" - {reason}")
    print("\n")

def main():
    engine = DecisionEngine()

    # 1. Normal High Occupancy State
    normal_state = {
        "timestamp": 12.4,
        "lanes": {
            "north": {"vehicle_count": 15, "occupancy": 0.78},
            "south": {"vehicle_count": 5, "occupancy": 0.24},
            "east": {"vehicle_count": 9, "occupancy": 0.51},
            "west": {"vehicle_count": 3, "occupancy": 0.16}
        },
        "emergency": {
            "detected": False,
            "lane": None
        }
    }
    decision1 = engine.decide(normal_state)
    print_decision("Normal Operation (North has highest occupancy/vehicles)", normal_state, decision1)

    # 2. Emergency Override State
    emergency_state = {
        "timestamp": 32.4,  # +20.0s elapsed
        "lanes": {
            "north": {"vehicle_count": 15, "occupancy": 0.78},
            "south": {"vehicle_count": 5, "occupancy": 0.24},
            "east": {"vehicle_count": 9, "occupancy": 0.51},
            "west": {"vehicle_count": 3, "occupancy": 0.16}
        },
        "emergency": {
            "detected": True,
            "lane": "east"
        }
    }
    decision2 = engine.decide(emergency_state)
    print_decision("Emergency Vehicle Override (East)", emergency_state, decision2)

    # 3. Simulate Starvation State
    # Let's perform multiple cycles where East is green or North is green,
    # causing South to starved and then trigger starvation prevention.
    print("=" * 60)
    print("SIMULATING TRANSITION TO STARVATION PREVENTION FOR SOUTH APPROACH")
    print("=" * 60)
    
    # We will run 6 consecutive cycles where North is kept extremely busy,
    # and South has some traffic but is repeatedly skipped.
    sim_engine = DecisionEngine()
    
    for cycle in range(1, 7):
        state = {
            "timestamp": cycle * 30.0,
            "lanes": {
                "north": {"vehicle_count": 25, "occupancy": 0.90},
                "south": {"vehicle_count": 2, "occupancy": 0.15},
                "east": {"vehicle_count": 1, "occupancy": 0.05},
                "west": {"vehicle_count": 1, "occupancy": 0.05}
            },
            "emergency": {
                "detected": False,
                "lane": None
            }
        }
        dec = sim_engine.decide(state)
        print(f"Cycle {cycle}: Selected {dec.active_lane.capitalize()} (Priority: {dec.priority})")
        if dec.active_lane == "south":
            print(f" -> Starvation prevention triggered! Reasons:")
            for reason in dec.reason:
                print(f"    * {reason}")
            break
    print("\n")

    # 4. Safe fallback for completely invalid data
    invalid_state = {
        "timestamp": "invalid_time",
        "lanes": {
            "north": {"vehicle_count": -5, "occupancy": 12.0},  # out-of-range occupancy
            "south": None  # missing dictionary structure
        },
        "emergency": "not_a_dict"
    }
    decision4 = engine.decide(invalid_state)
    print_decision("Graceful Handling of Malformed/Missing Data", invalid_state, decision4)

if __name__ == "__main__":
    main()
