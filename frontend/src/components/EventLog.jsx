import React, { useState, useMemo } from 'react';
import { Terminal, Clock, ShieldAlert, Activity, AlertTriangle, Zap, Shield, FileOutput, Server } from 'lucide-react';

export function EventLog({ events }) {
  const [activeTab, setActiveTab] = useState('ALL');

  const categories = ['ALL', 'DECISION', 'SIGNAL', 'SAFETY', 'EMERGENCY', 'MEASUREMENT', 'SYSTEM', 'ERROR'];

  const filteredEvents = useMemo(() => {
    if (!events) return [];
    
    // Create a copy and sort by timestamp descending (newest first)
    const sortedEvents = [...events].sort((a, b) => (b.timestamp || 0) - (a.timestamp || 0));

    if (activeTab === 'ALL') return sortedEvents;
    return sortedEvents.filter(e => e.category === activeTab);
  }, [events, activeTab]);

  const getEventIcon = (category) => {
    switch (category) {
      case 'DECISION': return <Activity className="w-3 h-3 text-indigo-400" />;
      case 'SIGNAL': return <Zap className="w-3 h-3 text-emerald-400" />;
      case 'SAFETY': return <Shield className="w-3 h-3 text-blue-400" />;
      case 'EMERGENCY': return <ShieldAlert className="w-3 h-3 text-rose-400" />;
      case 'MEASUREMENT': return <FileOutput className="w-3 h-3 text-amber-400" />;
      case 'ERROR': return <AlertTriangle className="w-3 h-3 text-rose-500" />;
      default: return <Server className="w-3 h-3 text-slate-400" />;
    }
  };

  const getSeverityColor = (severity) => {
    switch (severity?.toUpperCase()) {
      case 'CRITICAL': return 'text-rose-500 font-bold';
      case 'ERROR': return 'text-rose-400 font-bold';
      case 'WARNING': return 'text-amber-400 font-bold';
      default: return 'text-slate-400';
    }
  };

  const formatTime = (ts) => {
    if (!ts) return '';
    const d = new Date(ts * 1000);
    return d.toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  return (
    <div className="control-card rounded-xl p-4 flex flex-col h-full min-h-[300px]">
      <div className="flex items-center justify-between pb-2.5 border-b border-slate-700/80 mb-3">
        <div className="flex items-center gap-2">
          <div className="p-1 bg-indigo-500/20 text-indigo-400 rounded">
            <Terminal className="w-4 h-4" />
          </div>
          <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wider">
            Chronological Event Log
          </h2>
        </div>
        <span className="text-xs font-mono text-slate-400">MAX 500 EVENTS</span>
      </div>

      <div className="flex flex-wrap gap-1 mb-3">
        {categories.map(cat => (
          <button
            key={cat}
            onClick={() => setActiveTab(cat)}
            className={`px-2 py-1 text-[10px] font-mono rounded border ${
              activeTab === cat 
                ? 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30' 
                : 'bg-slate-800/40 text-slate-400 border-slate-700 hover:bg-slate-700/50 hover:text-slate-200'
            }`}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* Event Items Feed Container */}
      <div className="overflow-y-auto pr-1 space-y-2 flex-1 min-h-0">
        {filteredEvents.length > 0 ? (
          filteredEvents.map((item) => (
            <div
              key={item.event_id || item.timestamp}
              className="bg-slate-900/50 p-2.5 rounded-lg border border-slate-700/50 flex flex-col gap-1"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {getEventIcon(item.category)}
                  <span className="text-xs font-bold text-slate-200">{item.category}</span>
                  <span className={`text-[10px] uppercase font-mono ${getSeverityColor(item.severity)}`}>
                    {item.severity}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-[10px] font-mono text-slate-400">
                  <Clock className="w-3 h-3 opacity-50" />
                  {formatTime(item.timestamp)}
                </div>
              </div>
              
              <div className="text-xs text-slate-300 mt-1 leading-relaxed">
                {item.message}
              </div>

              {(item.target_lanes || item.decision_id || item.measurement_id) && (
                <div className="flex flex-wrap items-center gap-2 mt-1.5 pt-1.5 border-t border-slate-700/30">
                  {item.target_lanes && item.target_lanes.length > 0 && (
                    <span className="text-[10px] bg-slate-800 text-slate-300 px-1.5 py-0.5 rounded font-mono border border-slate-700">
                      LANES: {item.target_lanes.map(l => l.toUpperCase()).join('+')}
                    </span>
                  )}
                  {item.decision_id && (
                    <span className="text-[10px] text-slate-500 font-mono" title="Decision ID">
                      D: {item.decision_id.split('-').pop()}
                    </span>
                  )}
                  {item.measurement_id && (
                    <span className="text-[10px] text-slate-500 font-mono" title="Measurement ID">
                      M: {item.measurement_id.split('-').pop()}
                    </span>
                  )}
                </div>
              )}
            </div>
          ))
        ) : (
          <div className="text-center py-6 text-slate-500 text-xs italic">
            No events found for {activeTab}.
          </div>
        )}
      </div>
    </div>
  );
}
