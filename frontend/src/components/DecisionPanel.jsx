import React from 'react';
import { Brain, CheckCircle2, Sparkles, Clock, TrendingUp } from 'lucide-react';

export function DecisionPanel({ signalDecision }) {
  if (!signalDecision) {
    return (
      <div className="control-card rounded-xl p-4 flex flex-col justify-between h-full">
        <div className="flex items-center justify-between pb-3 border-b border-slate-700/80">
          <div className="flex items-center gap-2">
            <div className="p-1 bg-indigo-500/20 text-indigo-400 rounded">
              <Brain className="w-4 h-4" />
            </div>
            <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wider">
              AI Decision Engine
            </h2>
          </div>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <p className="text-xs text-slate-500 italic uppercase font-bold tracking-widest">Waiting for Traffic Data</p>
        </div>
      </div>
    );
  }

  const activeLane = signalDecision.selected_lane;
  const duration = signalDecision.duration;
  const priority = signalDecision.priority || 'NORMAL';
  const reasons = signalDecision.reasons || [];
  const scoreBreakdown = signalDecision.score_breakdown || null;

  const getPriorityBadge = () => {
    const p = String(priority).toUpperCase();
    if (p.includes('EMERGENCY')) return 'bg-rose-950 text-rose-300 border-rose-700 emergency-pulse';
    if (p.includes('HIGH') || p.includes('DEMAND')) return 'bg-amber-950 text-amber-300 border-amber-700';
    if (p.includes('FALLBACK')) return 'bg-orange-950 text-orange-300 border-orange-700';
    if (p.includes('MANUAL')) return 'bg-violet-950 text-violet-300 border-violet-700';
    return 'bg-emerald-950 text-emerald-300 border-emerald-700';
  };

  // Find max score for bar scaling
  const maxScore = scoreBreakdown
    ? Math.max(...Object.values(scoreBreakdown).map(s => s.total_score || 0), 1)
    : 1;

  return (
    <div className="control-card rounded-xl p-4 flex flex-col justify-between h-full">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-700/80">
        <div className="flex items-center gap-2">
          <div className="p-1 bg-indigo-500/20 text-indigo-400 rounded">
            <Brain className="w-4 h-4" />
          </div>
          <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wider">
            AI Decision Engine
          </h2>
        </div>
        <span className="flex items-center gap-1 text-xs text-indigo-300 font-mono">
          <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
          <span>ADAPTIVE</span>
        </span>
      </div>

      {/* Decision Overview */}
      <div className="grid grid-cols-2 gap-2 my-3">
        <div className="bg-slate-900/90 rounded-lg p-2.5 border border-slate-800">
          <span className="text-[10px] text-slate-400 font-medium block">Selected Approach</span>
          <span className="text-base font-extrabold uppercase text-emerald-400 font-mono block mt-0.5">
            {activeLane}
          </span>
        </div>
        <div className="bg-slate-900/90 rounded-lg p-2.5 border border-slate-800">
          <span className="text-[10px] text-slate-400 font-medium block">Green Duration</span>
          <div className="flex items-center gap-1 mt-0.5 font-mono">
            <Clock className="w-3.5 h-3.5 text-indigo-400" />
            <span className="text-base font-bold text-white">{duration}s</span>
          </div>
        </div>
      </div>

      {/* Priority Badge */}
      <div className="mb-3">
        <div className={`px-3 py-1.5 rounded-lg border text-xs font-semibold flex items-center justify-between ${getPriorityBadge()}`}>
          <span>PRIORITY: {String(priority).toUpperCase()}</span>
          <span className="text-[10px] font-mono opacity-80">Safety Validated</span>
        </div>
      </div>

      {/* Score Breakdown Bars */}
      {scoreBreakdown && (
        <div className="bg-slate-950/90 rounded-lg p-3 border border-slate-800 mb-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-bold text-slate-300 uppercase tracking-wide flex items-center gap-1.5">
              <TrendingUp className="w-3.5 h-3.5 text-indigo-400" />
              <span>Per-Approach Score Breakdown</span>
            </span>
            {String(priority).toUpperCase() === 'EMERGENCY' && (
              <span className="px-1.5 py-0.5 bg-rose-950 text-rose-300 border border-rose-700 rounded text-[9px] font-bold uppercase animate-pulse">
                EMERGENCY OVERRIDE
              </span>
            )}
          </div>
          <div className="space-y-1.5">
            {Object.entries(scoreBreakdown)
              .sort((a, b) => (b[1].total_score || 0) - (a[1].total_score || 0))
              .map(([lane, scores]) => {
                const isSelected = lane === activeLane;
                const pct = Math.round(((scores.total_score || 0) / maxScore) * 100);
                return (
                  <div key={lane} className="flex items-center gap-2">
                    <span className={`w-12 text-[10px] font-bold uppercase font-mono ${isSelected ? 'text-emerald-400' : 'text-slate-400'}`}>
                      {lane}
                    </span>
                    <div className="flex-1 bg-slate-900 rounded-full h-3 overflow-hidden border border-slate-800">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${isSelected ? 'bg-emerald-500' : 'bg-indigo-600/60'}`}
                        style={{ width: `${Math.max(pct, 2)}%` }}
                      />
                    </div>
                    <span className={`text-[10px] font-mono font-bold w-10 text-right ${isSelected ? 'text-emerald-400' : 'text-slate-400'}`}>
                      {(scores.total_score || 0).toFixed(2)}
                    </span>
                  </div>
                );
              })}
          </div>
          {/* Canonical scoring model from backend */}
          <div className="mt-2 pt-1.5 border-t border-slate-800/80 flex items-center justify-between text-[10px] text-slate-400 font-mono">
            <span>Model:</span>
            <span>
              {Object.values(scoreBreakdown)[0]?.used_tracking
                ? 'Tracking Mode (Est. Queue × 0.60 + Est. Wait × 0.40)'
                : 'Fallback Mode (Demand Ratio × 0.50 + Vehicles × 0.50)'}
            </span>
          </div>
        </div>
      )}

      {/* WHY — Decision Reasoning */}
      <div className="bg-slate-950/90 rounded-lg p-3 border border-slate-800 flex-1 flex flex-col justify-center">
        <span className="text-xs font-bold text-slate-300 uppercase tracking-wide block mb-2 flex items-center gap-1.5">
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
          <span>Why This Decision?</span>
        </span>
        {reasons.length > 0 ? (
          <ul className="space-y-1.5 text-xs text-slate-300">
            {reasons.map((reason, idx) => (
              <li key={idx} className="flex items-start gap-2 bg-slate-900/60 p-2 rounded border border-slate-800/80">
                <span className="text-indigo-400 font-bold shrink-0">•</span>
                <span className="leading-snug">{reason}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-slate-500 italic">Waiting for decision data from backend...</p>
        )}
      </div>

      {/* Footer */}
      <div className="mt-3 pt-2 border-t border-slate-800/60 text-[11px] text-slate-400 flex items-center justify-between">
        <span>Deterministic Rule Engine</span>
        <span className="text-emerald-400 font-semibold">Real-Time Adaptive Control</span>
      </div>
    </div>
  );
}
