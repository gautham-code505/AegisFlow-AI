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
  approachStatuses: {},
  safetyResult: null,
  measurements: [],
  analytics: {}
};

// 3 seconds threshold for UI data freshness (telemetry snapshot heartbeat).
// NOTE: This represents UI data freshness, NOT the traffic controller's safety mechanism (SafetyValidator).
const STALE_THRESHOLD_MS = 3000;

export function useTrafficState() {
  const [activeScenario, setActiveScenario] = useState(SCENARIOS.NORMAL);
  const [isMockMode, setIsMockMode] = useState(false);
  const [wsStatus, setWsStatus] = useState('DISCONNECTED');
  const [lastUpdated, setLastUpdated] = useState(null);
  const [isStale, setIsStale] = useState(false);

  const [data, setData] = useState(EMPTY_STATE);

  useEffect(() => {
    if (isMockMode) {
      setData(mockScenariosData[activeScenario]);
      setIsStale(false);
    } else {
      setData(EMPTY_STATE);
      setLastUpdated(null);
      setIsStale(false);
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

  // Handle mock mode countdowns
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

  // Real WebSocket connection
  useEffect(() => {
    if (isMockMode) return;

    const wsClient = createTrafficWebSocket({
      onMessage: (incoming) => {
        setLastUpdated(Date.now());
        setIsStale(false);
        
        if (incoming?.trafficState || incoming?.signalDecision || incoming?.signalState) {
          setData((prev) => {
            const newData = { ...prev };
            if (incoming.trafficState) newData.trafficState = incoming.trafficState;
            if (incoming.signalDecision) newData.signalDecision = incoming.signalDecision;
            if (incoming.signalState) newData.signalState = incoming.signalState;
            if (incoming.systemStatus) newData.systemStatus = incoming.systemStatus;
            if (incoming.events) newData.events = incoming.events;
            if (incoming.approachDetections !== undefined) newData.approachDetections = incoming.approachDetections;
            if (incoming.approachStatuses !== undefined) newData.approachStatuses = incoming.approachStatuses;
            if (incoming.safetyResult !== undefined) newData.safetyResult = incoming.safetyResult;
            if (incoming.measurements !== undefined) newData.measurements = incoming.measurements;
            if (incoming.analytics !== undefined) newData.analytics = incoming.analytics;
            return newData;
          });
        }
      },
      onStatusChange: (status) => {
        setWsStatus(status);
        if (status === 'DISCONNECTED' || status === 'ERROR') {
            setIsStale(true);
        }
      },
      onError: (err) => {
        console.warn('[useTrafficState] WebSocket error:', err);
      },
    });

    return () => {
      wsClient.disconnect();
    };
  }, [isMockMode]);

  // Staleness checker
  useEffect(() => {
    if (isMockMode || wsStatus !== 'CONNECTED') return;

    const interval = setInterval(() => {
      if (lastUpdated && Date.now() - lastUpdated > STALE_THRESHOLD_MS) {
        setIsStale(true);
      }
    }, 500);

    return () => clearInterval(interval);
  }, [isMockMode, wsStatus, lastUpdated]);

  return {
    trafficState: data.trafficState,
    signalDecision: data.signalDecision,
    signalState: data.signalState,
    systemStatus: data.systemStatus,
    events: data.events || [],
    measurements: data.measurements || [],
    analytics: data.analytics || {},
    approachDetections: data.approachDetections || {},
    approachStatuses: data.approachStatuses || {},
    safetyResult: data.safetyResult || null,
    activeScenario,
    setScenario,
    isMockMode,
    setIsMockMode,
    wsStatus,
    isStale,
    applyOverride,
  };
}
