# AegisFlow Efficiency Upgrade Roadmap
## UPG-01 Baseline + Performance Profiling Report

### A. Current Test Result
- **Total Tests:** 312
- **Passed:** 301
- **Failed:** 11
- **Skipped / Errors:** 0
- **Important Warnings:** Some vision tests failed due to a mock signature mismatch (`MockDetector.detect() got an unexpected keyword argument 'conf'`). A few integration and hardware proxy tests also failed. No production code was changed to force a pass.

### B. Current Camera Architecture
- The system runs the live camera in a dedicated background thread (`CameraRuntimeThread`) via `CameraRuntimeManager`.
- This correctly isolates the synchronous OpenCV/YOLO blocking calls from the FastAPI `asyncio` event loop.
- `VisionAdapter` iterates over a generator produced by `process_source`, applying YOLO inference (`detector.detect`) and tracking sequentially per frame.

### C. Current Frame-Buffering Behavior
- `VideoProcessor` implements a decoupled capture model.
- A `LiveCaptureThread` constantly reads frames from OpenCV (`cap.read()`) and updates a single `_latest_frame` variable protected by a lock.
- **Result:** "Latest-frame behavior" *already exists*. If inference is slower than the camera FPS, older unread frames are naturally dropped rather than building up a blocking queue.

### D. Current YOLO Configuration
- **Model:** `yolov8n.pt` (Nano)
- **Inference Size:** Default (640), as `imgsz` is not explicitly passed by `CameraRuntimeManager`.
- **Confidence Threshold:** Default (0.25), as `conf` is not explicitly passed.
- **Device:** CPU (Ultralytics auto-selects CPU on this environment).
- **Tracker:** ByteTrack (`bytetrack.yaml` default).

### E. YOLO / GPU Benchmark (Synthetic Image)
*(Measured via `bench_yolo.py` over 10 iterations on `car_contact.jpg`)*
- **Device:** CPU
- **Average Inference Latency:** 185.56 ms
- **Approximate Inference FPS:** ~5.39 FPS
- **Detection Count:** 23
- **GPU Usage:** N/A (Running on CPU)

### F. Recorded-Video Benchmark
*(Measured via `bench_video.py` on 50 frames of `approach_north_WhatsApp Video...mp4` without tracking)*
- **Processing FPS:** ~8.09 FPS
- **Average Frame Latency:** 123.67 ms
- **Frames Accumulate / Playback Outrun:** Because `VideoProcessor` uses a synchronous generator, reading from a file blocks until processed. However, in live streams, frames are successfully dropped.
- **Source Stop/EOF:** Ends the generator gracefully and releases resources.

### G. TrafficState / Decision Timing
- **Decision Scheduler Frequency:** Evaluated dynamically when a new frame is processed (synchronous flow in `Orchestrator`).
- **Telemetry Loop:** `_telemetry_broadcast_loop` fires every 1.0 seconds.
- **Emergency Wake-up:** The `CameraRuntimeManager` thread explicitly calls `loop.call_soon_threadsafe(decision_event.set)` if an emergency vehicle is detected, immediately waking up the `_decision_loop` to bypass the 1.0s timeout.

### H. WebSocket / Frontend Observations
- **Message Frequency:** Broadcasts happen at least every 1.0 seconds, plus dynamically every time `Orchestrator` processes a frame. This could result in 5-10 broadcasts per second depending on inference speed.
- **Message Size:** Image data is NOT mixed into the WebSocket state. `has_media=True` is just a boolean.
- **Frame Delivery:** The frontend fetches MJPEG via a separate `/stream` HTTP endpoint.
- **Frontend Observation:** The React `LivePerceptionPanel.jsx` component receives state updates often. Excessive unbatched broadcasts can trigger unnecessary React re-renders.

### J. Top 3 Measured Bottlenecks
1. **CPU-Bound Inference:** YOLOv8n running on CPU takes ~120-185ms per frame. This strictly caps the entire pipeline at ~5-8 FPS regardless of camera speed.
2. **Synchronous Tracking:** ByteTrack runs sequentially after YOLO on the same thread, further lowering the FPS in live environments.
3. **Redundant Broadcasts:** WebSocket broadcasts both on an interval (1.0s) and on every processed frame, causing network chatter and UI render churn.

### K. Recommended Optimization Order (For UPG-02 and beyond)
1. **Hardware Acceleration:** Force YOLO onto GPU (CUDA/TensorRT) and reduce inference `imgsz` (e.g., 320) to significantly boost FPS.
2. **Throttle WebSocket Broadcasts:** Implement a debouncer or fixed tick-rate (e.g., 250ms) for WebSocket state broadcasts to reduce React UI lag.
3. **Async Tracking / Parallelism:** Decouple the ByteTrack logic from the main YOLO inference thread if higher throughput is required, or use a lighter tracking configuration.

*(Note: Live camera and hardware controller benchmarks were bypassed as hardware is disconnected.)*
