import React from 'react';
import { Cpu, WifiOff, ShieldCheck, MapPin, Sliders } from 'lucide-react';

export function Header({ isMockMode, wsStatus, onOpenOverrideModal }) {
  return (
    <header className="control-card rounded-xl p-4 mb-4">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        {/* Title & Brand */}
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-indigo-600/20 border border-indigo-500/40 rounded-lg text-indigo-400">
            <Cpu className="w-6 h-6 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
                AEGISFLOW AI
              </h1>
              <span className="px-2 py-0.5 text-[10px] font-semibold bg-indigo-900/60 text-indigo-300 border border-indigo-700/60 rounded">
                v1.0 MVP
              </span>
            </div>
            <p className="text-xs text-slate-400 font-medium">
              Offline Intelligent Intersection Operating System — SmartAIthon 2026
            </p>
          </div>
        </div>

        {/* System Badges & Actions */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          {/* Offline First Indicator */}
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-950/60 border border-emerald-700/50 text-emerald-300 font-semibold shadow-inner">
            <WifiOff className="w-3.5 h-3.5 text-emerald-400" />
            <span>● LOCAL / OFFLINE MODE</span>
            <span className="text-[10px] text-emerald-400/80 font-normal border-l border-emerald-700/60 pl-1.5 ml-0.5">
              No Internet Required
            </span>
          </div>

          {/* Location Badge */}
          <div className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-slate-800/80 border border-slate-700 text-slate-300">
            <MapPin className="w-3.5 h-3.5 text-indigo-400" />
            <span>Junction Demo #01</span>
          </div>

          {/* Live vs Mock Status Badge */}
          <div className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-slate-800/80 border border-slate-700">
            <ShieldCheck className="w-3.5 h-3.5 text-indigo-400" />
            <span className="text-slate-300 font-medium">
              {isMockMode ? (
                <span className="text-amber-400">Mock Data Mode</span>
              ) : (
                <span className={wsStatus === 'CONNECTED' ? 'text-emerald-400' : 'text-rose-400'}>
                  WS: {wsStatus}
                </span>
              )}
            </span>
          </div>

          {/* Manual Override Operator Button */}
          <button
            onClick={onOpenOverrideModal}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500/20 text-amber-300 border border-amber-500/50 hover:bg-amber-500/40 transition-all font-semibold"
          >
            <Sliders className="w-3.5 h-3.5 text-amber-400" />
            <span>Manual Override UI</span>
          </button>
        </div>
      </div>
    </header>
  );
}
