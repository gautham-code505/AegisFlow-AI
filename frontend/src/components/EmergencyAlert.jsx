import React from 'react';
import { Siren, ShieldCheck, AlertOctagon } from 'lucide-react';

export function EmergencyAlert({ emergency }) {
  const isEmergency = emergency?.detected;
  const lane = emergency?.lane;
  const vehicleType = emergency?.vehicle_type || 'AMBULANCE';
  const confidence = emergency?.confidence;

  if (!isEmergency || !lane) {
    return (
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-3 flex items-center justify-between text-xs mb-4">
        <div className="flex items-center gap-2 text-slate-300">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          <span className="font-semibold">EMERGENCY PREEMPTION STATUS:</span>
          <span className="text-slate-400">No emergency vehicle detected on intersection approaches</span>
        </div>
        <span className="px-2.5 py-0.5 rounded text-[10px] font-semibold bg-emerald-950 text-emerald-300 border border-emerald-800">
          STANDARD ADAPTIVE CYCLE
        </span>
      </div>
    );
  }

  return (
    <div className="bg-rose-950/80 border-2 border-rose-600 rounded-xl p-3.5 flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs mb-4 emergency-pulse shadow-xl">
      <div className="flex items-center gap-3">
        <div className="p-2 bg-rose-600 text-white rounded-lg animate-bounce">
          <Siren className="w-5 h-5" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-extrabold text-white text-sm uppercase tracking-wider flex items-center gap-1.5">
              <AlertOctagon className="w-4 h-4 text-rose-300" />
              CRITICAL EMERGENCY PREEMPTION ACTIVE
            </h3>
            <span className="px-2 py-0.5 text-[10px] font-black bg-rose-600 text-white rounded uppercase animate-pulse">
              PRIORITY OVERRIDE
            </span>
          </div>
          <p className="text-rose-200 mt-0.5 font-medium">
            Emergency Vehicle Detected: <strong className="text-white uppercase">{vehicleType}</strong> on{' '}
            <strong className="text-white uppercase font-bold">{lane} APPROACH</strong>
            {confidence && (
              <span className="ml-2 text-rose-300 text-[10px]">
                (Confidence: {(confidence * 100).toFixed(1)}%)
              </span>
            )}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2 text-right">
        <div className="bg-slate-950/80 px-3 py-1.5 rounded-lg border border-rose-700/60 font-mono text-[11px] text-rose-200">
          <div>Safety Rule: <strong className="text-white">#E-01 Preemption</strong></div>
          <div className="text-emerald-400 font-semibold">Immediate Signal Clearing</div>
        </div>
      </div>
    </div>
  );
}
