import { useState, useEffect, useCallback } from 'react';
import { SCENARIOS, mockScenariosData } from '../services/mockData';
import { createTrafficWebSocket } from '../services/websocket';
import { postOverride, deleteOverride } from '../services/api';

const EMPTY_STATE = {
  trafficState: null,
  signalDecision: null,
  signalState: null,
  systemStatus: null,
  events: [],
  approachDetections: {},
  safetyResult: null
};

export function useTrafficState() {
  const [activeScenario, setActiveScenario] = useState(SCENARIOS.NORMAL);
  const [isMockMode, setIsMockMode] = useState(false);
  const [wsStatus, setWsStatus] = useState('DISCONNECTED');

  const [data, setData] = useState(EMPTY_STATE);

  useEffect(() => {
    if (isMockMode) {
      setData(mockScenariosData[activeScenario]);
    } else {
      setData(EMPTY_STATE);
    }
  }, [isMockMode, activeScenario]);

  const setScenario = useCallback((scenarioKey) => {
    if (mockScenariosData[scenarioKey]) {
      setActiveScenario(scenarioKey);
      if (isMockMode) {
        setData(mockScenariosData[scenarioKey]);
      }
    }
  }, [isMockMode]);

  const applyOverride = useCallback(async (overrideDecision) => {
    if (!isMockMode) {
      try {
        if (!overrideDecision || overrideDecision.selected_lane === 'none') {
          await deleteOverride();
        } else {
          await postOverride(overrideDecision.selected_lane, overrideDecision.duration || 60);
        }
      } catch (err) {
        console.error('Failed to apply live override', err);
      }
      return;
    }

    if (!overrideDecision) {
      setData(mockScenariosData[activeScenario]);
      return;
    }

    const targetLane = overrideDecision.selected_lane;
    const isFlush = targetLane === 'none';

    setData((prev) => ({
      ...prev,
      signalDecision: {
        ...prev.signalDecision,
        selected_lane: targetLane,
        duration: overrideDecision.duration || 60,
        priority: overrideDecision.priority || 'MANUAL',
        reasons: overrideDecision.reasons || ['Manual override active'],
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
          event_id: `ev-manual-${Date.now()}`,
          timestamp: Date.now() / 1000,
          type: 'OPERATOR_OVERRIDE',
          severity: 'warning',
          message: `⚠ MANUAL OVERRIDE: ${overrideDecision.priority} (${targetLane.toUpperCase()})`,
        },
        ...prev.events,
      ],
    }));
  }, [activeScenario, isMockMode]);

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

  useEffect(() => {
    if (isMockMode) return;

    const wsClient = createTrafficWebSocket({
      onMessage: (incoming) => {
        if (incoming?.trafficState || incoming?.signalDecision || incoming?.signalState) {
          setData((prev) => {
            const newData = { ...prev };
            if (incoming.trafficState) newData.trafficState = incoming.trafficState;
            if (incoming.signalDecision) newData.signalDecision = incoming.signalDecision;
            if (incoming.signalState) newData.signalState = incoming.signalState;
            if (incoming.systemStatus) newData.systemStatus = incoming.systemStatus;
            if (incoming.events) newData.events = incoming.events;
            if (incoming.approachDetections !== undefined) newData.approachDetections = incoming.approachDetections;
            if (incoming.safetyResult !== undefined) newData.safetyResult = incoming.safetyResult;
            return newData;
          });
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
    approachDetections: data.approachDetections || {},
    safetyResult: data.safetyResult || null,
    activeScenario,
    setScenario,
    isMockMode,
    setIsMockMode,
    wsStatus,
    applyOverride,
  };
}
