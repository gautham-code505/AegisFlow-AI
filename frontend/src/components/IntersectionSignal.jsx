import React from 'react';
import { Timer, ArrowUp, ArrowDown, ArrowLeft, ArrowRight, ShieldAlert } from 'lucide-react';

export function IntersectionSignal({ signalState, signalDecision, trafficState }) {
  const activeLane = signalDecision?.selected_lane || 'north';
  const remainingSeconds = signalState?.remaining_seconds ?? 30;
  const isEmergency = trafficState?.emergency?.detected;

  const getSignalColor = (lane) => {
    const state = signalState?.[lane]?.toUpperCase() || 'RED';
    if (state === 'GREEN') return 'bg-emerald-500 text-emerald-950 border-emerald-400 traffic-green-glow';
    if (state === 'YELLOW') return 'bg-amber-500 text-amber-950 border-amber-400 traffic-yellow-glow';
    return 'bg-rose-500/80 text-rose-100 border-rose-600/80 traffic-red-glow';
  };

  const getSignalDot = (lane) => {
    const state = signalState?.[lane]?.toUpperCase() || 'RED';
    if (state === 'GREEN') return 'bg-emerald-400 animate-pulse';
    if (state === 'YELLOW') return 'bg-amber-400 animate-ping';
    return 'bg-rose-500';
  };

  return (
    <div className="control-card rounded-xl p-4 flex flex-col justify-between h-full">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-700/80">
        <div className="flex items-center gap-2">
          <div className="p-1 bg-emerald-500/20 text-emerald-400 rounded">
            <Timer className="w-4 h-4" />
          </div>
          <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wider">
            Intersection Signal Matrix
          </h2>
        </div>
        <span className="text-xs font-mono text-slate-400">4-WAY CONTROLLER</span>
      </div>

      {/* 2D Intersection Junction Map */}
      <div className="relative my-4 flex-1 flex items-center justify-center min-h-[260px]">
        {/* Intersection Road Overlay Canvas */}
        <div className="relative w-64 h-64 bg-slate-900 border-2 border-slate-700/80 rounded-2xl flex items-center justify-center overflow-hidden shadow-2xl">
          {/* Vertical Road (North - South) */}
          <div className="absolute inset-y-0 w-24 bg-slate-800/90 border-x border-slate-700/60 flex flex-col justify-between items-center py-2">
            <div className="w-0.5 h-full border-r border-dashed border-slate-600/60" />
          </div>

          {/* Horizontal Road (East - West) */}
          <div className="absolute inset-x-0 h-24 bg-slate-800/90 border-y border-slate-700/60 flex justify-between items-center px-2">
            <div className="w-full h-0.5 border-b border-dashed border-slate-600/60" />
          </div>

          {/* Central Junction Square */}
          <div className="absolute w-24 h-24 bg-slate-950 border border-indigo-500/40 rounded-lg flex flex-col items-center justify-center z-10 p-2 text-center shadow-lg">
            {isEmergency ? (
              <div className="text-rose-400 flex flex-col items-center animate-bounce">
                <ShieldAlert className="w-6 h-6" />
                <span className="text-[10px] font-bold mt-0.5 uppercase tracking-tighter">EMERGENCY</span>
              </div>
            ) : (
              <>
                <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">ACTIVE</span>
                <span className="text-sm font-bold text-white uppercase tracking-wider">{activeLane}</span>
                <div className="flex items-center gap-1 mt-1 text-emerald-400 font-mono font-bold text-base">
                  <span>{remainingSeconds}</span>
                  <span className="text-[10px] font-normal text-slate-400">s</span>
                </div>
              </>
            )}
          </div>

          {/* North Signal Head */}
          <div className="absolute top-2 z-20 flex flex-col items-center">
            <div className={`px-2.5 py-1 rounded-md text-[11px] font-bold border flex items-center gap-1.5 ${getSignalColor('north')}`}>
              <span className={`w-2 h-2 rounded-full ${getSignalDot('north')}`} />
              <span>NORTH: {signalState?.north || 'RED'}</span>
            </div>
            {activeLane === 'north' && <ArrowDown className="w-4 h-4 text-emerald-400 animate-bounce mt-1" />}
          </div>

          {/* South Signal Head */}
          <div className="absolute bottom-2 z-20 flex flex-col items-center">
            {activeLane === 'south' && <ArrowUp className="w-4 h-4 text-emerald-400 animate-bounce mb-1" />}
            <div className={`px-2.5 py-1 rounded-md text-[11px] font-bold border flex items-center gap-1.5 ${getSignalColor('south')}`}>
              <span className={`w-2 h-2 rounded-full ${getSignalDot('south')}`} />
              <span>SOUTH: {signalState?.south || 'RED'}</span>
            </div>
          </div>

          {/* West Signal Head */}
          <div className="absolute left-2 z-20 flex items-center">
            <div className={`px-2 py-1 rounded-md text-[10px] font-bold border flex items-center gap-1 ${getSignalColor('west')}`}>
              <span className={`w-2 h-2 rounded-full ${getSignalDot('west')}`} />
              <span>WEST</span>
            </div>
            {activeLane === 'west' && <ArrowRight className="w-4 h-4 text-emerald-400 animate-pulse ml-1" />}
          </div>

          {/* East Signal Head */}
          <div className="absolute right-2 z-20 flex items-center">
            {activeLane === 'east' && <ArrowLeft className="w-4 h-4 text-emerald-400 animate-pulse mr-1" />}
            <div className={`px-2 py-1 rounded-md text-[10px] font-bold border flex items-center gap-1 ${getSignalColor('east')}`}>
              <span className={`w-2 h-2 rounded-full ${getSignalDot('east')}`} />
              <span>EAST</span>
            </div>
          </div>
        </div>
      </div>

      {/* Active Phase Countdown Banner */}
      <div className="bg-slate-900/80 border border-slate-700/60 rounded-lg p-2.5 flex items-center justify-between text-xs">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-ping" />
          <span className="text-slate-300 font-medium">
            Active Phase: <strong className="text-emerald-400 uppercase">{activeLane} APPROACH</strong>
          </span>
        </div>
        <div className="font-mono text-slate-300">
          Green Allocation: <strong className="text-white">{signalDecision?.duration || 30}s</strong>
        </div>
      </div>
    </div>
  );
}
