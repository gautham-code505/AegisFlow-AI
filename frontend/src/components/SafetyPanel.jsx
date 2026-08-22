import React from 'react';
import { Shield, CheckCircle2, XCircle, AlertTriangle, ShieldCheck } from 'lucide-react';

export function SafetyPanel({ safetyResult }) {
  if (!safetyResult) {
    return (
      <div className="control-card rounded-xl p-4 flex flex-col justify-between h-full">
        <div className="flex items-center justify-between pb-3 border-b border-slate-700/80">
          <div className="flex items-center gap-2">
            <div className="p-1 bg-emerald-500/20 text-emerald-400 rounded">
              <Shield className="w-4 h-4" />
            </div>
            <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wider">
              Safety Validation
            </h2>
          </div>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <p className="text-xs text-slate-500 italic">Awaiting safety validation data...</p>
        </div>
      </div>
    );
  }

  const isApproved = safetyResult.status === 'APPROVED' || safetyResult.approved === true;
  const isFallback = safetyResult.status === 'FALLBACK';
  const isRejected = safetyResult.status === 'REJECTED';
  const reasons = safetyResult.reasons || [];

  const getStatusConfig = () => {
    if (isApproved) return {
      label: 'APPROVED',
      bg: 'bg-emerald-950/60 border-emerald-700',
      text: 'text-emerald-300',
      Icon: CheckCircle2,
      iconColor: 'text-emerald-400',
    };
    if (isFallback) return {
      label: 'FALLBACK ACTIVE',
      bg: 'bg-amber-950/60 border-amber-700',
      text: 'text-amber-300',
      Icon: AlertTriangle,
      iconColor: 'text-amber-400',
    };
    return {
      label: 'REJECTED',
      bg: 'bg-rose-950/60 border-rose-700',
      text: 'text-rose-300',
      Icon: XCircle,
      iconColor: 'text-rose-400',
    };
  };

  const statusConfig = getStatusConfig();
  const StatusIcon = statusConfig.Icon;

  // Safety checks to display
  const checks = [
    { label: 'Lane Selection Valid', pass: !reasons.some(r => r.toLowerCase().includes('invalid') && r.toLowerCase().includes('lane')) },
    { label: 'Duration Within Bounds', pass: !reasons.some(r => r.toLowerCase().includes('duration')) },
    { label: 'Traffic Data Fresh', pass: !reasons.some(r => r.toLowerCase().includes('stale') && r.toLowerCase().includes('traffic')) },
    { label: 'Decision Data Fresh', pass: !reasons.some(r => r.toLowerCase().includes('stale') && r.toLowerCase().includes('decision')) },
    { label: 'Min Green Hold Respected', pass: !reasons.some(r => r.toLowerCase().includes('minimum green')) },
    { label: 'Conflict-Free Phase', pass: !reasons.some(r => r.toLowerCase().includes('conflict')) },
  ];

  return (
    <div className="control-card rounded-xl p-4 flex flex-col justify-between h-full">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-700/80">
        <div className="flex items-center gap-2">
          <div className={`p-1 rounded ${isApproved ? 'bg-emerald-500/20 text-emerald-400' : 'bg-amber-500/20 text-amber-400'}`}>
            <Shield className="w-4 h-4" />
          </div>
          <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wider">
            Safety Validation
          </h2>
        </div>
        <div className={`px-2 py-0.5 text-[10px] font-bold rounded border flex items-center gap-1 ${statusConfig.bg} ${statusConfig.text}`}>
          <StatusIcon className={`w-3 h-3 ${statusConfig.iconColor}`} />
          <span>{statusConfig.label}</span>
        </div>
      </div>

      {/* Safety Checks Grid */}
      <div className="grid grid-cols-2 gap-1.5 my-3">
        {checks.map((check) => (
          <div key={check.label} className="flex items-center gap-1.5 bg-slate-950/80 px-2 py-1.5 rounded border border-slate-800/80">
            {isApproved || check.pass ? (
              <CheckCircle2 className="w-3 h-3 text-emerald-400 shrink-0" />
            ) : (
              <XCircle className="w-3 h-3 text-rose-400 shrink-0" />
            )}
            <span className={`text-[10px] font-medium ${isApproved || check.pass ? 'text-slate-300' : 'text-rose-300'}`}>
              {check.label}
            </span>
          </div>
        ))}
      </div>

      {/* Proposed Decision Info */}
      {safetyResult.proposed_lane && (
        <div className="bg-slate-900/80 rounded-lg p-2.5 border border-slate-800 mb-3">
          <div className="flex items-center justify-between text-[11px]">
            <span className="text-slate-400">
              Validated Approach: <strong className="text-white uppercase">{safetyResult.proposed_lane}</strong>
            </span>
            {safetyResult.proposed_duration && (
              <span className="text-slate-400">
                Duration: <strong className="text-white">{safetyResult.proposed_duration}s</strong>
              </span>
            )}
          </div>
        </div>
      )}

      {/* Validation Reasons */}
      {reasons.length > 0 && !isApproved && (
        <div className="bg-slate-950/90 rounded-lg p-2.5 border border-slate-800 flex-1">
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wide block mb-1.5">
            Validation Notes:
          </span>
          <ul className="space-y-1">
            {reasons.map((reason, idx) => (
              <li key={idx} className="text-[10px] text-slate-300 flex items-start gap-1.5">
                <AlertTriangle className="w-3 h-3 text-amber-400 shrink-0 mt-0.5" />
                <span>{reason}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Approved confirmation */}
      {isApproved && (
        <div className="bg-emerald-950/40 rounded-lg p-2.5 border border-emerald-800/60 flex-1 flex items-center gap-2">
          <ShieldCheck className="w-5 h-5 text-emerald-400" />
          <div>
            <span className="text-xs font-bold text-emerald-300 block">All Safety Checks Passed</span>
            <span className="text-[10px] text-emerald-400/80">Signal phase is conflict-free and within safe timing bounds</span>
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="mt-3 pt-2 border-t border-slate-800/60 text-[11px] text-slate-400 flex items-center justify-between">
        <span>ConflictMatrix + PhaseGroup Validator</span>
        <span className="text-emerald-400 font-semibold">Always Active</span>
      </div>
    </div>
  );
}
