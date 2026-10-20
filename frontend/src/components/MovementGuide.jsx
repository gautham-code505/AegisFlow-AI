import React from 'react';
import { Navigation, OctagonX, TriangleAlert } from 'lucide-react';

// Where vehicles from each approach exit, by movement. Lane names are the approach
// the vehicle comes FROM (NORTH = vehicles entering from the north edge, heading south).
const MOVEMENTS = {
  north: { straight: 'south', left: 'east', right: 'west' },
  east: { straight: 'west', left: 'south', right: 'north' },
  south: { straight: 'north', left: 'west', right: 'east' },
  west: { straight: 'east', left: 'north', right: 'south' },
};

// Diagram is drawn for NORTH and rotated clockwise for the other approaches.
const ROTATION = { north: 0, east: 90, south: 180, west: 270 };

const ALL_LANES = ['north', 'east', 'south', 'west'];
const upper = (lane) => String(lane).toUpperCase();

function JunctionDiagram({ fromLane, color }) {
  return (
    <svg viewBox="0 0 160 160" className="w-36 h-36 shrink-0" role="img"
      aria-label={fromLane ? `Permitted movements from ${upper(fromLane)}` : 'All approaches stopped'}>
      {/* Roads */}
      <rect x="55" y="0" width="50" height="160" className="fill-slate-800" />
      <rect x="0" y="55" width="160" height="50" className="fill-slate-800" />
      <rect x="55" y="55" width="50" height="50" className="fill-slate-700/60" />
      {/* Compass labels */}
      <text x="80" y="12" textAnchor="middle" className="fill-slate-400 text-[10px] font-bold">N</text>
      <text x="80" y="156" textAnchor="middle" className="fill-slate-400 text-[10px] font-bold">S</text>
      <text x="152" y="84" textAnchor="middle" className="fill-slate-400 text-[10px] font-bold">E</text>
      <text x="8" y="84" textAnchor="middle" className="fill-slate-400 text-[10px] font-bold">W</text>
      {fromLane && (
        <g transform={`rotate(${ROTATION[fromLane]} 80 80)`} className={color} fill="none"
          stroke="currentColor" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round">
          <defs>
            <marker id="mg-arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="4" markerHeight="4" orient="auto-start-reverse">
              <path d="M0,0 L10,5 L0,10 z" fill="currentColor" stroke="none" />
            </marker>
          </defs>
          {/* Straight: north edge to south edge */}
          <path d="M80 20 L80 140" markerEnd="url(#mg-arrow)" />
          {/* Left (heading south, left is east) */}
          <path d="M80 30 Q80 80 140 80" markerEnd="url(#mg-arrow)" />
          {/* Right (heading south, right is west) */}
          <path d="M80 30 Q80 80 20 80" markerEnd="url(#mg-arrow)" />
        </g>
      )}
      {!fromLane && (
        <g className="text-rose-400" stroke="currentColor" strokeWidth="6" strokeLinecap="round">
          <line x1="64" y1="64" x2="96" y2="96" />
          <line x1="96" y1="64" x2="64" y2="96" />
        </g>
      )}
    </svg>
  );
}

function MovementRow({ label, to, tone }) {
  return (
    <div className="flex items-center justify-between rounded-md bg-slate-900/60 border border-slate-700/60 px-3 py-1.5">
      <span className="text-xs text-slate-300">{label}</span>
      <span className={`text-xs font-bold font-mono ${tone}`}>to {upper(to)}</span>
    </div>
  );
}

export function MovementGuide({ signalState, isStale = false }) {
  // Read the per-approach light colours: exactly what the physical signal heads show.
  const colorOf = (lane) => String(signalState?.[lane] || 'RED').toUpperCase();
  const greenLanes = ALL_LANES.filter((lane) => colorOf(lane) === 'GREEN');
  const yellowLanes = ALL_LANES.filter((lane) => colorOf(lane) === 'YELLOW');
  const isGreen = !isStale && greenLanes.length === 1 && yellowLanes.length === 0;
  const isYellow = !isStale && yellowLanes.length === 1 && greenLanes.length === 0;
  const isUnexpected = !isStale && greenLanes.length + yellowLanes.length > 1;
  const fromLane = isGreen ? greenLanes[0] : isYellow ? yellowLanes[0] : null;
  const stoppedLanes = ALL_LANES.filter((lane) => lane !== fromLane);

  let title;
  let subtitle;
  let Icon = OctagonX;
  let accent = 'text-rose-400';
  if (isStale) {
    title = 'Live signal data unavailable';
    subtitle = 'Dashboard is not receiving signal updates. Treat every approach as STOP.';
  } else if (isUnexpected) {
    title = 'More than one approach active';
    subtitle = 'Not expected under single-approach phasing. Check the controller.';
    Icon = TriangleAlert;
    accent = 'text-amber-400';
  } else if (isGreen) {
    title = `Vehicles from ${upper(fromLane)} may go`;
    subtitle = 'Protected phase: every other approach is held at RED.';
    Icon = Navigation;
    accent = 'text-emerald-400';
  } else if (isYellow) {
    title = `${upper(fromLane)} clearing`;
    subtitle = 'Stop if it is safe to do so; vehicles already in the junction finish crossing.';
    Icon = TriangleAlert;
    accent = 'text-amber-400';
  } else {
    title = 'All approaches STOP';
    subtitle = 'All-red clearance: the junction empties before the next approach gets green.';
  }

  const moves = fromLane ? MOVEMENTS[fromLane] : null;

  return (
    <div className="control-card rounded-xl p-4">
      <div className="flex items-center justify-between pb-3 border-b border-slate-700/80">
        <div className="flex items-center gap-2">
          <div className="p-1 bg-emerald-500/20 text-emerald-400 rounded">
            <Navigation className="w-4 h-4" />
          </div>
          <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wider">
            Permitted Vehicle Movements
          </h2>
        </div>
        <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400">
          One approach green at a time
        </span>
      </div>

      <div className="mt-3 flex flex-col sm:flex-row gap-4 items-center sm:items-start">
        <JunctionDiagram fromLane={fromLane}
          color={isGreen ? 'text-emerald-400' : 'text-amber-400'} />

        <div className="flex-1 w-full min-w-0 space-y-2">
          <div className="flex items-start gap-2">
            <Icon className={`w-5 h-5 shrink-0 ${accent}`} />
            <div>
              <p className={`text-sm font-bold ${accent}`}>{title}</p>
              <p className="text-xs text-slate-400">{subtitle}</p>
            </div>
          </div>

          {isGreen && moves && (
            <div className="grid gap-1.5">
              <MovementRow label="Straight" to={moves.straight} tone="text-emerald-300" />
              <MovementRow label="Turn left" to={moves.left} tone="text-emerald-300" />
              <MovementRow label="Turn right" to={moves.right} tone="text-emerald-300" />
            </div>
          )}

          <div className="flex flex-wrap gap-1.5 pt-1">
            {(isGreen || isYellow ? stoppedLanes : ALL_LANES).map((lane) => (
              <span key={lane} className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded border border-rose-800 bg-rose-950/60 text-rose-300">
                {upper(lane)}: STOP
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
