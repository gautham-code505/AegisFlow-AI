# AegisFlow Final Runbook

## 1. Localhost Startup & Dashboard
AegisFlow operates as a completely offline, edge-first AI operating system. 
1. **Start Backend**: `python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000`
2. **Start Frontend**: `npm run dev -- --host 127.0.0.1 --port 5173`
3. **Open Dashboard**: Navigate to [http://127.0.0.1:5173](http://127.0.0.1:5173) in any modern browser. All assets are bundled locally; no internet access is required.

## 2. Phone USB Webcam Configuration
The canonical live perception pipeline requires a physical camera connected via USB.
- **Requirement:** Connect an Android phone via USB and configure it to act as an Android Webcam.
- **Resolution Expectation:** The Windows MSMF backend must expose the camera at exactly `1280x720`.
- **Camera Source Index:** The system defaults to checking `camera_source: 2` (or via the UI Start Camera command `source: 1`/`source: 0` as enumerated by Windows). Modify `camera_source` in `vision/config.json` if Windows re-indexes your phone upon reboot.

## 3. YOLOv8 & Inference
- **Inference Size:** YOLOv8n runs at `imgsz=960` for the perfect balance of detection accuracy (especially for distant vehicles) and processing speed.
- **Hardware Acceleration:** The runtime automatically attaches to the NVIDIA RTX 3050 CUDA device, computing inference at ~29 FPS on the live 720p stream.

## 4. Offline Runtime Statement
**AegisFlow is a True Offline Operating System.** 
It performs real-time YOLOv8 object detection on CUDA, tracks objects, evaluates traffic states, and renders the live interactive telemetry dashboard without transmitting a single byte over the public internet. Telemetry and metrics modules gracefully disable themselves without hanging or throwing network timeout errors when run offline.

## 5. Camera Stop → ALL_RED Safety Behavior
The safety kernel operates deterministically:
- If the live camera feed stops or the video stream is severed, the system immediately recognizes the loss of perception (`vision: ERROR`, `camera: NO INPUT`).
- **Fail-Safe Triggered:** All active/stale traffic cues are purged. The controller automatically restricts the system to an `ALL_RED` state. 
- No green lights will ever be erroneously held due to a frozen or dead camera feed.
