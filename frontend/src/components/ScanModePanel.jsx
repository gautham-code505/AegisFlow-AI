import React, { useCallback, useEffect, useState } from 'react';
import { Camera, CheckCircle2, Circle, RotateCcw, Play, Square, ScanLine, ShieldCheck, ShieldX, TrafficCone, RefreshCw } from 'lucide-react';
import {
  fetchScanStatus, startScan, stopScan, newScan, captureApproach, confirmApproach,
  retakeApproach, applyScan, scanImageUrl, videoStreamUrl,
} from '../services/api';

const ORDER = ['north', 'east', 'south', 'west'];
const upper = (s) => String(s || '').toUpperCase();

const VALIDITY_STYLE = {
  VALID: 'bg-emerald-950/60 border-emerald-700 text-emerald-300',
  INCOMPLETE: 'bg-slate-900 border-slate-700 text-slate-300',
  EXPIRED: 'bg-amber-950/60 border-amber-700 text-amber-300',
  APPLIED: 'bg-indigo-950/60 border-indigo-700 text-indigo-300',
};

function StepCard({ lane, observation, isCurrent, onSelect }) {
  const status = observation?.status;
  const confirmed = status === 'CONFIRMED';
  const pending = status === 'PENDING';
  return (
    <button
      type="button"
      onClick={() => onSelect(lane)}
      className={`text-left rounded-lg border p-2 transition-colors ${
        isCurrent ? 'border-indigo-500 bg-indigo-950/40' : 'border-slate-700/70 bg-slate-900/60 hover:border-slate-500'
      }`}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-bold tracking-wider text-slate-100">{upper(lane)}</span>
        {confirmed ? <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          : <Circle className={`w-4 h-4 ${pending ? 'text-amber-400' : 'text-slate-600'}`} />}
      </div>
      <div className="mt-1.5 aspect-video rounded bg-slate-950 border border-slate-800 overflow-hidden flex items-center justify-center">
        {observation ? (
          <img src={scanImageUrl(lane, observation.image_sha256)} alt={`${upper(lane)} capture`} className="w-full h-full object-cover" />
        ) : (
          <span className="text-[10px] text-slate-600">Not captured</span>
        )}
      </div>
      <div className="mt-1.5 flex items-center justify-between text-[11px]">
        <span className={confirmed ? 'text-emerald-300 font-bold' : pending ? 'text-amber-300 font-bold' : 'text-slate-500'}>
          {observation ? `${observation.vehicle_count} veh` : '—'}
        </span>
        <span className="text-slate-400 font-mono">{observation ? `${Math.round(observation.age_seconds)}s ago` : ''}</span>
      </div>
      <div className="text-[10px] uppercase tracking-wider mt-0.5 text-slate-500">
        {confirmed ? 'Confirmed' : pending ? 'Review capture' : 'Waiting'}
      </div>
    </button>
  );
}

