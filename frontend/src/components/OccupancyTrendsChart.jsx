import React from 'react';
import { TrendingUp, BarChart2 } from 'lucide-react';

export function OccupancyTrendsChart({ trafficState }) {
  // Generate sample historical trend data points based on current traffic state
  const northOcc = Math.round((trafficState?.lanes?.north?.occupancy || 0.42) * 100);
  const southOcc = Math.round((trafficState?.lanes?.south?.occupancy || 0.28) * 100);
  const eastOcc = Math.round((trafficState?.lanes?.east?.occupancy || 0.35) * 100);
  const westOcc = Math.round((trafficState?.lanes?.west?.occupancy || 0.18) * 100);

  // Dynamic SVG polyline points calculation for sparklines
  const points = [
    { time: 'T-25s', n: Math.max(10, northOcc - 15), s: Math.max(5, southOcc + 10), e: Math.max(8, eastOcc - 8), w: Math.max(4, westOcc + 5) },
    { time: 'T-20s', n: Math.max(12, northOcc - 8), s: Math.max(6, southOcc + 5), e: Math.max(10, eastOcc + 4), w: Math.max(5, westOcc - 2) },
    { time: 'T-15s', n: Math.max(15, northOcc - 12), s: Math.max(4, southOcc - 4), e: Math.max(12, eastOcc + 8), w: Math.max(6, westOcc + 2) },
    { time: 'T-10s', n: Math.max(20, northOcc - 4), s: Math.max(8, southOcc - 2), e: Math.max(15, eastOcc - 2), w: Math.max(5, westOcc - 1) },
    { time: 'T-5s',  n: Math.max(18, northOcc + 2), s: Math.max(6, southOcc + 1), e: Math.max(14, eastOcc + 2), w: Math.max(4, westOcc + 1) },
    { time: 'NOW',   n: northOcc, s: southOcc, e: eastOcc, w: westOcc },
  ];

  // Map 0-100 to SVG Y coords (height 80px)
  const getY = (val) => 70 - (val / 100) * 60;
  const getPolyline = (key) => points.map((p, idx) => `${idx * 50 + 10},${getY(p[key])}`).join(' ');

  return (
    <div className="control-card rounded-xl p-4 flex flex-col justify-between h-full">
      <div className="flex items-center justify-between pb-3 border-b border-slate-700/80 mb-3">
        <div className="flex items-center gap-2">
          <div className="p-1 bg-indigo-500/20 text-indigo-400 rounded">
            <TrendingUp className="w-4 h-4" />
          </div>
          <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wider">
            Approach Occupancy Trends (Real-Time)
          </h2>
        </div>
        <span className="text-xs font-mono text-slate-400 flex items-center gap-1">
          <BarChart2 className="w-3.5 h-3.5 text-indigo-400" />
          <span>30s TELEMETRY</span>
        </span>
      </div>

      {/* SVG Real-Time Multi-Approach Sparkline Chart */}
      <div className="bg-slate-950/90 rounded-lg p-3 border border-slate-800 my-1 relative">
        <svg viewBox="0 0 270 80" className="w-full h-24 overflow-visible">
          {/* Grid lines */}
          <line x1="0" y1="10" x2="270" y2="10" stroke="#334155" strokeDasharray="2,2" opacity="0.4" />
          <line x1="0" y1="40" x2="270" y2="40" stroke="#334155" strokeDasharray="2,2" opacity="0.4" />
          <line x1="0" y1="70" x2="270" y2="70" stroke="#334155" strokeDasharray="2,2" opacity="0.4" />

          {/* Lines for each lane */}
          <polyline fill="none" stroke="#6366f1" strokeWidth="2" points={getPolyline('n')} />
          <polyline fill="none" stroke="#10b981" strokeWidth="2" points={getPolyline('s')} />
          <polyline fill="none" stroke="#f59e0b" strokeWidth="2" points={getPolyline('e')} />
          <polyline fill="none" stroke="#06b6d4" strokeWidth="2" points={getPolyline('w')} />

          {/* Current values dots */}
          <circle cx="260" cy={getY(northOcc)} r="4" fill="#6366f1" />
          <circle cx="260" cy={getY(southOcc)} r="4" fill="#10b981" />
          <circle cx="260" cy={getY(eastOcc)} r="4" fill="#f59e0b" />
          <circle cx="260" cy={getY(westOcc)} r="4" fill="#06b6d4" />
        </svg>

        {/* X-Axis labels */}
        <div className="flex justify-between text-[10px] text-slate-500 font-mono mt-1 pt-1 border-t border-slate-800/80">
          {points.map((p, idx) => (
            <span key={idx}>{p.time}</span>
          ))}
        </div>
      </div>

      {/* Chart Legend */}
      <div className="grid grid-cols-4 gap-2 text-[11px] pt-2 border-t border-slate-800/60">
        <div className="flex items-center gap-1.5 font-semibold text-indigo-400">
          <span className="w-2.5 h-2.5 rounded-full bg-indigo-500" />
          <span>NORTH: {northOcc}%</span>
        </div>
        <div className="flex items-center gap-1.5 font-semibold text-emerald-400">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
          <span>SOUTH: {southOcc}%</span>
        </div>
        <div className="flex items-center gap-1.5 font-semibold text-amber-400">
          <span className="w-2.5 h-2.5 rounded-full bg-amber-500" />
          <span>EAST: {eastOcc}%</span>
        </div>
        <div className="flex items-center gap-1.5 font-semibold text-cyan-400">
          <span className="w-2.5 h-2.5 rounded-full bg-cyan-500" />
          <span>WEST: {westOcc}%</span>
        </div>
      </div>
    </div>
  );
}
