import { useState, useEffect, useCallback } from 'react';
import { SCENARIOS, mockScenariosData } from '../services/mockData';
import { createTrafficWebSocket } from '../services/websocket';
import { sendManualOverride } from '../services/api';

export function useTrafficState() {
  const [activeScenario, setActiveScenario] = useState(SCENARIOS.NORMAL);
  const [isMockMode, setIsMockMode] = useState(true);
  const [wsStatus, setWsStatus] = useState('DISCONNECTED');

  // Active data state initialized from mock scenario
  const [data, setData] = useState(() => mockScenariosData[SCENARIOS.NORMAL]);

  // Handle scenario switching in mock mode
  const setScenario = useCallback((scenarioKey) => {
    if (mockScenariosData[scenarioKey]) {
      setActiveScenario(scenarioKey);
      setData(mockScenariosData[scenarioKey]);
    }
  }, []);

  /**
   * Local-only simulation of the override result — used as mock mode fallback
   * or when the backend override endpoint is unreachable.
   */
  const _applyOverrideLocally = useCallback((overrideDecision, prevData) => {
    const targetLane = overrideDecision.active_lane;
    const isFlush = targetLane === 'none';

    return {
      ...prevData,
      signalDecision: {
        ...prevData.signalDecision,
        active_lane: targetLane,
        duration: overrideDecision.duration || 60,
        priority: overrideDecision.priority || 'MANUAL_OPERATOR_OVERRIDE',
        reason: overrideDecision.reason || ['Manual override active'],
      },
      signalState: {
        north: isFlush ? 'RED' : targetLane === 'north' ? 'GREEN' : 'RED',
        south: isFlush ? 'RED' : targetLane === 'south' ? 'GREEN' : 'RED',
        east: isFlush ? 'RED' : targetLane === 'east' ? 'GREEN' : 'RED',
        west: isFlush ? 'RED' : targetLane === 'west' ? 'GREEN' : 'RED',
        remaining_seconds: overrideDecision.duration || 60,
      },
      events: [
        {
          id: `ev-manual-${Date.now()}`,
          timestamp: new Date().toLocaleTimeString('en-US', { hour12: false }),
          type: 'OPERATOR_OVERRIDE',
          message: `⚠ MANUAL OVERRIDE: ${overrideDecision.priority} (${targetLane.toUpperCase()})`,
        },
        ...prevData.events,
      ],
    };
  }, []);

  /**
   * Handle operator manual override.
   *
   * In live mode: sends override command to backend. The server validates the
   * request and returns the resulting SignalState — the frontend applies that
   * authoritative state. Browser-only state mutation is never treated as real
   * control in live mode.
   *
   * In mock mode (or when the backend is unreachable): falls back to local
   * simulation so judge demonstrations work 100% offline.
   */
  const applyOverride = useCallback(async (overrideDecision) => {
    if (!overrideDecision) {
      // Reset to scenario defaults
      setData(mockScenariosData[activeScenario]);
      return;
    }

    if (isMockMode) {
      // Mock mode: apply purely locally — no backend call
      setData((prev) => _applyOverrideLocally(overrideDecision, prev));
      return;
    }

    // Live mode: command goes to backend for server-side validation
    try {
      const serverResponse = await sendManualOverride(overrideDecision);

      // Backend returns validated SignalState (and optionally signalDecision)
      setData((prev) => ({
        ...prev,
        ...(serverResponse.signalDecision ? { signalDecision: serverResponse.signalDecision } : {}),
        ...(serverResponse.signalState ? { signalState: serverResponse.signalState } : {}),
        events: [
          {
            id: `ev-manual-${Date.now()}`,
            timestamp: new Date().toLocaleTimeString('en-US', { hour12: false }),
            type: 'OPERATOR_OVERRIDE',
            message: `⚠ MANUAL OVERRIDE: ${overrideDecision.priority} (${(overrideDecision.active_lane || 'none').toUpperCase()}) — Server Validated`,
          },
          ...prev.events,
        ],
      }));
    } catch (err) {
      // Backend unreachable: fall back to local simulation
      console.warn('[useTrafficState] Override backend unreachable, applying locally:', err.message);
      setData((prev) => _applyOverrideLocally(overrideDecision, prev));
    }
  }, [activeScenario, isMockMode, _applyOverrideLocally]);

  // Countdown timer effect for visual presentation in mock mode
  useEffect(() => {
    if (!isMockMode) return;

    const timer = setInterval(() => {
      setData((prevData) => {
        if (!prevData?.signalState) return prevData;
        const currentRem = prevData.signalState.remaining_seconds;
        const newRem = currentRem > 1 ? currentRem - 1 : prevData.signalDecision?.duration || 30;

        return {
          ...prevData,
          signalState: {
            ...prevData.signalState,
            remaining_seconds: newRem,
          },
        };
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [isMockMode]);

  // WebSocket listener when live mode is toggled on
  useEffect(() => {
    if (isMockMode) return;

    const wsClient = createTrafficWebSocket({
      onMessage: (incoming) => {
        // Apply ALL valid object payloads — not only those that happen to
        // contain a trafficState key. Each payload is shallow-merged so the
        // backend can send partial updates (e.g. signalState-only frames).
        if (incoming && typeof incoming === 'object' && !Array.isArray(incoming)) {
          setData((prev) => ({
            ...prev,
            ...incoming,
          }));
        }
      },
      onStatusChange: (status) => {
        setWsStatus(status);
      },
      onError: (err) => {
        console.warn('[useTrafficState] WebSocket error:', err);
      },
    });

    return () => {
      wsClient.disconnect();
    };
  }, [isMockMode]);

  return {
    trafficState: data.trafficState,
    signalDecision: data.signalDecision,
    signalState: data.signalState,
    systemStatus: data.systemStatus,
    events: data.events || [],
    activeScenario,
    setScenario,
    isMockMode,
    setIsMockMode,
    wsStatus,
    applyOverride,
  };
}
