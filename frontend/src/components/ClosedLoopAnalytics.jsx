import React from 'react';
import { BarChart3, CheckCircle2, Clock, AlertCircle } from 'lucide-react';

export function ClosedLoopAnalytics({ measurements = [], analytics = {} }) {
  // Sort measurements by end_timestamp descending
  const completedMeasurements = measurements
    .filter(m => m.end_timestamp)
    .sort((a, b) => b.end_timestamp - a.end_timestamp);

  const getMetricDelta = (before, after) => {
    if (before === null || before === undefined || after === null || after === undefined) {
      return null;
    }
    return after - before;
  };

  const renderDelta = (delta, label, unit = '', isInverseGood = true) => {
    if (delta === null) return <span className="text-slate-500">N/A</span>;
    
    // For queues and wait times, negative delta is an improvement.
    const isImproved = isInverseGood ? delta < 0 : delta > 0;
    const isNeutral = delta === 0;
    
    let colorClass = 'text-slate-400';
    let prefix = '';
    
    if (isImproved) {
      colorClass = 'text-emerald-400';
      prefix = '';
    } else if (!isNeutral) {
      colorClass = 'text-rose-400';
      prefix = '+';
    }

    return (
      <div className="flex flex-col">
        <span className="text-xs text-slate-400 font-medium">{label}</span>
        <span className={`text-sm font-bold ${colorClass}`}>
          {prefix}{typeof delta === 'number' && delta % 1 !== 0 ? delta.toFixed(1) : delta}{unit}
        </span>
      </div>
    );
  };

  const renderTopMetric = (label, value, unit = '') => (
    <div className="bg-slate-800/40 rounded-lg p-3 border border-slate-700/50">
      <div className="text-xs text-slate-400 font-mono tracking-wider mb-1">{label}</div>
      <div className="text-xl font-bold text-slate-200">
        {value === null || value === undefined ? (
          <span className="text-sm text-slate-500 font-normal">Insufficient data</span>
        ) : (
          <>{value}{unit}</>
        )}
      </div>
    </div>
  );

  return (
    <div className="control-card rounded-xl p-4 mt-4">
      <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-700/80">
        <div className="flex items-center gap-2">
          <div className="p-1 bg-indigo-500/20 text-indigo-400 rounded">
            <BarChart3 className="w-4 h-4" />
          </div>
          <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wider">
            Closed-Loop Service Analytics
          </h2>
        </div>
        <div className="text-xs text-slate-400 uppercase tracking-widest font-mono">
          Last {Math.min(completedMeasurements.length, 5)} Measurements
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-3 mb-6">
        {renderTopMetric('Avg Obs. Wait', analytics.average_observed_wait, 's')}
        {renderTopMetric('Max Obs. Wait', analytics.maximum_observed_wait, 's')}
        {renderTopMetric('Avg Queue Before', analytics.average_queue_before)}
        {renderTopMetric('Obs. Queue Change', analytics.average_observed_queue_change)}
        {renderTopMetric('Obs. Wait Change', analytics.average_observed_wait_change, 's')}
        {renderTopMetric('Service Intervals', analytics.completed_service_intervals)}
        {renderTopMetric('Adaptive Decisions', analytics.decision_counts?.NORMAL || 0)}
        {renderTopMetric('Emergency Events', analytics.emergency_event_count)}
        {renderTopMetric('Safety Rejections', analytics.safety_rejection_count)}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm whitespace-nowrap">
          <thead className="bg-slate-800/50 text-slate-400 text-xs uppercase font-mono tracking-wider">
            <tr>
              <th className="p-3 rounded-tl-lg">Service Phase</th>
              <th className="p-3">Priority / Reason</th>
              <th className="p-3">Duration</th>
              <th className="p-3">Tracking</th>
              <th className="p-3">Observed Queue Change</th>
              <th className="p-3">Observed Avg Wait Change</th>
              <th className="p-3 rounded-tr-lg">Observed Max Wait Change</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/50">
            {completedMeasurements.length === 0 && (
              <tr>
                <td colSpan="7" className="p-8 text-center text-slate-500 font-mono text-sm">
                  Waiting for completed service intervals...
                </td>
              </tr>
            )}
            
            {completedMeasurements.slice(0, 5).map((m) => {
              const queueDelta = getMetricDelta(m.queue_before, m.queue_after);
              const avgWaitDelta = getMetricDelta(m.wait_avg_before, m.wait_avg_after);
              const maxWaitDelta = getMetricDelta(m.wait_max_before, m.wait_max_after);
              const lanesStr = m.target_lanes.map(l => l.toUpperCase()).join(' + ');
              
              return (
                <tr key={m.measurement_id} className="hover:bg-slate-800/20 transition-colors">
                  <td className="p-3">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                      <span className="font-bold text-slate-200">{lanesStr}</span>
                    </div>
                  </td>
                  <td className="p-3">
                    <div className="flex flex-col">
                      <span className="font-bold text-slate-300">{m.priority_type}</span>
                      <span className="text-xs text-slate-500 truncate max-w-[200px]" title={m.decision_reason}>
                        {m.decision_reason || 'Adaptive'}
                      </span>
                    </div>
                  </td>
                  <td className="p-3 font-mono text-slate-300">
                    {m.green_duration ? `${m.green_duration.toFixed(1)}s` : 'N/A'}
                  </td>
                  <td className="p-3">
                    {m.has_tracking_data ? (
                      <span className="px-2 py-1 bg-emerald-500/10 text-emerald-400 text-xs rounded border border-emerald-500/20">
                        Available
                      </span>
                    ) : (
                      <span className="px-2 py-1 bg-rose-500/10 text-rose-400 text-xs rounded border border-rose-500/20">
                        Unavailable
                      </span>
                    )}
                  </td>
                  <td className="p-3">
                    {m.has_tracking_data ? renderDelta(queueDelta, 'Vehicles') : <span className="text-slate-600">Measurement Unavailable</span>}
                  </td>
                  <td className="p-3">
                    {m.has_tracking_data ? renderDelta(avgWaitDelta, 'Seconds', 's') : <span className="text-slate-600">Measurement Unavailable</span>}
                  </td>
                  <td className="p-3">
                    {m.has_tracking_data ? renderDelta(maxWaitDelta, 'Seconds', 's') : <span className="text-slate-600">Measurement Unavailable</span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
