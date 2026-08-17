# AegisFlow AI — Intelligent Intersection Operating System

Offline AI-powered intelligent intersection system for adaptive mixed-traffic signal management using computer vision, explainable decision-making, deterministic safety validation, and edge-first processing.

---

## 🚦 System Architecture

- **Perception Layer (`vision/`)**: YOLOv8 + ROI polygon tracking converting real video feeds into canonical `TrafficState` observations (vehicle counts, occupancy, pedestrians, heavy vehicles).
- **Decision Engine (`decision_engine/`)**: Multi-factor priority scoring balancing real-time demand, queue starvation, and pedestrian safety.
- **Safety Kernel (`safety/`)**: Deterministic safety invariants, strict `ConflictMatrix` evaluation, clearance interval enforcement (Yellow + All-Red), and automatic fallback management.
- **Virtual Signal Controller (`controller/`)**: Time-driven finite state machine orchestrating physical/virtual signal transitions and concurrent compatible corridor green phases.
- **Backend Service (`backend/`)**: FastAPI offline-first server with REST APIs, WebSocket live snapshot streaming, and video processing pipeline.
- **Frontend Dashboard (`frontend/`)**: Modern React + Vite interactive dashboard for live traffic monitoring, signal visualization, emergency alerts, and manual overrides.

---

## 🚀 Quickstart Guide for Teammates

### 1. Clone the Repository
```bash
git clone https://github.com/gautham-code505/AegisFlow-AI.git
cd AegisFlow-AI
```

---

### 2. Backend Setup & Run

Create and activate a Python virtual environment:

**Windows (PowerShell / Command Prompt):**
```powershell
python -m venv .venv
.venv\Scripts\activate
```

**Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install backend dependencies:
```bash
pip install -r requirements.txt
```

Run the backend server:
```bash
python -m uvicorn backend.app:app --port 8000
```

- **Backend Base URL**: `http://127.0.0.1:8000`
- **Interactive Swagger Documentation**: `http://127.0.0.1:8000/docs`
- **Live WebSocket Stream**: `ws://127.0.0.1:8000/ws/traffic`

---

### 3. Frontend Setup & Run

In a second terminal window:

```bash
cd frontend
npm install
npm run dev
```

- **Live Dashboard UI**: `http://localhost:5173/`

---

### 4. Demo Video Placement

The sample demo video is included directly in the Git repository at:
```text
data/videos/demo_traffic.mp4
```

To run the full computer vision pipeline:
1. Open the dashboard at `http://localhost:5173/` or use Swagger docs at `http://127.0.0.1:8000/docs`.
2. Upload `data/videos/demo_traffic.mp4` via `POST /api/v1/video/upload`.
3. Watch the system process detections in background, score lane queues, and safely adapt signal phase timings in real time!

---

## 🧪 Testing & Verification

Run the full Python test suite (76 tests covering models, decision engine, safety invariants, virtual controller, and vision adapter):
```bash
python -m pytest tests/ decision_engine/tests/
```

Verify frontend production build:
```bash
cd frontend
npm run build
```

---

## 🛡️ Emergency Preemption & Scenarios

AegisFlow AI supports high-priority emergency preemption with safe clearance:
- **Trigger Emergency on East approach**: `POST /api/v1/demo/emergency-east`
- **Clear Emergency**: `POST /api/v1/demo/emergency/clear`
- **Preset Synthetic Scenarios**: `POST /api/v1/demo/balanced`, `POST /api/v1/demo/heavy-north`, `POST /api/v1/demo/heavy-east`
