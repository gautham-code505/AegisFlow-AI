import React from 'react';
import { Activity, Camera, Eye, Cpu, Shield, HardDrive, WifiOff, CheckCircle, AlertTriangle, XCircle } from 'lucide-react';

export function SystemHealthBar({ systemStatus, wsStatus, isStale }) {
  const isConnected = wsStatus === 'CONNECTED';
  
  const getModStatus = (key, defaultStatus = 'offline') => {
    if (!isConnected) return 'offline';
    const statusVal = systemStatus?.[key] || defaultStatus;
    return typeof statusVal === 'string' ? statusVal.toLowerCase() : 'offline';
  };

  const getConnectionStatus = () => {
    if (!isConnected) return { label: 'DISCONNECTED', status: 'offline' };
    if (isStale) return { label: 'STALE DATA', status: 'warning' };
    return { label: 'LIVE DATA', status: 'online' };
  };

  const connState = getConnectionStatus();

  const modules = [
    { key: 'camera', name: 'Camera Vision', icon: Camera, status: getModStatus('camera') },
    { key: 'vision', name: 'YOLOv8 AI Model', icon: Eye, status: getModStatus('vision') },
    { key: 'decision_engine', name: 'Decision Engine', icon: Cpu, status: getModStatus('decision_engine') },
    { key: 'safety', name: 'Safety Validator', icon: Shield, status: getModStatus('safety') },
    { key: 'controller', name: 'ESP32 Controller', icon: HardDrive, status: getModStatus('controller') },
    { key: 'connection', name: 'Data Freshness', icon: Activity, status: connState.status, overrideLabel: connState.label },
  ];

  const getStatusBadge = (status, overrideLabel) => {
    if (status === 'online') {
      return {
        label: overrideLabel || 'ONLINE',
        bg: 'bg-emerald-950/60 text-emerald-300 border-emerald-800/80',
        dot: 'bg-emerald-400',
        Icon: CheckCircle,
      };
    }
    if (status === 'warning' || status === 'fallback') {
      return {
        label: overrideLabel || status.toUpperCase(),
        bg: 'bg-amber-950/60 text-amber-300 border-amber-800/80',
        dot: 'bg-amber-400 animate-pulse',
        Icon: AlertTriangle,
      };
    }
    if (status === 'offline') {
      return {
        label: overrideLabel || 'OFFLINE',
        bg: 'bg-rose-950/60 text-rose-300 border-rose-800/80',
        dot: 'bg-rose-500',
        Icon: XCircle,
      };
    }
    return {
      label: 'UNAVAILABLE',
      bg: 'bg-slate-900 text-slate-400 border-slate-700',
      dot: 'bg-slate-500',
      Icon: XCircle,
    };
  };

  return (
    <div className="control-card rounded-xl p-4 flex flex-col justify-between h-full">
      <div className="flex items-center justify-between pb-3 border-b border-slate-700/80 mb-3">
        <div className="flex items-center gap-2">
          <div className="p-1 bg-indigo-500/20 text-indigo-400 rounded">
            <Activity className="w-4 h-4" />
          </div>
          <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wider">
            Subsystem Health Matrix
          </h2>
        </div>
        <span className={`px-2 py-0.5 text-[10px] font-bold rounded border ${
          connState.status === 'online' ? 'bg-emerald-950 text-emerald-300 border-emerald-700' : 
          connState.status === 'warning' ? 'bg-amber-950 text-amber-300 border-amber-700' : 
          'bg-rose-950 text-rose-300 border-rose-700'
        }`}>
          DATA FRESHNESS: {connState.label}
        </span>
      </div>

      {/* Grid of Subsystems */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 my-1">
        {modules.map((mod) => {
          const { label, bg, dot, Icon } = getStatusBadge(mod.status, mod.overrideLabel);
          const ModIcon = mod.icon;
          return (
            <div
              key={mod.key}
              className="bg-slate-950/80 p-2.5 rounded-lg border border-slate-800 flex flex-col justify-between"
            >
              <div className="flex items-center justify-between text-slate-400 mb-1.5">
                <ModIcon className="w-3.5 h-3.5 text-indigo-400" />
                <span className={`w-2 h-2 rounded-full ${dot}`} />
              </div>
              <div>
                <span className="text-[11px] font-semibold text-slate-300 block truncate">
                  {mod.name}
                </span>
                <span
                  className={`mt-1 px-2 py-0.5 text-[10px] font-bold rounded border inline-flex items-center gap-1 ${bg}`}
                >
                  <Icon className="w-3 h-3" />
                  <span>{label}</span>
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Offline Mode Explicit Communication Box */}
      <div className="mt-3 bg-slate-900/90 border border-emerald-700/40 rounded-lg p-2.5 flex items-center justify-between text-xs">
        <div className="flex items-center gap-2 text-emerald-300">
          <WifiOff className="w-4 h-4 text-emerald-400" />
          <div>
            <span className="font-bold block">OFFLINE ARCHITECTURE VERIFIED</span>
            <span className="text-[10px] text-slate-400">Core logic processes 100% locally on intersection edge</span>
          </div>
        </div>
        <span className="text-[10px] font-mono text-emerald-400 font-bold bg-emerald-950 px-2 py-1 rounded border border-emerald-800">
          100% LOCAL
        </span>
      </div>
    </div>
  );
}
