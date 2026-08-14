import React, { useState } from 'react';
import { useTrafficState } from './hooks/useTrafficState';
import { Header } from './components/Header';
import { ScenarioSelector } from './components/ScenarioSelector';
import { VideoPanel } from './components/VideoPanel';
import { IntersectionSignal } from './components/IntersectionSignal';
import { TrafficStats } from './components/TrafficStats';
import { OccupancyTrendsChart } from './components/OccupancyTrendsChart';
import { PerformanceMetrics } from './components/PerformanceMetrics';
import { DecisionPanel } from './components/DecisionPanel';
import { EmergencyAlert } from './components/EmergencyAlert';
import { SystemHealth } from './components/SystemHealth';
import { EventLog } from './components/EventLog';
import { ManualOverrideModal } from './components/ManualOverrideModal';

export default function App() {
  const [isOverrideModalOpen, setIsOverrideModalOpen] = useState(false);

  const {
    trafficState,
    signalDecision,
    signalState,
    systemStatus,
    events,
    activeScenario,
    setScenario,
    isMockMode,
    setIsMockMode,
    wsStatus,
    applyOverride,
  } = useTrafficState();

  return (
    <div className="min-h-screen bg-[#0b0f17] text-slate-100 p-4 md:p-6 font-sans">
      <div className="max-w-[1600px] mx-auto">
        {/* Header Bar */}
        <Header
          isMockMode={isMockMode}
          wsStatus={wsStatus}
          onOpenOverrideModal={() => setIsOverrideModalOpen(true)}
        />

        {/* Demo Scenario & Data Mode Switcher */}
        <ScenarioSelector
          activeScenario={activeScenario}
          onSelectScenario={setScenario}
          isMockMode={isMockMode}
          onToggleMockMode={setIsMockMode}
        />

        {/* Emergency Alert Banner */}
        <EmergencyAlert emergency={trafficState?.emergency} />

        {/* Main Grid Section 1: Perception & Signal Matrix */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
          <VideoPanel systemStatus={systemStatus} trafficState={trafficState} />
          <IntersectionSignal
            signalState={signalState}
            signalDecision={signalDecision}
            trafficState={trafficState}
          />
        </div>

        {/* Main Grid Section 2: 4-Way Approach Density & Counts */}
        <div className="mb-4">
          <TrafficStats trafficState={trafficState} signalDecision={signalDecision} />
        </div>

        {/* Main Grid Section 3: Telemetry Trends & Performance */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
          <OccupancyTrendsChart trafficState={trafficState} />
          <PerformanceMetrics systemStatus={systemStatus} />
        </div>

        {/* Main Grid Section 4: Explainable AI, Subsystem Health & Audit Event Stream */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <DecisionPanel signalDecision={signalDecision} />
          <SystemHealth systemStatus={systemStatus} />
          <EventLog events={events} />
        </div>

        {/* Manual Override Control Modal */}
        <ManualOverrideModal
          isOpen={isOverrideModalOpen}
          onClose={() => setIsOverrideModalOpen(false)}
          onApplyOverride={applyOverride}
        />

        {/* Footer */}
        <footer className="mt-6 pt-4 border-t border-slate-800 text-center text-xs text-slate-500 flex flex-col sm:flex-row items-center justify-between gap-2">
          <div>
            AegisFlow AI — SmartAIthon 2026 | Team: Divya K (Frontend), Gautham M A (Lead), Harshadha M (Vision), Jayasuriya S (Decision)
          </div>
          <div className="text-emerald-400/80 font-mono font-medium">
            100% Offline Edge Operation Verified
          </div>
        </footer>
      </div>
    </div>
  );
}
