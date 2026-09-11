import React from 'react';
import {
  Timer,
  ArrowUp,
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ShieldAlert,
  AlertTriangle,
} from 'lucide-react';

/**
 * 3-Aspect Signal Head Component
 * Strictly displays the authoritative state of a single lane's signal head.
 */
function SignalHead({ lane, signalColor, isConflicting }) {
  const isRed = signalColor === 'RED';
  const isYellow = signalColor === 'YELLOW';
  const isGreen = signalColor === 'GREEN';

  return (
    <div className="flex flex-col items-center select-none">
      {/* 3-Aspect Signal Housing */}
      <div className="bg-black/90 border border-slate-700/80 rounded px-1.5 py-0.5 flex items-center gap-1 shadow-lg">
        <span
          title="RED"
          className={`w-2.5 h-2.5 rounded-full transition-all duration-300 ${
            isRed
              ? 'bg-rose-500 shadow-[0_0_8px_#f43f5e]'
              : 'bg-rose-950/40 opacity-30'
          }`}
        />
        <span
          title="YELLOW"
          className={`w-2.5 h-2.5 rounded-full transition-all duration-300 ${
            isYellow
              ? 'bg-amber-400 animate-pulse shadow-[0_0_8px_#fbbf24]'
              : 'bg-amber-950/40 opacity-30'
          }`}
        />
        <span
          title="GREEN"
          className={`w-2.5 h-2.5 rounded-full transition-all duration-300 ${
            isGreen
              ? 'bg-emerald-400 shadow-[0_0_8px_#34d399]'
              : 'bg-emerald-950/40 opacity-30'
          }`}
        />
      </div>

      {/* Lane Label & Movement State */}
      <div className="flex items-center gap-1 mt-1">
        <span
          className={`text-[10px] font-bold px-1.5 py-0.2 rounded border font-mono ${
            isGreen
              ? 'bg-emerald-950/80 text-emerald-300 border-emerald-700'
              : isYellow
              ? 'bg-amber-950/80 text-amber-300 border-amber-700'
              : 'bg-slate-900 text-slate-300 border-slate-700'
          }`}
        >
          {lane.toUpperCase()}
        </span>
        {isConflicting && isRed && (
          <span className="text-[8px] font-mono font-semibold px-1 py-0.2 rounded bg-rose-950/60 text-rose-300 border border-rose-800/60">
            HELD
          </span>
        )}
      </div>
    </div>
  );
}

/**
 * Compact Approach Traffic Intelligence Chip
 */
function ApproachChip({ name, laneData, hasTrackingData, isEmergency }) {
  const vehicleCount = laneData?.vehicle_count ?? 0;
  const queuedCount = hasTrackingData ? (laneData?.queued_vehicle_count ?? 0) : '—';
  const waitTime = hasTrackingData ? `${Math.round(laneData?.observed_average_wait ?? 0)}s` : '—';

  return (
    <div
      className={`p-1.5 rounded-lg border text-[10px] backdrop-blur-sm shadow-md transition-all ${
        isEmergency
          ? 'bg-rose-950/70 border-rose-500 shadow-rose-950/40 animate-pulse'
          : 'bg-slate-900/80 border-slate-800'
      }`}
    >
      <div className="flex items-center justify-between pb-0.5 border-b border-slate-800/80 mb-1">
        <span className="font-bold uppercase tracking-wider text-slate-300 text-[9px]">
          {name}
        </span>
        {isEmergency ? (
          <span className="text-[8px] font-bold bg-rose-600 text-white px-1 rounded">
            EMG
          </span>
        ) : (
          <span className="text-[9px] font-mono text-slate-400">
            {vehicleCount} veh
          </span>
        )}
      </div>
      <div className="grid grid-cols-2 gap-1 text-[9px] font-mono text-slate-400">
        <div>
          <span className="text-[8px] block text-slate-500">QUEUE</span>
          <span className="text-slate-200 font-semibold">{queuedCount}</span>
        </div>
        <div>
          <span className="text-[8px] block text-slate-500">WAIT</span>
          <span className="text-slate-200 font-semibold">{waitTime}</span>
        </div>
      </div>
    </div>
  );
}

