# AegisFlow AI Shared Contract Models (`models/`)

This directory serves as the **single source of truth** for data contracts and schemas shared across all AegisFlow AI sub-systems:

```
Harshadha Vision
       ↓
  TrafficState
       ↓
Jayasuriya Decision Engine
       ↓
 SignalDecision
       ↓
Gautham Safety / Controller
       ↓
  SignalState
       ↓
 Divya Dashboard
```

---

## Contract Modules

- **[`enums.py`](file:///f:/AegisFlow%20AI/models/enums.py)**: Canonical enumeration types (`Lane`, `SignalColor`, `SignalPhase`, `Priority`, `SystemMode`, `Status`, `EventSeverity`).
- **[`traffic_state.py`](file:///f:/AegisFlow%20AI/models/traffic_state.py)**: `TrafficState`, `LaneState`, and `EmergencyState` models representing vision observations.
- **[`signal_decision.py`](file:///f:/AegisFlow%20AI/models/signal_decision.py)**: `SignalDecision` model representing algorithm recommendations from the Decision Engine.
- **[`signal_state.py`](file:///f:/AegisFlow%20AI/models/signal_state.py)**: `SignalState` model representing real-time execution on signal heads with concurrent `active_lanes` support.
- **[`system_status.py`](file:///f:/AegisFlow%20AI/models/system_status.py)**: `SystemStatus` telemetry health status for edge nodes.
- **[`events.py`](file:///f:/AegisFlow%20AI/models/events.py)**: `Event` audit log and alert signal model.

---

## Intersection Geometry Assumptions & Safety Boundaries

> [!NOTE]
> The MVP uses a configurable simplified four-approach intersection model (`north`, `south`, `east`, `west`).
> The phase matrix represents the safety assumptions of this software prototype. It is NOT a universal representation of every real-world intersection.
> Real deployment would require intersection-specific geometry, lane/movement mapping, turning restrictions, pedestrian phases, and traffic-authority validation.
>
> The prototype prevents signal combinations that violate its configured deterministic conflict matrix.

---

## Inspection Findings & Branch Incompatibilities

During repository inspection of the remote feature branches, the following structural mismatches were identified between team member implementations and these unified shared models:

### 1. Vision Module (`origin/update-gitignore` — Harshadha)
- **Current Implementation**: Emits a raw dictionary per processed frame via `vision/main.py`.
- **Mismatches**:
  - Emits `occupancy` and `vehicle_count`, but omits `pedestrian_count` and `heavy_vehicle_count` metrics per lane.
  - `emergency` dictionary uses string keys (`detected`, `lane`) without strong enum validation.
- **Adaptation Strategy**: In future integration phases, a vision output parser will normalize frame dictionaries into `TrafficState`.

### 2. Decision Engine Module (`origin/Jayasuriya0202-feature` — Jayasuriya)
- **Current Implementation**: Defines custom Python dataclasses inside `decision_engine/models.py`.
- **Mismatches**:
  - Uses `dataclass` rather than Pydantic V2 models (`TrafficState`, `LaneState`, `EmergencyState`, `SignalDecision`).
  - `SignalDecision` uses field name `active_lane` instead of canonical `selected_lane`.
  - `SignalDecision` lacks `decision_id` and structured `score_breakdown` dictionary.
  - Option `pedestrians` in `TrafficState` is formatted as a separate top-level dict `Dict[str, int]` rather than being integrated into each `LaneState`.
- **Adaptation Strategy**: In future integration phases, `DecisionEngine` will ingest `TrafficState` and output canonical `SignalDecision` models directly or via lightweight wrappers.

### 3. Dashboard Frontend (`origin/feature/divya-dashboard` — Divya)
- **Current Implementation**: React frontend with mock data structures in `frontend/src/services/mockData.js` and WebSocket listener in `frontend/src/hooks/useTrafficState.js`.
- **Mismatches**:
  - `trafficState` expects camelCase/snake_case hybrid keys (`vehicle_count`, `heavy_vehicles`, `pedestrians`).
  - `signalState` uses flat string key mapping (`north: "GREEN"`, `south: "RED"`, `remaining_seconds: 22`), omitting explicit `phase` enum.
  - `systemStatus` includes UI dashboard fields like `fps` and `latency_ms`.
  - `SignalDecision` includes an unverified `confidence` float field.
- **Adaptation Strategy**: Future API / WebSocket serialization layers will bridge these shared models cleanly to the dashboard schemas.

---

## Validation Principles

- Models enforce strict data type constraints, bounds checking (e.g. `occupancy` in `[0.0, 1.0]`, counts `>= 0`, duration `> 0`), and enum validity.
- Models **do not** implement traffic safety logic (e.g. enforcing "North and South cannot both be GREEN"). Safety invariant enforcement belongs strictly to the **Safety Validator** (`safety/`) component.
