// Mock Data Scenarios for AegisFlow AI Dashboard

export const SCENARIOS = {
  NORMAL: 'SCENARIO_1_NORMAL',
  HEAVY_NORTH: 'SCENARIO_2_HEAVY_NORTH',
  EMERGENCY_EAST: 'SCENARIO_3_EMERGENCY_EAST',
  HEAVY_SOUTH: 'SCENARIO_4_HEAVY_SOUTH',
  SYSTEM_WARNING: 'SCENARIO_5_SYSTEM_WARNING',
};

export const mockScenariosData = {
  [SCENARIOS.NORMAL]: {
    trafficState: {
      timestamp: 124.5,
      lanes: {
        north: { vehicle_count: 8, occupancy: 0.42, pedestrians: 1, heavy_vehicles: 1 },
        south: { vehicle_count: 5, occupancy: 0.28, pedestrians: 0, heavy_vehicles: 0 },
        east: { vehicle_count: 6, occupancy: 0.35, pedestrians: 2, heavy_vehicles: 1 },
        west: { vehicle_count: 3, occupancy: 0.18, pedestrians: 0, heavy_vehicles: 0 },
      },
      emergency: {
        detected: false,
        lane: null,
        vehicle_type: null,
      },
    },
    signalDecision: {
      active_lane: 'north',
      duration: 30,
      priority: 'NORMAL',
      confidence: 0.94,
      reason: [
        'Highest lane occupancy (42%)',
        'Normal demand distribution across approaches',
        'No emergency preemption request',
      ],
    },
    signalState: {
      north: 'GREEN',
      south: 'RED',
      east: 'RED',
      west: 'RED',
      remaining_seconds: 22,
    },
    systemStatus: {
      camera: 'online',
      ai: 'online',
      decision_engine: 'online',
      controller: 'online',
      internet: 'offline',
      mode: 'local',
      fps: 28,
      latency_ms: 18,
    },
    events: [
      { id: 'ev-101', timestamp: '14:32:10', type: 'SIGNAL_DECISION', message: 'North approach selected (30s green phase)' },
      { id: 'ev-100', timestamp: '14:31:40', type: 'TRAFFIC_UPDATE', message: 'Traffic state updated from visual detection' },
      { id: 'ev-099', timestamp: '14:31:20', type: 'SIGNAL_CHANGE', message: 'Signal transition: West → North' },
    ],
  },

  [SCENARIOS.HEAVY_NORTH]: {
    trafficState: {
      timestamp: 156.2,
      lanes: {
        north: { vehicle_count: 19, occupancy: 0.84, pedestrians: 3, heavy_vehicles: 3 },
        south: { vehicle_count: 4, occupancy: 0.20, pedestrians: 1, heavy_vehicles: 0 },
        east: { vehicle_count: 7, occupancy: 0.38, pedestrians: 0, heavy_vehicles: 1 },
        west: { vehicle_count: 2, occupancy: 0.12, pedestrians: 0, heavy_vehicles: 0 },
      },
      emergency: {
        detected: false,
        lane: null,
        vehicle_type: null,
      },
    },
    signalDecision: {
      active_lane: 'north',
      duration: 45,
      priority: 'HIGH_DEMAND',
      confidence: 0.98,
      reason: [
        'Critical approach queue on North (84% occupancy)',
        '19 vehicles detected on primary corridor',
        'Extended green phase allocated to clear bottleneck',
      ],
    },
    signalState: {
      north: 'GREEN',
      south: 'RED',
      east: 'RED',
      west: 'RED',
      remaining_seconds: 36,
    },
    systemStatus: {
      camera: 'online',
      ai: 'online',
      decision_engine: 'online',
      controller: 'online',
      internet: 'offline',
      mode: 'local',
      fps: 30,
      latency_ms: 16,
    },
    events: [
      { id: 'ev-203', timestamp: '14:35:02', type: 'PRIORITY_SHIFT', message: 'High demand priority triggered for North approach' },
      { id: 'ev-202', timestamp: '14:34:30', type: 'SIGNAL_DECISION', message: 'North allocated extended green duration (45s)' },
      { id: 'ev-201', timestamp: '14:34:00', type: 'QUEUE_WARNING', message: 'North occupancy exceeded 80% threshold' },
    ],
  },

  [SCENARIOS.EMERGENCY_EAST]: {
    trafficState: {
      timestamp: 189.0,
      lanes: {
        north: { vehicle_count: 12, occupancy: 0.58, pedestrians: 2, heavy_vehicles: 1 },
        south: { vehicle_count: 9, occupancy: 0.45, pedestrians: 0, heavy_vehicles: 0 },
        east: { vehicle_count: 6, occupancy: 0.72, pedestrians: 0, heavy_vehicles: 1 },
        west: { vehicle_count: 3, occupancy: 0.15, pedestrians: 1, heavy_vehicles: 0 },
      },
      emergency: {
        detected: true,
        lane: 'east',
        vehicle_type: 'AMBULANCE',
      },
    },
    signalDecision: {
      active_lane: 'east',
      duration: 35,
      priority: 'CRITICAL_EMERGENCY',
      confidence: 0.99,
      reason: [
        '⚠ EMERGENCY VEHICLE DETECTED: AMBULANCE on East approach',
        'Immediate safety preemption rule #E-01 executed',
        'Normal occupancy rotation preempted for emergency passage',
      ],
    },
    signalState: {
      north: 'RED',
      south: 'RED',
      east: 'GREEN',
      west: 'RED',
      remaining_seconds: 28,
    },
    systemStatus: {
      camera: 'online',
      ai: 'online',
      decision_engine: 'online',
      controller: 'online',
      internet: 'offline',
      mode: 'local',
      fps: 29,
      latency_ms: 14,
    },
    events: [
      { id: 'ev-303', timestamp: '14:38:15', type: 'EMERGENCY_ALERT', message: '⚠ EMERGENCY OVERRIDE: Ambulance on East lane' },
      { id: 'ev-302', timestamp: '14:38:12', type: 'PREEMPTION', message: 'Safety Validator force-cleared East signal head to GREEN' },
      { id: 'ev-301', timestamp: '14:37:50', type: 'SIGNAL_DECISION', message: 'Emergency clearance phase initiated' },
    ],
  },

  [SCENARIOS.HEAVY_SOUTH]: {
    trafficState: {
      timestamp: 210.4,
      lanes: {
        north: { vehicle_count: 4, occupancy: 0.22, pedestrians: 0, heavy_vehicles: 0 },
        south: { vehicle_count: 22, occupancy: 0.91, pedestrians: 4, heavy_vehicles: 4 },
        east: { vehicle_count: 5, occupancy: 0.27, pedestrians: 1, heavy_vehicles: 0 },
        west: { vehicle_count: 4, occupancy: 0.20, pedestrians: 0, heavy_vehicles: 0 },
      },
      emergency: {
        detected: false,
        lane: null,
        vehicle_type: null,
      },
    },
    signalDecision: {
      active_lane: 'south',
      duration: 50,
      priority: 'HIGH_DEMAND',
      confidence: 0.97,
      reason: [
        'Severe congestion on South approach (91% occupancy)',
        '22 vehicles queued including 4 heavy transport units',
        'Max duration green phase assigned to clear corridor',
      ],
    },
    signalState: {
      north: 'RED',
      south: 'GREEN',
      east: 'RED',
      west: 'RED',
      remaining_seconds: 42,
    },
    systemStatus: {
      camera: 'online',
      ai: 'online',
      decision_engine: 'online',
      controller: 'online',
      internet: 'offline',
      mode: 'local',
      fps: 27,
      latency_ms: 19,
    },
    events: [
      { id: 'ev-402', timestamp: '14:41:05', type: 'SIGNAL_CHANGE', message: 'Signal transition: North → South' },
      { id: 'ev-401', timestamp: '14:40:40', type: 'QUEUE_WARNING', message: 'South lane occupancy reached 91%' },
    ],
  },

  [SCENARIOS.SYSTEM_WARNING]: {
    trafficState: {
      timestamp: 245.8,
      lanes: {
        north: { vehicle_count: 0, occupancy: 0.0, pedestrians: 0, heavy_vehicles: 0 },
        south: { vehicle_count: 0, occupancy: 0.0, pedestrians: 0, heavy_vehicles: 0 },
        east: { vehicle_count: 0, occupancy: 0.0, pedestrians: 0, heavy_vehicles: 0 },
        west: { vehicle_count: 0, occupancy: 0.0, pedestrians: 0, heavy_vehicles: 0 },
      },
      emergency: {
        detected: false,
        lane: null,
        vehicle_type: null,
      },
    },
    signalDecision: {
      active_lane: 'north',
      duration: 20,
      priority: 'FALLBACK_FIXED',
      confidence: 0.50,
      reason: [
        '⚠ Camera vision feed frame-drop detected',
        'Safety Validator active: Enforcing deterministic fail-safe timing',
        'Operating in safe round-robin fallback cycle',
      ],
    },
    signalState: {
      north: 'YELLOW',
      south: 'RED',
      east: 'RED',
      west: 'RED',
      remaining_seconds: 4,
    },
    systemStatus: {
      camera: 'warning',
      ai: 'offline',
      decision_engine: 'online',
      controller: 'fallback',
      internet: 'offline',
      mode: 'local',
      fps: 0,
      latency_ms: 0,
    },
    events: [
      { id: 'ev-503', timestamp: '14:45:00', type: 'SYSTEM_WARN', message: '⚠ Vision AI pipeline lost frame sync. Fallback activated.' },
      { id: 'ev-502', timestamp: '14:44:58', type: 'SAFETY_INTERVENTION', message: 'Safety Validator switched controller to safe fixed-time mode' },
    ],
  },
};
