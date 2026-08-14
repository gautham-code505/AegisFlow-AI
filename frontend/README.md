# AegisFlow AI — Frontend Dashboard

This directory contains the human-facing control-room dashboard for **AegisFlow AI** (SmartAIthon 2026 — Round 2).

The dashboard translates real-time perception data, adaptive signal decisions, subsystem health status, and emergency alerts into an intuitive, high-trust visual control center for hackathon judges, traffic operators, and faculty demonstrators.

---

## Features & P0 Capabilities

- **Offline-First Architecture**: Clear, prominent indicator confirming 100% local edge processing with zero internet dependencies.
- **Explainable AI (XAI) Panel**: Answers *"WHY did AegisFlow choose that road?"* with structured logic explanations.
- **2D Intersection Signal Schematic**: Interactive 4-way signal light matrix with real-time countdown timer.
- **Perception & Video Stream**: Local traffic video uploader (MP4/AVI/MOV) with YOLOv8 detection metadata overlay.
- **4-Approach Occupancy Cards**: Vehicle counts, heavy vehicle tracking, pedestrian counts, and dynamic progress bars.
- **Emergency Priority Alert**: High-visibility preemption notification banner when emergency vehicles (e.g. Ambulances) are detected.
- **Subsystem Health Matrix**: Real-time status for Vision AI, Decision Engine, Safety Validator, and ESP32 Hardware Controller.
- **Real-Time Audit Log**: Monospace event stream tracking signal transitions and priority shifts.
- **Mock Presentation Scenarios**: Built-in 5-scenario demo switcher for presentation without backend runtime.

---

## Getting Started

### Prerequisites
- Node.js (v18+)
- npm (v9+)

### Installation
```bash
cd frontend
npm install
```

### Running Development Server
```bash
npm run dev
```
Open `http://localhost:5173` in your browser.

### Building for Production
```bash
npm run build
```

---

## Demo Scenarios Switcher

When operating in **MOCK / DEMO MODE**, use the header bar scenario buttons to demonstrate key system capabilities during presentations:

1. **1. Normal Balanced Traffic**: Standard round-robin signal allocation across 4 approaches.
2. **2. Heavy North Corridor**: North approach at 84% density; demonstrates extended green phase.
3. **3. Emergency Vehicle (East)**: Ambulance detected on East approach; demonstrates instant emergency preemption override.
4. **4. Heavy South Congestion**: 91% queue density on South approach with heavy vehicles.
5. **5. Vision Pipeline Warning**: Demonstrates Safety Validator fallback state during frame drops.

---

## Backend & Hardware Integration

To connect the dashboard to the live AegisFlow Python/C++ backend:

1. Click the **MOCK / DEMO MODE** toggle button in the header bar to switch to **LIVE API / WS**.
2. Configure environment variables in `.env` (optional):
   ```env
   VITE_API_URL=http://localhost:8000
   VITE_WS_URL=ws://localhost:8000/ws/traffic
   ```
3. Data contracts handled out of the box in `src/services/api.js` and `src/services/websocket.js`:
   - `TrafficState`
   - `SignalDecision`
   - `SignalState`
   - `SystemStatus`
   - `Events`

---

## Component Architecture

```
src/
├── main.jsx
├── App.jsx
├── components/
│   ├── Header.jsx             # Title, offline badge, WS connection state
│   ├── ScenarioSelector.jsx   # Demo scenario switcher & data mode toggle
│   ├── VideoPanel.jsx         # Video upload, perception overlay, YOLO stats
│   ├── IntersectionSignal.jsx # 2D 4-way junction map & countdown ring
│   ├── TrafficStats.jsx       # Wrapper for approach density cards
│   ├── OccupancyCard.jsx      # Vehicle counts & occupancy progress bars
│   ├── DecisionPanel.jsx      # Explainable AI (XAI) reason card
│   ├── EmergencyAlert.jsx     # Emergency preemption notification banner
│   ├── SystemHealth.jsx       # Subsystem component status grid
│   └── EventLog.jsx           # Audit event ticker feed
├── hooks/
│   └── useTrafficState.js     # Unified mock/live state manager hook
├── services/
│   ├── api.js                 # REST API client abstraction
│   ├── websocket.js           # WebSocket client with reconnect logic
│   └── mockData.js            # 5 presentation demo scenarios
└── styles/
    └── index.css              # Dark control-room styling tokens
```
