# AI CONTROL TOWER

# CURRENT OBJECTIVE
Live four-way physical demonstration tomorrow using:
phone camera → perception → TrafficState → Decision → Safety → ESP32 → 12 LEDs

# MASTER TASK BOARD

| Task ID | Status      | Priority | Owner       | Dependencies | Acceptance Criteria |
|---------|-------------|----------|-------------|--------------|---------------------|
| P0      | Done        | High     | Antigravity | None         | Controller dynamic timing handles 1 Hz orchestrator decisions gracefully. |
| P1      | Done        | High     | Antigravity | None         | Verify runtime model path, device, and size explicitly without code modification. |
| P2      | Done        | High     | Claude      | P0           | Independent review of the signal timing fix logic against safety invariants. |
| P3      | Done        | Critical | Antigravity | None         | Identify lowest-risk path to improve multi-vehicle live detection before demo. |
| P4      | Done        | High     | Antigravity | None         | Perform full ESP32 physical end-to-end integration test (software to lights). |
| P5      | Done        | Medium   | Team        | P3           | Run phone camera diagnostic baseline to confirm miniature vehicle detection failure. |
| P6      | Prepared    | High     | Antigravity | P5           | Execute scratch crop experiment when physical board is available tomorrow. |
| P7      | Pending     | High     | User        | P6           | Physical-board full E2E test. |
| P8      | Review      | High     | Team        | None         | Single-approach phasing (one direction GREEN at a time) + dashboard Permitted Vehicle Movements panel. Branch `single-direction-phasing`. |
| P9      | Review      | High     | Team        | None         | Firmware comms watchdog (3 s → YELLOW → ALL_RED) + conflicting-state rejection. Branch `firmware-watchdog-conflict-check`; compiled, NOT flashed or bench-tested. |

# CURRENT VERIFIED FACTS
- controller ACCEPTED
- emergency-clear fix complete
- 320 tests passing
- ESP32 physical signal sequence passed
- phone 1280x720 / ~30 FPS raw verified
- miniature vehicle live detection remains unresolved (0 detections with standard yolov8n.pt)
- crop experiment prepared for tomorrow
- physical-board full E2E still pending
- (branch single-direction-phasing) 338 tests passing; one approach GREEN at a time is the default (`ControllerConfig.SINGLE_APPROACH_PHASING`); paired N+S / E+W still available by config
- (branch single-direction-phasing) fixed: decisions re-targeting the controller during clearance starved approaches (only NORTH was ever served in a 4-way simulation); clearance target is now committed and engine bookkeeping is kept only for decisions that start a served phase

# OPEN RISKS
- Miniature vehicle detection failure under live demo lighting/angles.
- Physical-board full E2E still pending.
- Stale TrafficState reaching the orchestrator triggers FallbackController: NORTH GREEN is sent to hardware, then ALL_RED without YELLOW on the next tick (reproduced). Not yet fixed.
- With toy-car counts (<=12) green times stay near MIN_GREEN because scoring normalises to MAX_EXPECTED_VEHICLES=30; after the first long green, the 5-skip fairness rule drives a near round-robin. Tuning needed.
- ESP32 holds its last state if the backend dies (fixed on firmware branch, not yet flashed).

# ENHANCEMENT BACKLOG (proposed, not started unless marked)
Safety
- E1 Fix stale-input FALLBACK green flash; single staleness threshold from config; treat missing TrafficState with vision PROCESSING as stale.
- E2 Stop re-stamping old TrafficState with `now` in simulated-emergency and legacy per-approach endpoints.
- E3 Verify (and lock if needed) concurrent `get_current_signal_state` calls from REST threads and the telemetry loop.
- E4 Firmware: duplicate command_id after a backend restart is ACKed without latching.
Perception
- E5 Fine-tune YOLOv8n on labelled photos of the actual toy vehicles (root cause of 0 detections).
- E6 Use one YOLO setting (conf / imgsz) across live, video and image paths.
- E7 Remove hard-coded debug `cv2.imwrite` to C:\project in vision/adapter.py.
- E8 Compare P6 crop inference vs handheld close-range capture with measured counts on the same board.
- E9 Live Manual Scan mode: capture N/E/S/W with one handheld phone, review counts, propose a decision, operator presses Apply, one cycle, then ALL_RED (design reviewed; not built).
Dashboard / demo
- E10 Show ESP32 link status, last ACKed command and watchdog state.
- E11 Show the decision reason in plain words from score_breakdown.
- E12 Tune green-time scoring for tabletop vehicle counts.
Evidence
- E13 Fixed-time vs AegisFlow comparison on the same recorded videos (queue, wait, service frequency).
- E14 Firmware bench test: watchdog trip, recovery, conflicting-state NACK; record video.
Hygiene
- E15 Commit or discard stray working-tree changes; keep one firmware folder; CI running pytest + arduino-cli compile.

# NEXT TASK
"P7 — Physical-board full E2E test."

# RULE
This file must be updated whenever a major task is completed, rejected, or superseded.
