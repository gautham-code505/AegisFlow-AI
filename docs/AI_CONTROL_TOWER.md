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

# CURRENT VERIFIED FACTS
- controller ACCEPTED
- emergency-clear fix complete
- 320 tests passing
- ESP32 physical signal sequence passed
- phone 1280x720 / ~30 FPS raw verified
- miniature vehicle live detection remains unresolved (0 detections with standard yolov8n.pt)
- crop experiment prepared for tomorrow
- physical-board full E2E still pending

# OPEN RISKS
- Miniature vehicle detection failure under live demo lighting/angles.
- Physical-board full E2E still pending.

# NEXT TASK
"P7 — Physical-board full E2E test."

# RULE
This file must be updated whenever a major task is completed, rejected, or superseded.