export function IntersectionTwin({
  signalState,
  trafficState,
  signalDecision,
  safetyResult,
  isStale = false,
}) {
  // Use ONLY authoritative SignalState for the twin's physical representation
  const activeLanes =
    signalState?.active_lanes ||
    (signalState?.active_lane ? [signalState.active_lane] : []);
  const targetLanes = signalState?.target_lanes || [];
  const remainingSeconds = signalState?.remaining_seconds ?? 0;
  const phase = signalState?.phase || 'ALL_RED';

  // Traffic context data
  const hasTrackingData = trafficState?.has_tracking_data === true;
  const isEmergency = trafficState?.emergency?.detected === true;
  const emergencyLane = isEmergency ? trafficState.emergency.lane : null;

  // Signal color helpers strictly from SignalState
  const getLaneColor = (lane) => signalState?.[lane]?.toUpperCase() || 'RED';
  const northColor = getLaneColor('north');
  const southColor = getLaneColor('south');
  const eastColor = getLaneColor('east');
  const westColor = getLaneColor('west');

  // Three-Layer Comparison Variables
  const aiProposedLanes =
    signalDecision?.selected_lanes?.join('+')?.toUpperCase() ||
    signalDecision?.selected_lane?.toUpperCase() ||
    'NONE';
  const aiProposedDuration = signalDecision?.recommended_green_duration
    ? `${signalDecision.recommended_green_duration}s`
    : signalDecision?.duration
    ? `${signalDecision.duration}s`
    : '—';

  const isSafetyApproved =
    safetyResult?.status === 'APPROVED' || safetyResult?.approved === true || safetyResult?.is_safe === true;
  const isSafetyFallback = safetyResult?.status === 'FALLBACK';
  const safetyLabel = isSafetyApproved
    ? 'PERMITTED'
    : isSafetyFallback
    ? 'FALLBACK'
    : safetyResult
    ? 'REJECTED'
    : 'MONITORING';
  const safetyStatusColor = isSafetyApproved
    ? 'text-emerald-400'
    : isSafetyFallback
    ? 'text-amber-400'
    : 'text-rose-400';

  const phaseColor =
    phase === 'GREEN'
      ? 'text-emerald-400'
      : phase === 'YELLOW'
      ? 'text-amber-400'
      : 'text-rose-400';

  return (
    <div className="control-card rounded-xl p-4 flex flex-col justify-between h-full">
      {/* Header */}
      <div>
        <div className="flex items-center justify-between pb-2 border-b border-slate-700/80">
          <div className="flex items-center gap-2">
            <div className="p-1 bg-emerald-500/20 text-emerald-400 rounded">
              <Timer className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wider">
                Intersection Twin
              </h2>
              <span className="text-[10px] text-slate-400 font-mono">
                AUTHORITATIVE CONTROLLER OBSERVER
              </span>
            </div>
          </div>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
            ACTUAL STATE
          </span>
        </div>

        {/* Stale Telemetry Notice (Without Synthesized Countdown) */}
        {isStale && (
          <div className="mt-2 px-2.5 py-1 bg-amber-950/60 border border-amber-700/80 rounded text-[11px] text-amber-300 flex items-center justify-between">
            <span className="flex items-center gap-1.5 font-medium">
              <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0" />
              <span>STALE TELEMETRY — HOLDING LAST KNOWN CONTROLLER STATE</span>
            </span>
            <span className="text-[9px] font-mono text-amber-400 uppercase">
              NO FAKE CLOCK
            </span>
          </div>
        )}
      </div>

      {/* 2D Intersection Engineering Visualization */}
      <div className="relative my-3 flex-1 flex items-center justify-center">
        <div className="relative w-full max-w-[340px] h-[330px] bg-slate-950 border border-slate-700/80 rounded-2xl overflow-hidden shadow-2xl p-2 select-none">
          {/* Vertical Road (North - South) */}
          <div className="absolute left-1/2 -translate-x-1/2 inset-y-0 w-28 bg-slate-900/95 border-x border-slate-700/60 flex flex-col justify-between items-center py-2">
            {/* North Crosswalk & Stop Line */}
            <div className="w-full flex flex-col items-center">
              <div className="w-full h-2.5 bg-[repeating-linear-gradient(90deg,#94a3b8,#94a3b8_5px,transparent_5px,transparent_10px)] opacity-30 mb-1" />
              <div className="w-full h-0.5 bg-slate-200/60 shadow-sm" />
            </div>

            {/* Vertical Center Lane Divider */}
            <div className="w-0 h-full border-r border-dashed border-amber-500/40 my-1" />

            {/* South Crosswalk & Stop Line */}
            <div className="w-full flex flex-col items-center">
              <div className="w-full h-0.5 bg-slate-200/60 shadow-sm mb-1" />
              <div className="w-full h-2.5 bg-[repeating-linear-gradient(90deg,#94a3b8,#94a3b8_5px,transparent_5px,transparent_10px)] opacity-30" />
            </div>
          </div>

          {/* Horizontal Road (East - West) */}
          <div className="absolute top-1/2 -translate-y-1/2 inset-x-0 h-28 bg-slate-900/95 border-y border-slate-700/60 flex justify-between items-center px-2">
            {/* West Crosswalk & Stop Line */}
            <div className="h-full flex items-center">
              <div className="h-full w-2.5 bg-[repeating-linear-gradient(0deg,#94a3b8,#94a3b8_5px,transparent_5px,transparent_10px)] opacity-30 mr-1" />
              <div className="h-full w-0.5 bg-slate-200/60 shadow-sm" />
            </div>

            {/* Horizontal Center Lane Divider */}
            <div className="h-0 w-full border-b border-dashed border-amber-500/40 mx-1" />

            {/* East Crosswalk & Stop Line */}
            <div className="h-full flex items-center">
              <div className="h-full w-0.5 bg-slate-200/60 shadow-sm mr-1" />
              <div className="h-full w-2.5 bg-[repeating-linear-gradient(0deg,#94a3b8,#94a3b8_5px,transparent_5px,transparent_10px)] opacity-30" />
            </div>
          </div>

          {/* 4 Corner Traffic Intelligence Chips */}
          <div className="absolute top-2 left-2 z-10 w-24">
            <ApproachChip
              name="West"
              laneData={trafficState?.lanes?.west}
              hasTrackingData={hasTrackingData}
              isEmergency={emergencyLane === 'west'}
            />
          </div>
          <div className="absolute top-2 right-2 z-10 w-24">
            <ApproachChip
              name="North"
              laneData={trafficState?.lanes?.north}
              hasTrackingData={hasTrackingData}
              isEmergency={emergencyLane === 'north'}
            />
          </div>
          <div className="absolute bottom-2 left-2 z-10 w-24">
            <ApproachChip
              name="South"
              laneData={trafficState?.lanes?.south}
              hasTrackingData={hasTrackingData}
              isEmergency={emergencyLane === 'south'}
            />
          </div>
          <div className="absolute bottom-2 right-2 z-10 w-24">
            <ApproachChip
              name="East"
              laneData={trafficState?.lanes?.east}
              hasTrackingData={hasTrackingData}
              isEmergency={emergencyLane === 'east'}
            />
          </div>

          {/* Signal Heads & Movement Arrows */}

          {/* North Signal Head */}
          <div className="absolute top-2 left-1/2 -translate-x-1/2 z-20 flex flex-col items-center">
            <SignalHead
              lane="north"
              signalColor={northColor}
              isConflicting={northColor === 'RED'}
            />
            {northColor === 'GREEN' ? (
              <ArrowDown className="w-4 h-4 text-emerald-400 animate-bounce mt-0.5" />
            ) : northColor === 'YELLOW' ? (
              <ArrowDown className="w-4 h-4 text-amber-400 animate-pulse mt-0.5" />
            ) : (
              <div className="w-4 h-0.5 bg-rose-500/60 mt-1" />
            )}
          </div>

          {/* South Signal Head */}
          <div className="absolute bottom-2 left-1/2 -translate-x-1/2 z-20 flex flex-col items-center">
            {southColor === 'GREEN' ? (
              <ArrowUp className="w-4 h-4 text-emerald-400 animate-bounce mb-0.5" />
            ) : southColor === 'YELLOW' ? (
              <ArrowUp className="w-4 h-4 text-amber-400 animate-pulse mb-0.5" />
            ) : (
              <div className="w-4 h-0.5 bg-rose-500/60 mb-1" />
            )}
            <SignalHead
              lane="south"
              signalColor={southColor}
              isConflicting={southColor === 'RED'}
            />
          </div>

          {/* West Signal Head */}
          <div className="absolute left-2 top-1/2 -translate-y-1/2 z-20 flex items-center">
            <SignalHead
              lane="west"
              signalColor={westColor}
              isConflicting={westColor === 'RED'}
            />
            {westColor === 'GREEN' ? (
              <ArrowRight className="w-4 h-4 text-emerald-400 animate-pulse ml-1" />
            ) : westColor === 'YELLOW' ? (
              <ArrowRight className="w-4 h-4 text-amber-400 animate-ping ml-1" />
            ) : (
              <div className="w-0.5 h-4 bg-rose-500/60 ml-1" />
            )}
          </div>

          {/* East Signal Head */}
          <div className="absolute right-2 top-1/2 -translate-y-1/2 z-20 flex items-center">
            {eastColor === 'GREEN' ? (
              <ArrowLeft className="w-4 h-4 text-emerald-400 animate-pulse mr-1" />
            ) : eastColor === 'YELLOW' ? (
              <ArrowLeft className="w-4 h-4 text-amber-400 animate-ping mr-1" />
            ) : (
              <div className="w-0.5 h-4 bg-rose-500/60 mr-1" />
            )}
            <SignalHead
              lane="east"
              signalColor={eastColor}
              isConflicting={eastColor === 'RED'}
            />
          </div>

          {/* Central Junction Status Box */}
          <div
            className={`absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-28 h-28 bg-slate-950/95 rounded-xl border-2 z-20 flex flex-col items-center justify-center p-1.5 text-center shadow-2xl backdrop-blur-sm transition-all duration-300 ${
              phase === 'GREEN'
                ? 'border-emerald-500/80 shadow-emerald-950/60'
                : phase === 'YELLOW'
                ? 'border-amber-500/80 shadow-amber-950/60'
                : 'border-rose-500/80 shadow-rose-950/60'
            }`}
          >
            {isEmergency ? (
              <div className="text-rose-400 flex flex-col items-center animate-bounce">
                <ShieldAlert className="w-5 h-5 text-rose-500" />
                <span className="text-[9px] font-bold uppercase tracking-tighter mt-0.5">
                  EMERGENCY
                </span>
                <span className="text-[10px] font-mono font-bold text-white uppercase">
                  {emergencyLane || 'ACTIVE'}
                </span>
                <span className="text-[10px] font-mono text-rose-300 font-bold">
                  {remainingSeconds}s
                </span>
              </div>
            ) : (
              <>
                <span
                  className={`text-[9px] font-bold uppercase tracking-wider px-1 py-0.2 rounded border ${
                    phase === 'GREEN'
                      ? 'bg-emerald-950/80 text-emerald-300 border-emerald-700'
                      : phase === 'YELLOW'
                      ? 'bg-amber-950/80 text-amber-300 border-amber-700'
                      : 'bg-rose-950/80 text-rose-300 border-rose-700'
                  }`}
                >
                  {phase}
                </span>

                <span className="text-[11px] font-bold text-white uppercase tracking-wider mt-1 font-mono">
                  {activeLanes.length > 0
                    ? activeLanes.join('+')
                    : 'CLEARANCE'}
                </span>

                {/* Transition target indication if in clearance */}
                {phase !== 'GREEN' && targetLanes.length > 0 && (
                  <span className="text-[8px] font-mono text-indigo-300 bg-indigo-950/60 px-1 rounded border border-indigo-700/50 mt-0.5">
                    → {targetLanes.join('+').toUpperCase()}
                  </span>
                )}

                <div
                  className={`flex items-baseline gap-0.5 mt-0.5 font-mono font-bold text-sm ${phaseColor}`}
                >
                  <span>{remainingSeconds}</span>
                  <span className="text-[9px] font-normal opacity-70">s</span>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Three-Layer Verification Strip: AI Proposal → Safety Gate → Controller Execution */}
      <div className="pt-2 border-t border-slate-700/80">
        <div className="text-[9px] font-bold uppercase tracking-wider text-slate-400 mb-1.5 flex items-center justify-between">
          <span>Three-Layer Control Flow</span>
          <span className="text-emerald-400 font-mono text-[8px]">
            AI PRIORITY → SAFETY PERMISSION → CONTROLLER
          </span>
        </div>
        <div className="grid grid-cols-3 gap-1.5 text-center text-xs">
          {/* Layer 1: AI Proposal */}
          <div className="bg-slate-900/80 border border-slate-700/60 rounded-lg p-1.5 flex flex-col justify-between">
            <div>
              <span className="text-[8px] font-bold uppercase tracking-wider text-indigo-400 block">
                1. AI Priority
              </span>
              <div className="font-mono font-bold text-slate-200 text-[11px] mt-0.5 truncate">
                {aiProposedLanes}
              </div>
            </div>
            <div className="text-[9px] text-slate-400 mt-1">
              Req:{' '}
              <span className="text-slate-200 font-mono font-medium">
                {aiProposedDuration}
              </span>
            </div>
          </div>

          {/* Layer 2: Safety Gate */}
          <div className="bg-slate-900/80 border border-slate-700/60 rounded-lg p-1.5 flex flex-col justify-between">
            <div>
              <span className="text-[8px] font-bold uppercase tracking-wider text-emerald-400 block">
                2. Safety Gate
              </span>
              <div
                className={`font-mono font-bold text-[11px] mt-0.5 ${safetyStatusColor}`}
              >
                {safetyLabel}
              </div>
            </div>
            <div className="text-[9px] text-slate-400 mt-1">
              Rules:{' '}
              <span className="text-emerald-400 font-medium">ENFORCED</span>
            </div>
          </div>

          {/* Layer 3: Controller Execution */}
          <div className="bg-slate-900/80 border border-slate-700/60 rounded-lg p-1.5 flex flex-col justify-between">
            <div>
              <span className="text-[8px] font-bold uppercase tracking-wider text-amber-400 block">
                3. Controller
              </span>
              <div className="font-mono font-bold text-slate-200 text-[11px] mt-0.5 truncate">
                {activeLanes.length > 0
                  ? activeLanes.join('+').toUpperCase()
                  : 'CLEARANCE'}
              </div>
            </div>
            <div className="text-[9px] text-slate-400 mt-1 font-mono">
              <span className={phaseColor}>{phase}</span> ({remainingSeconds}s)
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
