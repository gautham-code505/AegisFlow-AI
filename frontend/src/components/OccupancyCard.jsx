import React from 'react';
import { Car, AlertTriangle, Users, Truck } from 'lucide-react';

export function OccupancyCard({ laneName, laneData, isActive, isEmergencyLane }) {
  const vehicleCount = laneData?.vehicle_count || 0;
  const occupancyFraction = laneData?.occupancy || 0;
  const occupancyPercent = Math.round(occupancyFraction * 100);
  const pedestrians = laneData?.pedestrian_count || 0;
  const heavyVehicles = laneData?.heavy_vehicle_count || 0;

  // Semantic color for occupancy bar
  const getOccupancyColor = () => {
    if (isEmergencyLane) return 'bg-rose-500';
    if (occupancyPercent >= 75) return 'bg-rose-500';
    if (occupancyPercent >= 40) return 'bg-amber-500';
    return 'bg-emerald-500';
  };

  const getOccupancyBadge = () => {
    if (isEmergencyLane) return 'text-rose-400 bg-rose-950/80 border-rose-800';
    if (occupancyPercent >= 75) return 'text-rose-300 bg-rose-950/60 border-rose-800/60';
    if (occupancyPercent >= 40) return 'text-amber-300 bg-amber-950/60 border-amber-800/60';
    return 'text-emerald-300 bg-emerald-950/60 border-emerald-800/60';
  };

  return (
    <div
      className={`rounded-xl p-3.5 border transition-all ${
        isEmergencyLane
          ? 'bg-rose-950/40 border-rose-600 emergency-pulse'
          : isActive
          ? 'bg-slate-800/90 border-indigo-500/80 shadow-lg shadow-indigo-950/40'
          : 'bg-slate-900/60 border-slate-800 hover:border-slate-700'
      }`}
    >
      {/* Approach Card Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span
            className={`w-2.5 h-2.5 rounded-full ${
              isActive ? 'bg-emerald-400 animate-pulse' : 'bg-slate-600'
            }`}
          />
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200">
            {laneName} Approach
          </h3>
        </div>
        {isActive && (
          <span className="px-2 py-0.5 text-[10px] font-bold bg-emerald-950 text-emerald-300 border border-emerald-700 rounded">
            ACTIVE GREEN
          </span>
        )}
      </div>

      {/* Primary Metrics Row */}
      <div className="grid grid-cols-2 gap-2 my-2">
        <div className="bg-slate-950/80 rounded-lg p-2 border border-slate-800/80">
          <span className="text-[10px] text-slate-400 font-medium block">Vehicles</span>
          <div className="flex items-center gap-1.5 mt-0.5">
            <Car className="w-4 h-4 text-indigo-400" />
            <span className="text-base font-bold font-mono text-white">{vehicleCount}</span>
          </div>
        </div>

        <div className="bg-slate-950/80 rounded-lg p-2 border border-slate-800/80">
          <span className="text-[10px] text-slate-400 font-medium block">Occupancy</span>
          <div className="flex items-center gap-1.5 mt-0.5">
            <span className={`text-base font-bold font-mono ${getOccupancyBadge().split(' ')[0]}`}>
              {occupancyPercent}%
            </span>
          </div>
        </div>
      </div>

      {/* Dynamic Occupancy Progress Bar */}
      <div className="w-full bg-slate-950 rounded-full h-2 overflow-hidden my-2 border border-slate-800">
        <div
          className={`h-full transition-all duration-500 rounded-full ${getOccupancyColor()}`}
          style={{ width: `${Math.min(occupancyPercent, 100)}%` }}
        />
      </div>

      {/* Sub-Metrics Row */}
      <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1 border-t border-slate-800/60 mt-2">
        <span className="flex items-center gap-1">
          <Truck className="w-3 h-3 text-slate-500" />
          <span>Heavy: <strong>{heavyVehicles}</strong></span>
        </span>
        <span className="flex items-center gap-1">
          <Users className="w-3 h-3 text-slate-500" />
          <span>Peds: <strong>{pedestrians}</strong></span>
        </span>
      </div>
    </div>
  );
}
