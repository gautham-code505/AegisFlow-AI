import React from 'react';
import { Gauge, Cpu, Zap, HardDrive } from 'lucide-react';

export function PerformanceMetrics({ systemStatus }) {
  const fps = systemStatus?.fps || 30;
  const latency = systemStatus?.latency_ms || 16;

  return (
    <div className="control-card rounded-xl p-4 flex flex-col justify-between h-full">
      <div className="flex items-center justify-between pb-3 border-b border-slate-700/80 mb-3">
        <div className="flex items-center gap-2">
          <div className="p-1 bg-indigo-500/20 text-indigo-400 rounded">
            <Gauge className="w-4 h-4" />
          </div>
          <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wider">
            Edge Node System Performance
          </h2>
        </div>
        <span className="text-xs font-mono text-slate-400">TELEMETRY</span>
      </div>

      <div className="grid grid-cols-2 gap-2 my-1">
        <div className="bg-slate-950/80 p-2.5 rounded-lg border border-slate-800 flex items-center justify-between">
          <div>
            <span className="text-[10px] text-slate-400 font-medium block">YOLOv8 Latency</span>
            <span className="text-sm font-bold font-mono text-emerald-400 mt-0.5 block">{latency} ms</span>
          </div>
          <Zap className="w-4 h-4 text-emerald-400" />
        </div>

        <div className="bg-slate-950/80 p-2.5 rounded-lg border border-slate-800 flex items-center justify-between">
          <div>
            <span className="text-[10px] text-slate-400 font-medium block">Processing FPS</span>
            <span className="text-sm font-bold font-mono text-indigo-300 mt-0.5 block">{fps} FPS</span>
          </div>
          <Gauge className="w-4 h-4 text-indigo-400" />
        </div>

        <div className="bg-slate-950/80 p-2.5 rounded-lg border border-slate-800 flex items-center justify-between">
          <div>
            <span className="text-[10px] text-slate-400 font-medium block">Edge RAM Footprint</span>
            <span className="text-sm font-bold font-mono text-slate-200 mt-0.5 block">142 MB</span>
          </div>
          <Cpu className="w-4 h-4 text-indigo-400" />
        </div>

        <div className="bg-slate-950/80 p-2.5 rounded-lg border border-slate-800 flex items-center justify-between">
          <div>
            <span className="text-[10px] text-slate-400 font-medium block">ESP32 UART Bus</span>
            <span className="text-sm font-bold font-mono text-emerald-400 mt-0.5 block">115.2 kbps</span>
          </div>
          <HardDrive className="w-4 h-4 text-emerald-400" />
        </div>
      </div>

      <div className="mt-3 pt-2 border-t border-slate-800/60 flex items-center justify-between text-[11px] text-slate-400">
        <span>Hardware Accelerator: GPU/NPU active</span>
        <span className="text-emerald-400 font-semibold">Ultra-Low Power</span>
      </div>
    </div>
  );
}
