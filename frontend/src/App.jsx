import React, { useState } from 'react';
import { useTrafficState } from './hooks/useTrafficState';
import { Header } from './components/Header';
import { ScenarioSelector } from './components/ScenarioSelector';
import { VideoPanel } from './components/VideoPanel';
import { IntersectionSignal } from './components/IntersectionSignal';
import { TrafficStats } from './components/TrafficStats';
import { DecisionPanel } from './components/DecisionPanel';
import { SafetyPanel } from './components/SafetyPanel';
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
    approachDetections,
    safetyResult,
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

        {/* Data Source & Scenario Selector */}
        <ScenarioSelector
          activeScenario={activeScenario}
          onSelectScenario={setScenario}
          isMockMode={isMockMode}
          onToggleMockMode={setIsMockMode}
        />

        {/* Emergency Alert Banner */}
        <EmergencyAlert emergency={trafficState?.emergency} />

        {/* Section 1: Inputs (VideoPanel) */}
        <div className="mb-4">
          <VideoPanel
            systemStatus={systemStatus}
            trafficState={trafficState}
            approachDetections={approachDetections}
            signalDecision={signalDecision}
          />
        </div>

        {/* Section 2: AI Decision + Signal Matrix + Safety */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
          <DecisionPanel signalDecision={signalDecision} />
          <IntersectionSignal
            signalState={signalState}
            signalDecision={signalDecision}
            trafficState={trafficState}
          />
          <SafetyPanel safetyResult={safetyResult} />
        </div>

        {/* Section 3: Stats & Health */}
        <div className="grid grid-cols-1 xl:grid-cols-4 gap-4 mb-4">
          <div className="xl:col-span-3">
            <TrafficStats trafficState={trafficState} signalDecision={signalDecision} />
          </div>
          <div className="xl:col-span-1">
            <SystemHealth systemStatus={systemStatus} />
          </div>
        </div>

        {/* Section 4: Event Audit Log */}
        <div className="mb-4">
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
            AegisFlow AI — Intelligent Adaptive Traffic Control
          </div>
          <div className="text-emerald-400/80 font-mono font-medium">
            100% Offline Edge Operation
          </div>
        </footer>
      </div>
    </div>
  );
}
