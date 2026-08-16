import React, { useState } from 'react';
import { Sliders, ShieldAlert, CheckCircle2, RotateCcw, AlertTriangle, X, Loader2 } from 'lucide-react';

export function ManualOverrideModal({ isOpen, onClose, onApplyOverride }) {
  const [overrideActive, setOverrideActive] = useState(false);
  const [activeOverrideTarget, setActiveOverrideTarget] = useState(null);
  const [isValidating, setIsValidating] = useState(false);

  if (!isOpen) return null;

  const handleForceGreen = async (lane) => {
    setIsValidating(true);
    const overridePayload = {
      active_lane: lane,
      duration: 60,
      priority: 'MANUAL_OPERATOR_OVERRIDE',
      reason: [`Manual priority override initiated by operator for ${lane.toUpperCase()} approach`],
    };

    try {
      await onApplyOverride?.(overridePayload);
      setOverrideActive(true);
      setActiveOverrideTarget(`FORCE GREEN: ${lane.toUpperCase()}`);
    } finally {
      setIsValidating(false);
    }
  };

  const handleAllRed = async () => {
    setIsValidating(true);
    const overridePayload = {
      active_lane: 'none',
      duration: 15,
      priority: 'EMERGENCY_FLUSH',
      reason: ['All-Red emergency junction flush requested by traffic controller operator'],
    };

    try {
      await onApplyOverride?.(overridePayload);
      setOverrideActive(true);
      setActiveOverrideTarget('ALL RED EMERGENCY FLUSH');
    } finally {
      setIsValidating(false);
    }
  };

  const handleReset = async () => {
    setIsValidating(true);
    try {
      await onApplyOverride?.(null); // Reset to adaptive AI
      setOverrideActive(false);
      setActiveOverrideTarget(null);
    } finally {
      setIsValidating(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
      <div className="control-card rounded-2xl p-6 max-w-lg w-full border border-indigo-500/50 shadow-2xl relative">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1 text-slate-400 hover:text-white rounded-lg bg-slate-800/60"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Modal Header */}
        <div className="flex items-center gap-3 pb-4 border-b border-slate-700">
          <div className="p-2.5 bg-amber-500/20 text-amber-400 border border-amber-500/40 rounded-xl">
            <Sliders className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              Operator Manual Signal Override
            </h2>
            <p className="text-xs text-slate-400">
              Server-validated signal preemption — requires backend confirmation
            </p>
          </div>
        </div>

        {/* Override Status Banner */}
        <div className="my-4">
          {isValidating ? (
            <div className="bg-indigo-950/80 border border-indigo-600 rounded-xl p-3 flex items-center gap-3 text-xs text-indigo-200">
              <Loader2 className="w-4 h-4 text-indigo-400 animate-spin shrink-0" />
              <span className="font-semibold">Sending command to server for validation…</span>
            </div>
          ) : overrideActive ? (
            <div className="bg-amber-950/80 border border-amber-600 rounded-xl p-3 flex items-center justify-between text-xs text-amber-200 emergency-pulse">
              <div className="flex items-center gap-2 font-semibold">
                <AlertTriangle className="w-4 h-4 text-amber-400" />
                <span>OVERRIDE ACTIVE: <strong className="text-white uppercase">{activeOverrideTarget}</strong></span>
              </div>
              <button
                onClick={handleReset}
                disabled={isValidating}
                className="px-2.5 py-1 bg-amber-600 text-slate-950 font-bold rounded flex items-center gap-1 hover:bg-amber-500 transition-all disabled:opacity-50"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Reset to AI</span>
              </button>
            </div>
          ) : (
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-3 flex items-center gap-2 text-xs text-emerald-400">
              <CheckCircle2 className="w-4 h-4" />
              <span>Adaptive Decision Engine in full automated control</span>
            </div>
          )}
        </div>

        {/* Force Green Controls Grid */}
        <div className="space-y-3">
          <span className="text-xs font-bold text-slate-300 uppercase tracking-wider block">
            Direct Approach Force Green (60s Duration):
          </span>
          <div className="grid grid-cols-2 gap-2 text-xs">
            {['north', 'south', 'east', 'west'].map((lane) => (
              <button
                key={lane}
                onClick={() => handleForceGreen(lane)}
                disabled={isValidating}
                className="p-3 bg-slate-900 hover:bg-emerald-950/80 border border-slate-700 hover:border-emerald-500 rounded-xl font-bold text-slate-200 hover:text-emerald-300 transition-all flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <span>FORCE GREEN: {lane.toUpperCase()}</span>
              </button>
            ))}
          </div>

          {/* Emergency All-Red Command */}
          <button
            onClick={handleAllRed}
            disabled={isValidating}
            className="w-full p-3 bg-rose-950/90 hover:bg-rose-900 border border-rose-600 rounded-xl font-extrabold text-white text-xs transition-all flex items-center justify-center gap-2 shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <ShieldAlert className="w-4 h-4 text-rose-300" />
            <span>TRIGGER ALL-RED EMERGENCY JUNCTION FLUSH</span>
          </button>
        </div>

        {/* Footer */}
        <div className="mt-5 pt-3 border-t border-slate-800 flex items-center justify-between text-[11px] text-slate-500">
          <span>Operator ID: #TOC-9042</span>
          <button
            onClick={onClose}
            className="px-3 py-1 bg-slate-800 text-slate-300 hover:text-white rounded-lg"
          >
            Close Window
          </button>
        </div>
      </div>
    </div>
  );
}
