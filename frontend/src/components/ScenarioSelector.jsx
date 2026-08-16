import React from 'react';
import { SCENARIOS } from '../services/mockData';
import { Sliders, Radio, ToggleLeft, ToggleRight } from 'lucide-react';

export function ScenarioSelector({ activeScenario, onSelectScenario, isMockMode, onToggleMockMode }) {
  const scenarioLabels = [
    { key: SCENARIOS.NORMAL, label: '1. Normal Balanced Traffic', badge: 'Normal' },
    { key: SCENARIOS.HEAVY_NORTH, label: '2. Heavy North Corridor', badge: 'High Density' },
    { key: SCENARIOS.EMERGENCY_EAST, label: '3. Emergency Vehicle (East)', badge: 'Emergency' },
    { key: SCENARIOS.HEAVY_SOUTH, label: '4. Heavy South Congestion', badge: 'Queue Priority' },
    { key: SCENARIOS.SYSTEM_WARNING, label: '5. Vision Pipeline Warning', badge: 'Fallback' },
  ];

  return (
    <div className="control-card rounded-xl p-3 mb-4 text-xs">
      <div className="flex flex-wrap items-center justify-between gap-3">
        {/* Mode Toggle */}
        <div className="flex items-center gap-2 border-r border-slate-700 pr-4">
          <span className="text-slate-400 font-medium">Data Source:</span>
          <button
            onClick={() => onToggleMockMode(!isMockMode)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-semibold transition-all ${
              isMockMode
                ? 'bg-indigo-600/30 text-indigo-300 border border-indigo-500/50'
                : 'bg-emerald-600/30 text-emerald-300 border border-emerald-500/50'
            }`}
          >
            {isMockMode ? <ToggleLeft className="w-4 h-4 text-indigo-400" /> : <ToggleRight className="w-4 h-4 text-emerald-400" />}
            <span>{isMockMode ? 'MOCK / DEMO MODE' : 'LIVE API / WS'}</span>
          </button>
        </div>

        {/* Scenario Selectors (Enabled in Mock Mode) */}
        {isMockMode && (
          <div className="flex items-center gap-2 flex-1 overflow-x-auto py-1">
            <div className="flex items-center gap-1 text-slate-400 font-medium shrink-0">
              <Sliders className="w-3.5 h-3.5 text-indigo-400" />
              <span>Demo Scenario:</span>
            </div>
            <div className="flex items-center gap-1.5">
              {scenarioLabels.map((sc) => {
                const isActive = activeScenario === sc.key;
                return (
                  <button
                    key={sc.key}
                    onClick={() => onSelectScenario(sc.key)}
                    className={`px-2.5 py-1 rounded-md text-[11px] font-medium whitespace-nowrap transition-all flex items-center gap-1.5 ${
                      isActive
                        ? 'bg-indigo-600 text-white shadow-sm shadow-indigo-500/50 border border-indigo-400'
                        : 'bg-slate-800/80 text-slate-300 hover:bg-slate-700 border border-slate-700/60'
                    }`}
                  >
                    <Radio className={`w-3 h-3 ${isActive ? 'text-white' : 'text-slate-500'}`} />
                    <span>{sc.label}</span>
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
