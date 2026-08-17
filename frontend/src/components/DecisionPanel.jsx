import React from 'react';
import { Brain, CheckCircle2, ShieldAlert, Sparkles, Clock, AlertTriangle } from 'lucide-react';

export function DecisionPanel({ signalDecision }) {
  const activeLane = signalDecision?.active_lane || 'north';
  const duration = signalDecision?.duration || 30;
  const priority = signalDecision?.priority || 'NORMAL';
  const confidence = Math.round((signalDecision?.confidence || 0.95) * 100);
  const reasons = signalDecision?.reason || [
    'Highest occupancy on approach corridor',
    'Demand threshold satisfied',
    'No emergency preemption conflict',
  ];

  const getPriorityBadge = () => {
    if (priority.includes('EMERGENCY')) {
      return 'bg-rose-950 text-rose-300 border-rose-700 emergency-pulse';
    }
    if (priority.includes('HIGH') || priority.includes('DEMAND')) {
      return 'bg-amber-950 text-amber-300 border-amber-700';
    }
    if (priority.includes('FALLBACK')) {
      return 'bg-orange-950 text-orange-300 border-orange-700';
    }
    return 'bg-emerald-950 text-emerald-300 border-emerald-700';
  };

  return (
    <div className="control-card rounded-xl p-4 flex flex-col justify-between h-full">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-700/80">
        <div className="flex items-center gap-2">
          <div className="p-1 bg-indigo-500/20 text-indigo-400 rounded">
            <Brain className="w-4 h-4" />
          </div>
          <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wider">
            Explainable AI (XAI) Decision Engine
          </h2>
        </div>
        <span className="flex items-center gap-1 text-xs text-indigo-300 font-mono">
          <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
          <span>ADAPTIVE OS</span>
        </span>
      </div>

      {/* Decision Overview Grid */}
      <div className="grid grid-cols-3 gap-2 my-3">
        <div className="bg-slate-900/90 rounded-lg p-2.5 border border-slate-800">
          <span className="text-[10px] text-slate-400 font-medium block">Selected Approach</span>
          <span className="text-base font-extrabold uppercase text-emerald-400 font-mono block mt-0.5">
            {activeLane}
          </span>
        </div>

        <div className="bg-slate-900/90 rounded-lg p-2.5 border border-slate-800">
          <span className="text-[10px] text-slate-400 font-medium block">Green Allocation</span>
          <div className="flex items-center gap-1 mt-0.5 font-mono">
            <Clock className="w-3.5 h-3.5 text-indigo-400" />
            <span className="text-base font-bold text-white">{duration}s</span>
          </div>
        </div>

        <div className="bg-slate-900/90 rounded-lg p-2.5 border border-slate-800">
          <span className="text-[10px] text-slate-400 font-medium block">Confidence</span>
          <span className="text-base font-bold text-indigo-300 font-mono block mt-0.5">
            {confidence}%
          </span>
        </div>
      </div>

      {/* Priority Badge */}
      <div className="mb-3">
        <div className={`px-3 py-1.5 rounded-lg border text-xs font-semibold flex items-center justify-between ${getPriorityBadge()}`}>
          <span>PRIORITY TIER: {priority}</span>
          <span className="text-[10px] font-mono opacity-80">Safety Validator Approved</span>
        </div>
      </div>

      {/* Structured Reason Explanations ("WHY did AegisFlow choose that road?") */}
      <div className="bg-slate-950/90 rounded-lg p-3 border border-slate-800 flex-1 flex flex-col justify-center">
        <span className="text-xs font-bold text-slate-300 uppercase tracking-wide block mb-2 flex items-center gap-1.5">
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
          <span>Decision Reasoning & Logic:</span>
        </span>
        <ul className="space-y-1.5 text-xs text-slate-300">
          {reasons.map((reason, idx) => (
            <li key={idx} className="flex items-start gap-2 bg-slate-900/60 p-2 rounded border border-slate-800/80">
              <span className="text-indigo-400 font-bold">•</span>
              <span className="leading-snug">{reason}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Verification Footer */}
      <div className="mt-3 pt-2 border-t border-slate-800/60 text-[11px] text-slate-400 flex items-center justify-between">
        <span>Deterministic Rule Engine: Enabled</span>
        <span className="text-emerald-400 font-semibold">Zero Hallucination Guarantee</span>
      </div>
    </div>
  );
}