export function ScanModePanel() {
  const [status, setStatus] = useState(null);
  const [selected, setSelected] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [streamKey, setStreamKey] = useState(0);

  const refresh = useCallback(async () => {
    try {
      setStatus(await fetchScanStatus());
    } catch (err) {
      setStatus(null);
      setError(`Backend not reachable: ${err.message}`);
    }
  }, []);

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 1000);
    return () => clearInterval(timer);
  }, [refresh]);

  const run = async (action) => {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
      refresh();
    }
  };

  const scan = status?.scan;
  const active = status?.active === true;
  const cameraState = status?.camera?.state || 'OFF';
  const isApplied = scan?.validity === 'APPLIED';
  const current = isApplied ? null : (selected || scan?.next_approach || null);
  const observation = current ? scan?.observations?.[current] : null;
  const isPending = observation?.status === 'PENDING';
  const cycle = status?.cycle;

  const handleStart = () => run(async () => { await startScan(); setSelected(null); setStreamKey((k) => k + 1); });
  const handleStop = () => run(async () => { await stopScan(); setSelected(null); });
  const handleNew = () => run(async () => { await newScan(); setSelected(null); });
  const handleCapture = () => run(() => captureApproach(current));
  const handleConfirm = () => run(async () => { await confirmApproach(current); setSelected(null); });
  const handleRetake = () => run(() => retakeApproach(current));
  const handleApply = () => run(() => applyScan());

  return (
    <div className="control-card rounded-xl p-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-slate-700/80">
        <div className="flex items-center gap-2">
          <div className="p-1 bg-indigo-500/20 text-indigo-400 rounded"><ScanLine className="w-4 h-4" /></div>
          <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wider">Four-Direction Scan</h2>
          <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded border ${
            cameraState === 'LIVE' ? 'border-emerald-700 text-emerald-300 bg-emerald-950/50'
              : cameraState === 'ERROR' ? 'border-rose-700 text-rose-300 bg-rose-950/50'
              : 'border-slate-700 text-slate-400 bg-slate-900'}`}>
            Camera {cameraState}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {active && (
            <button type="button" onClick={handleNew} disabled={busy}
              className="flex items-center gap-1.5 text-xs font-bold px-3 py-1.5 rounded-lg border border-slate-600 text-slate-200 hover:bg-slate-800 disabled:opacity-50">
              <RefreshCw className="w-3.5 h-3.5" /> New scan
            </button>
          )}
          {active ? (
            <button type="button" onClick={handleStop} disabled={busy}
              className="flex items-center gap-1.5 text-xs font-bold px-3 py-1.5 rounded-lg bg-rose-900/70 border border-rose-700 text-rose-100 hover:bg-rose-800 disabled:opacity-50">
              <Square className="w-3.5 h-3.5" /> Stop scan mode
            </button>
          ) : (
            <button type="button" onClick={handleStart} disabled={busy || !status}
              className="flex items-center gap-1.5 text-xs font-bold px-3 py-1.5 rounded-lg bg-emerald-600 text-white hover:bg-emerald-500 disabled:opacity-50">
              <Play className="w-3.5 h-3.5" /> Start scan mode
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="mt-3 text-xs text-rose-300 bg-rose-950/50 border border-rose-800 rounded px-3 py-2">{error}</div>
      )}
      {status?.camera?.error && (
        <div className="mt-3 text-xs text-rose-300 bg-rose-950/50 border border-rose-800 rounded px-3 py-2">
          Camera problem: {status.camera.error}. Stop and start scan mode again.
        </div>
      )}

      {!active && (
        <p className="mt-4 text-xs text-slate-400">
          Hold the phone close to one approach at a time. Capture and confirm NORTH, EAST, SOUTH and WEST;
          AegisFlow then proposes which approach gets green. Signals stay ALL RED while you scan.
        </p>
      )}

      {active && scan && (
        <>
          {/* Four steps */}
          <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-2">
            {ORDER.map((lane) => (
              <StepCard key={lane} lane={lane} observation={scan.observations?.[lane]}
                isCurrent={lane === current} onSelect={setSelected} />
            ))}
          </div>

          <div className="mt-4 grid grid-cols-1 lg:grid-cols-5 gap-4">
            {/* Camera / capture review */}
            <div className="lg:col-span-3">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm font-bold text-slate-100">
                  {current ? <>Point camera at: <span className="text-indigo-300">{upper(current)}</span></>
                    : isApplied ? 'Scan applied to the signals' : 'All four approaches confirmed'}
                </p>
                {observation && (
                  <span className="text-[11px] text-slate-400 font-mono">
                    captured {new Date(observation.captured_at * 1000).toLocaleTimeString()}
                  </span>
                )}
              </div>

              <div className="aspect-video rounded-lg bg-slate-950 border border-slate-800 overflow-hidden flex items-center justify-center">
                {isPending ? (
                  <img src={scanImageUrl(current, observation.image_sha256)} alt="Captured still" className="w-full h-full object-contain" />
                ) : cameraState === 'LIVE' ? (
                  <img key={streamKey} src={videoStreamUrl()} alt="Live preview" className="w-full h-full object-contain" />
                ) : (
                  <span className="text-xs text-slate-500 flex items-center gap-2"><Camera className="w-4 h-4" /> Waiting for camera…</span>
                )}
              </div>

              <div className="mt-2 flex flex-wrap items-center gap-2">
                {isPending ? (
                  <>
                    <span className="text-sm text-amber-300 font-bold mr-auto">
                      {observation.vehicle_count} vehicle{observation.vehicle_count === 1 ? '' : 's'} counted
                      {observation.excluded_count > 0 && (
                        <span className="text-xs text-slate-400 font-normal"> ({observation.excluded_count} outside the box ignored)</span>
                      )}
                    </span>
                    <button type="button" onClick={handleRetake} disabled={busy}
                      className="flex items-center gap-1.5 text-xs font-bold px-3 py-2 rounded-lg border border-slate-600 text-slate-200 hover:bg-slate-800 disabled:opacity-50">
                      <RotateCcw className="w-3.5 h-3.5" /> Retake
                    </button>
                    <button type="button" onClick={handleConfirm} disabled={busy}
                      className="flex items-center gap-1.5 text-xs font-bold px-4 py-2 rounded-lg bg-emerald-600 text-white hover:bg-emerald-500 disabled:opacity-50">
                      <CheckCircle2 className="w-3.5 h-3.5" /> OK, use this
                    </button>
                  </>
                ) : current ? (
                  <>
                    <span className="text-xs text-slate-400 mr-auto">Only vehicles inside the white box are counted.</span>
                    {observation?.status === 'CONFIRMED' && (
                      <button type="button" onClick={handleRetake} disabled={busy}
                        className="flex items-center gap-1.5 text-xs font-bold px-3 py-2 rounded-lg border border-slate-600 text-slate-200 hover:bg-slate-800 disabled:opacity-50">
                        <RotateCcw className="w-3.5 h-3.5" /> Retake {upper(current)}
                      </button>
                    )}
                    <button type="button" onClick={handleCapture} disabled={busy || cameraState !== 'LIVE'}
                      className="flex items-center gap-1.5 text-xs font-bold px-4 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-50">
                      <Camera className="w-3.5 h-3.5" /> Capture {upper(current)}
                    </button>
                  </>
                ) : isApplied || scan.validity === 'EXPIRED' ? (
                  <>
                    <span className="text-xs text-slate-400 mr-auto">
                      {isApplied
                        ? 'Traffic has changed since this scan. Scan all four directions again for the next cycle.'
                        : 'These captures are too old to use. Retake the oldest directions, or start a new scan.'}
                    </span>
                    <button type="button" onClick={handleNew} disabled={busy}
                      className="flex items-center gap-1.5 text-xs font-bold px-4 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-50">
                      <RefreshCw className="w-3.5 h-3.5" /> Start new scan
                    </button>
                  </>
                ) : null}
              </div>
            </div>

            {/* Result and signal permission */}
            <div className="lg:col-span-2 space-y-3">
              <div className={`rounded-lg border px-3 py-2 ${VALIDITY_STYLE[scan.validity] || VALIDITY_STYLE.INCOMPLETE}`}>
                <p className="text-xs font-bold uppercase tracking-wider">Scan {scan.validity}</p>
                <p className="text-xs mt-0.5">{scan.reason}</p>
                {scan.oldest_age_seconds !== null && (
                  <p className="text-[11px] mt-1 font-mono opacity-80">
                    Oldest capture {Math.round(scan.oldest_age_seconds)}s / limit {Math.round(status.settings.max_age_seconds)}s
                  </p>
                )}
              </div>

              <div className="rounded-lg border border-slate-700 bg-slate-900/60 px-3 py-2">
                <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                  <TrafficCone className="w-3.5 h-3.5" /> Proposed signal
                </p>
                {scan.proposal ? (
                  <>
                    <p className="text-sm font-bold text-emerald-300 mt-1">
                      {upper(scan.proposal.selected_lane)} GREEN for {scan.proposal.duration}s
                    </p>
                    <ul className="mt-1 space-y-0.5">
                      {scan.proposal.reasons.map((r, i) => (
                        <li key={i} className="text-[11px] text-slate-300">{r}</li>
                      ))}
                    </ul>
                  </>
                ) : (
                  <p className="text-xs text-slate-500 mt-1">Available when all four approaches are confirmed.</p>
                )}
              </div>

              <div className={`rounded-lg border px-3 py-2 ${scan.actuation_permitted ? 'border-emerald-700 bg-emerald-950/40' : 'border-slate-700 bg-slate-900/60'}`}>
                <p className="text-[11px] font-bold uppercase tracking-wider flex items-center gap-1.5 text-slate-300">
                  {scan.actuation_permitted
                    ? <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                    : <ShieldX className="w-3.5 h-3.5 text-slate-500" />}
                  Physical signal: {scan.actuation_permitted ? 'permitted' : 'not permitted'}
                </p>
                {!scan.actuation_permitted && scan.actuation_blocked_reason && (
                  <p className="text-[11px] text-slate-400 mt-0.5">{scan.actuation_blocked_reason}</p>
                )}
                {cycle && (
                  <p className="text-xs text-emerald-300 font-bold mt-1">
                    {upper(cycle.lane)} GREEN running: {cycle.green_remaining_seconds}s left, then YELLOW and ALL RED
                  </p>
                )}
                <button type="button" onClick={handleApply} disabled={busy || !scan.actuation_permitted}
                  className="mt-2 w-full text-xs font-bold px-3 py-2 rounded-lg bg-emerald-600 text-white hover:bg-emerald-500 disabled:opacity-40 disabled:cursor-not-allowed">
                  Apply to signals (one cycle)
                </button>
                <p className="text-[10px] text-slate-500 mt-1.5">
                  Tabletop demonstration only. One green for one approach, then yellow and all red. Scan again for the next cycle.
                </p>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
