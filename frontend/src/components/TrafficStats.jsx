import React from 'react';
import { OccupancyCard } from './OccupancyCard';
import { Activity } from 'lucide-react';

export function TrafficStats({ trafficState, signalDecision }) {
  const activeLane = signalDecision?.active_lane || 'north';
  const emergencyLane = trafficState?.emergency?.detected ? trafficState.emergency.lane : null;

  const lanes = [
    { key: 'north', label: 'North' },
    { key: 'south', label: 'South' },
    { key: 'east', label: 'East' },
    { key: 'west', label: 'West' },
  ];

  return (
    <div className="control-card rounded-xl p-4">
      <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-700/80">
        <div className="flex items-center gap-2">
          <div className="p-1 bg-indigo-500/20 text-indigo-400 rounded">
            <Activity className="w-4 h-4" />
          </div>
          <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wider">
            4-Approach Traffic State & Density
          </h2>
        </div>
        <span className="text-xs font-mono text-slate-400">REAL-TIME OCCUPANCY</span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {lanes.map((lane) => (
          <OccupancyCard
            key={lane.key}
            laneName={lane.label}
            laneData={trafficState?.lanes?.[lane.key]}
            isActive={activeLane === lane.key}
            isEmergencyLane={emergencyLane === lane.key}
          />
        ))}
      </div>
    </div>
  );
}
