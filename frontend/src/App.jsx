import React, { useState } from 'react';
import { useTrafficState } from './hooks/useTrafficState';
import { Header } from './components/Header';
import { ScenarioSelector } from './components/ScenarioSelector';
import { VideoPanel } from './components/VideoPanel';
import { LivePerceptionPanel } from './components/LivePerceptionPanel';
import { IntersectionTwin } from './components/IntersectionTwin';
import { TrafficIntelligence } from './components/TrafficIntelligence';
import { DecisionPanel } from './components/DecisionPanel';
import { SafetyPanel } from './components/SafetyPanel';
import { EmergencyAlert } from './components/EmergencyAlert';
import { SystemHealthBar } from './components/SystemHealthBar';
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
    measurements,
    analytics,
    approachDetections,
    approachStatuses,
    safetyResult,
    activeScenario,
    setScenario,
    isMockMode,
    setIsMockMode,
    wsStatus,
    isStale,
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

        {/* LIVE PERCEPTION PANEL */}
        {!isMockMode && (
          <div className="mb-4">
            <LivePerceptionPanel systemStatus={systemStatus} trafficState={trafficState} />
          </div>
        )}

        {/* Section 1: AI Decision + Digital Twin + Safety */}
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 mb-4">
          <div className="lg:col-span-1">
            <DecisionPanel signalDecision={signalDecision} />
          </div>
          <div className="lg:col-span-2">
            <IntersectionTwin
              signalState={signalState}
              trafficState={trafficState}
              signalDecision={signalDecision}
              safetyResult={safetyResult}
              isStale={isStale}
              systemStatus={systemStatus}
            />
          </div>
          <div className="lg:col-span-1">
            <SafetyPanel safetyResult={safetyResult} />
          </div>
        </div>

        {/* Section 3: Stats & Health */}
        <div className="grid grid-cols-1 xl:grid-cols-4 gap-4 mb-4">
          <div className="xl:col-span-3">
            <TrafficIntelligence 
              trafficState={trafficState} 
              signalDecision={signalDecision} 
              approachStatuses={approachStatuses}
              measurements={measurements}
              analytics={analytics}
              has_tracking_data={trafficState?.has_tracking_data}
            />
          </div>
          <div className="xl:col-span-1">
            <SystemHealthBar systemStatus={systemStatus} wsStatus={wsStatus} isStale={isStale} />
          </div>
        </div>

        {/* Section 3: Event Audit Log */}
        <div className="mb-4">
          <EventLog events={events} />
        </div>

        {/* Section 4: Legacy Debug Video Panel */}
        <details className="mb-4 bg-slate-900/40 rounded-xl border border-slate-800/80 p-1 group">
          <summary className="text-xs font-bold text-slate-400 uppercase tracking-wider cursor-pointer list-none flex items-center justify-between p-3 hover:text-slate-300 hover:bg-slate-800/30 rounded-lg transition-colors">
            <span className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-slate-600"></span>
              Legacy 4-Camera Perception Feed (Debug View)
            </span>
            <span className="text-slate-600 group-open:rotate-180 transition-transform duration-300">▼</span>
          </summary>
          <div className="mt-2 p-1">
            <VideoPanel
              systemStatus={systemStatus}
              trafficState={trafficState}
              approachDetections={approachDetections}
              approachStatuses={approachStatuses}
              signalDecision={signalDecision}
            />
          </div>
        </details>

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
