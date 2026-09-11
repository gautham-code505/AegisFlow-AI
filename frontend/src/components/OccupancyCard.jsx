import React from 'react';
import { Car, Clock, Activity, AlertCircle } from 'lucide-react';

export function OccupancyCard({ laneName, laneData, hasTrackingData, approachStatus, isActive, isEmergencyLane }) {
  const hasInput = approachStatus !== 'WAITING_FOR_INPUT';
  
  // Basic metrics
  const vehicleCount = hasInput ? (laneData?.vehicle_count ?? '-') : '-';
  const occupancyPercent = hasInput ? (laneData?.occupancy !== undefined ? Math.round(laneData.occupancy * 100) : '-') : '-';
  
  // Tracking metrics
  const queued = hasTrackingData ? (laneData?.queued_vehicle_count ?? 0) : null;
  const moving = hasTrackingData ? (laneData?.moving_vehicle_count ?? 0) : null;
  const avgWait = hasTrackingData ? (laneData?.observed_average_wait ?? 0).toFixed(1) : null;
  const maxWait = hasTrackingData ? (laneData?.observed_max_wait ?? 0).toFixed(1) : null;

  return (
    <div
      className={`rounded-xl p-3.5 border transition-all flex flex-col h-full ${
        isEmergencyLane
          ? 'bg-rose-950/40 border-rose-600 emergency-pulse'
          : isActive
          ? 'bg-slate-800/90 border-indigo-500/80 shadow-lg shadow-indigo-950/40'
          : 'bg-slate-900/60 border-slate-800'
      }`}
    >
      {/* Approach Card Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span
            className={`w-2.5 h-2.5 rounded-full ${
              isActive ? 'bg-emerald-400 animate-pulse' : 'bg-slate-600'
            }`}
          />
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200">
            {laneName}
          </h3>
        </div>
        {isActive && (
          <span className="px-2 py-0.5 text-[10px] font-bold bg-emerald-950 text-emerald-300 border border-emerald-700 rounded">
            ACTIVE
          </span>
        )}
      </div>

      {!hasInput ? (
        <div className="flex-1 flex flex-col items-center justify-center py-4 opacity-50">
          <AlertCircle className="w-6 h-6 text-slate-500 mb-2" />
          <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">No Input Data</span>
        </div>
      ) : hasTrackingData ? (
        <div className="flex-1 flex flex-col gap-2">
          {/* Tracking Mode Grid */}
          <div className="grid grid-cols-2 gap-2">
            <div className="bg-slate-950/80 rounded border border-slate-800/80 p-2">
               <span className="text-[10px] text-slate-400 font-medium block leading-tight">Estimated Queue</span>
               <div className="flex items-center gap-1.5 mt-0.5">
                 <Car className="w-3.5 h-3.5 text-rose-400" />
                 <span className="text-sm font-bold font-mono text-white">{queued}</span>
               </div>
            </div>
            <div className="bg-slate-950/80 rounded border border-slate-800/80 p-2">
               <span className="text-[10px] text-slate-400 font-medium block leading-tight">Estimated Moving Vehicles</span>
               <div className="flex items-center gap-1.5 mt-0.5">
                 <Activity className="w-3.5 h-3.5 text-emerald-400" />
                 <span className="text-sm font-bold font-mono text-white">{moving}</span>
               </div>
            </div>
            <div className="bg-slate-950/80 rounded border border-slate-800/80 p-2">
               <span className="text-[10px] text-slate-400 font-medium block leading-tight">Estimated Avg. Wait</span>
               <div className="flex items-center gap-1.5 mt-0.5">
                 <Clock className="w-3.5 h-3.5 text-amber-400" />
                 <span className="text-sm font-bold font-mono text-white">{avgWait}s</span>
               </div>
            </div>
            <div className="bg-slate-950/80 rounded border border-slate-800/80 p-2">
               <span className="text-[10px] text-slate-400 font-medium block leading-tight">Estimated Max Wait</span>
               <div className="flex items-center gap-1.5 mt-0.5">
                 <Clock className="w-3.5 h-3.5 text-rose-400" />
                 <span className="text-sm font-bold font-mono text-white">{maxWait}s</span>
               </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="flex-1 flex flex-col gap-2">
          {/* Fallback Mode Grid */}
          <div className="bg-amber-950/20 border border-amber-900/40 rounded px-2 py-1 mb-1">
             <span className="text-[9px] font-bold text-amber-500/80 uppercase tracking-widest block text-center">
               Tracking Unavailable
             </span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div className="bg-slate-950/80 rounded border border-slate-800/80 p-2">
               <span className="text-[10px] text-slate-400 font-medium block leading-tight">Observed Vehicles</span>
               <div className="flex items-center gap-1.5 mt-0.5">
                 <Car className="w-3.5 h-3.5 text-indigo-400" />
                 <span className="text-sm font-bold font-mono text-white">{vehicleCount}</span>
               </div>
            </div>
            <div className="bg-slate-950/80 rounded border border-slate-800/80 p-2">
               <span className="text-[10px] text-slate-400 font-medium block leading-tight">Demand Ratio</span>
               <div className="flex items-center gap-1.5 mt-0.5">
                 <Activity className="w-3.5 h-3.5 text-amber-400" />
                 <span className="text-sm font-bold font-mono text-white">{occupancyPercent}%</span>
               </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
