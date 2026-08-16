import React from 'react';
import { Terminal, Clock, ShieldAlert, Cpu, Activity } from 'lucide-react';

export function EventLog({ events }) {
  const getEventBadge = (type) => {
    if (type?.includes('EMERGENCY') || type?.includes('PREEMPTION')) {
      return 'bg-rose-950 text-rose-300 border-rose-800';
    }
    if (type?.includes('WARN') || type?.includes('QUEUE')) {
      return 'bg-amber-950 text-amber-300 border-amber-800';
    }
    if (type?.includes('DECISION') || type?.includes('PRIORITY')) {
      return 'bg-indigo-950 text-indigo-300 border-indigo-800';
    }
    return 'bg-slate-900 text-slate-300 border-slate-700';
  };

  return (
    <div className="control-card rounded-xl p-4 flex flex-col justify-between h-full min-h-[220px]">
      <div className="flex items-center justify-between pb-2.5 border-b border-slate-700/80 mb-3">
        <div className="flex items-center gap-2">
          <div className="p-1 bg-indigo-500/20 text-indigo-400 rounded">
            <Terminal className="w-4 h-4" />
          </div>
          <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wider">
            Real-Time Audit & Event Log
          </h2>
        </div>
        <span className="text-xs font-mono text-slate-400">LIVE FEED</span>
      </div>

      {/* Event Items Feed Container */}
      <div className="overflow-y-auto max-h-[160px] pr-1 space-y-2 font-mono text-xs flex-1">
        {events && events.length > 0 ? (
          events.map((item) => (
            <div
              key={item.id || item.timestamp}
              className="bg-slate-950/80 p-2 rounded-lg border border-slate-800/80 flex items-start gap-2 justify-between"
            >
              <div className="flex items-start gap-2">
                <span className="text-indigo-400 font-semibold text-[11px] shrink-0 pt-0.5 flex items-center gap-1">
                  <Clock className="w-3 h-3 text-slate-500" />
                  {item.timestamp}
                </span>
                <span className="text-slate-300 leading-tight text-[11px]">{item.message}</span>
              </div>
              <span className={`px-2 py-0.5 rounded text-[9px] font-bold border uppercase shrink-0 ${getEventBadge(item.type)}`}>
                {item.type}
              </span>
            </div>
          ))
        ) : (
          <div className="text-center py-6 text-slate-500 text-xs italic">
            No events recorded yet. Waiting for intersection telemetry...
          </div>
        )}
      </div>

      <div className="mt-2 pt-2 border-t border-slate-800/60 flex items-center justify-between text-[10px] text-slate-500">
        <span>Persistent Log Buffer: 50 Records</span>
        <span>Auto-sync: Active</span>
      </div>
    </div>
  );
}
