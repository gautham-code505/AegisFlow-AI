import { useState, useEffect, useCallback } from 'react';
import { SCENARIOS, mockScenariosData } from '../services/mockData';
import { createTrafficWebSocket } from '../services/websocket';

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

  // Handle operator manual override
  const applyOverride = useCallback((overrideDecision) => {
    if (!overrideDecision) {
      // Reset to scenario defaults
      setData(mockScenariosData[activeScenario]);
      return;
    }

    const targetLane = overrideDecision.active_lane;
    const isFlush = targetLane === 'none';

    setData((prev) => ({
      ...prev,
      signalDecision: {
        ...prev.signalDecision,
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
        ...prev.events,
      ],
    }));
  }, [activeScenario]);

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
        if (incoming?.trafficState) {
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
