import React from 'react';
import { SCENARIOS } from '../services/mockData';
import { Sliders, Radio, ToggleLeft, ToggleRight } from 'lucide-react';

export function ScenarioSelector({ activeScenario, onSelectScenario, isMockMode, onToggleMockMode }) {
  const scenarioLabels = [
    { key: SCENARIOS.NORMAL, label: 'Normal Balanced', badge: 'Normal' },
    { key: SCENARIOS.HEAVY_NORTH, label: 'Heavy North', badge: 'High Density' },
    { key: SCENARIOS.EMERGENCY_EAST, label: 'Emergency East', badge: 'Emergency' },
    { key: SCENARIOS.HEAVY_SOUTH, label: 'Heavy South', badge: 'Queue Priority' },
    { key: SCENARIOS.SYSTEM_WARNING, label: 'System Warning', badge: 'Fallback' },
  ];

  return (
    <div className="control-card rounded-xl p-3 mb-4 text-xs">
      <div className="flex flex-wrap items-center justify-between gap-3">
        {/* Mode Toggle */}
        <div className="flex items-center gap-2">
          <span className="text-slate-400 font-medium">Input:</span>
          <button
            onClick={() => onToggleMockMode(!isMockMode)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-semibold transition-all ${
              isMockMode
                ? 'bg-indigo-600/30 text-indigo-300 border border-indigo-500/50'
                : 'bg-emerald-600/30 text-emerald-300 border border-emerald-500/50'
            }`}
          >
            {isMockMode ? <ToggleLeft className="w-4 h-4 text-indigo-400" /> : <ToggleRight className="w-4 h-4 text-emerald-400" />}
            <span>{isMockMode ? 'DEMO MODE' : 'REAL INPUT'}</span>
          </button>
        </div>

        {/* Scenario Selectors (Only visible in Mock Mode) */}
        {isMockMode && (
          <div className="flex items-center gap-2 flex-1 overflow-x-auto py-1">
            <div className="flex items-center gap-1 text-slate-400 font-medium shrink-0">
              <Sliders className="w-3.5 h-3.5 text-indigo-400" />
              <span>Scenario:</span>
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

        {/* Real Input guidance */}
        {!isMockMode && (
          <div className="flex items-center gap-2 text-slate-400">
            <span>Upload videos/images per approach above • WebSocket receives real YOLO results</span>
          </div>
        )}
      </div>
    </div>
  );
}
