# AegisFlow Agents & Guidelines

AegisFlow is being developed by a collaborative AI team:
- **ChatGPT**: Chief Architect / Technical Program Manager
- **Antigravity + Gemini**: Local Implementation + Experiment Agent
- **Claude**: Independent Senior Reviewer

All agents must treat `docs/AI_CONTROL_TOWER.md` as the current project status document.

## Architecture & Principles
AegisFlow architecture separates concerns strictly across Perception, Decision, Safety, and physical Control.

**Core Safety Invariants:**
1. **"AI decides priority. Safety decides permission."**
2. **Never allow conflicting green phases:** The ConflictMatrix is absolute.
3. **Loss of Perception:** No camera input (`VisionStatus.ERROR` or `camera_source: NO_INPUT`) immediately forces a safe `ALL_RED` state.
4. **Logical Authority:** Logical `SignalState` (managed by the VirtualSignalController) is the authoritative source of truth over the physical transport.
5. **Hardware Isolation:** Physical ESP32 failure, timeouts, or disconnection must not corrupt or freeze the logical state.

## Agent Working Rules
- **Do not modify unrelated systems** during focused, targeted tasks.
- **Evidence-Based Engineering:** Require reproducible evidence before claiming success.
- **Performance Integrity:** Never claim training or detection performance improvements without concrete measurements.
