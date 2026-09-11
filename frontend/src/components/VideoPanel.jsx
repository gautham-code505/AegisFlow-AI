import React, { useState, useRef } from 'react';
import { Video, Upload, Eye, CheckCircle2, Camera, ArrowUp, ArrowDown, ArrowLeft, ArrowRight } from 'lucide-react';

const APPROACHES = [
  { key: 'north', label: 'North', Icon: ArrowDown, color: 'indigo' },
  { key: 'south', label: 'South', Icon: ArrowUp, color: 'emerald' },
  { key: 'east', label: 'East', Icon: ArrowLeft, color: 'amber' },
  { key: 'west', label: 'West', Icon: ArrowRight, color: 'violet' },
];

function ApproachPanel({ approach, trafficState, approachDetections, approachStatuses, isActive }) {
  const [mediaUrl, setMediaUrl] = useState(null);
  const [mediaType, setMediaType] = useState(null);
  const [uploadStatus, setUploadStatus] = useState('IDLE');
  const [naturalSize, setNaturalSize] = useState({ w: 640, h: 640 });
  const fileInputRef = useRef(null);

  const handleFileChange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setUploadStatus('UPLOADING');
    const isVideo = file.type.startsWith('video/');
    const isImage = file.type.startsWith('image/');

    try {
      if (isVideo) {
        const { uploadApproachVideo } = await import('../services/api');
        await uploadApproachVideo(approach.key, file);
      } else if (isImage) {
        const { uploadApproachImage } = await import('../services/api');
        await uploadApproachImage(approach.key, file);
      }
    } catch (err) {
      console.error(`Failed to upload for ${approach.key}:`, err);
    }

    setMediaUrl(URL.createObjectURL(file));
    setMediaType(isVideo ? 'video' : 'image');
    setUploadStatus('READY');
  };

  const laneData = trafficState?.lanes?.[approach.key];
  const detData = approachDetections?.[approach.key];
  const status = approachStatuses?.[approach.key] || 'WAITING_FOR_INPUT';
  const hasInput = status !== 'WAITING_FOR_INPUT';
  const rawDetections = hasInput ? (detData?.raw_detections || []) : [];
  
  const vehicleCount = hasInput ? (laneData?.vehicle_count ?? detData?.vehicle_count ?? '-') : '-';
  const occupancy = hasInput ? (laneData?.occupancy ?? detData?.occupancy ?? 0) : 0;
  const occupancyPct = hasInput ? ((laneData?.occupancy !== undefined || detData?.occupancy !== undefined) ? Math.round(occupancy * 100) : '-') : '-';
  const heavyCount = hasInput ? (laneData?.heavy_vehicle_count ?? detData?.heavy_vehicle_count ?? '-') : '-';
  const pedCount = hasInput ? (laneData?.pedestrian_count ?? detData?.pedestrian_count ?? '-') : '-';
  const classBreakdown = hasInput ? (detData?.class_breakdown || {}) : {};
  const ApproachIcon = approach.Icon;

  const activeBorder = isActive
    ? 'border-emerald-500/80 shadow-lg shadow-emerald-950/30'
    : 'border-slate-700/80 hover:border-slate-600';

  return (
    <div className={`rounded-xl overflow-hidden border transition-all bg-slate-900/70 ${activeBorder} flex flex-col`}>
      {/* Approach Header */}
      <div className="flex items-center justify-between px-3 py-2 bg-slate-800/80 border-b border-slate-700/60 shrink-0">
        <div className="flex items-center gap-2">
          <ApproachIcon className={`w-3.5 h-3.5 text-${approach.color}-400`} />
          <span className="text-xs font-bold uppercase tracking-wider text-slate-200">
            {approach.label}
          </span>
          {isActive && (
            <span className="px-1.5 py-0.5 text-[9px] font-bold bg-emerald-950 text-emerald-300 border border-emerald-700 rounded">
              GREEN
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            accept="video/mp4,video/avi,video/mov,image/jpeg,image/png,image/webp"
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            className="flex items-center gap-1 px-2 py-0.5 text-[10px] font-semibold rounded bg-indigo-600/30 text-indigo-300 border border-indigo-500/50 hover:bg-indigo-600/50 transition-all"
          >
            <Upload className="w-3 h-3" />
            <span>{uploadStatus === 'UPLOADING' ? '...' : 'Upload'}</span>
          </button>
        </div>
      </div>

      {/* Media Viewport */}
      <div className="relative aspect-video bg-slate-950 flex items-center justify-center overflow-hidden shrink-0">
        {mediaUrl && mediaType === 'video' ? (
          <video 
            src={mediaUrl} 
            autoPlay 
            loop 
            muted 
            onLoadedMetadata={(e) => setNaturalSize({ w: e.target.videoWidth, h: e.target.videoHeight })}
            className="w-full h-full object-fill opacity-80" 
          />
        ) : mediaUrl && mediaType === 'image' ? (
          <img 
            src={mediaUrl} 
            alt={`${approach.label} approach`} 
            onLoad={(e) => setNaturalSize({ w: e.target.naturalWidth, h: e.target.naturalHeight })}
            className="w-full h-full object-fill opacity-80" 
          />
        ) : status === 'PROCESSING' ? (
          <div className="flex flex-col items-center justify-center text-center p-4 opacity-80">
            <div className="w-6 h-6 border-2 border-slate-400 border-t-emerald-400 rounded-full animate-spin mb-2"></div>
            <p className="text-[10px] text-emerald-400 font-bold uppercase">
              Processing...
            </p>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center text-center p-4 opacity-60">
            <Camera className={`w-6 h-6 text-${approach.color}-400 mb-1`} />
            <p className="text-[10px] text-slate-400">
              Upload {approach.label} video/image
            </p>
          </div>
        )}

        {/* Real YOLO Detections Overlay */}
        {mediaUrl && rawDetections.length > 0 && (
          <div className="absolute inset-0 pointer-events-none">
            {rawDetections.map((det, idx) => {
              const [x1, y1, x2, y2] = det.bbox;
              const { w, h } = naturalSize;
              const left = (x1 / w) * 100;
              const top = (y1 / h) * 100;
              const width = ((x2 - x1) / w) * 100;
              const height = ((y2 - y1) / h) * 100;
              
              // Map class to color
              let boxColor = 'border-emerald-400';
              let textBg = 'bg-emerald-500/80';
              if (det.class === 'person') { boxColor = 'border-amber-400'; textBg = 'bg-amber-500/80'; }
              if (det.class === 'bus' || det.class === 'truck') { boxColor = 'border-rose-400'; textBg = 'bg-rose-500/80'; }

              return (
                <div 
                  key={idx}
                  className={`absolute border-[1.5px] ${boxColor} shadow-[0_0_8px_rgba(0,0,0,0.5)]`}
                  style={{
                    left: `${left}%`,
                    top: `${top}%`,
                    width: `${width}%`,
                    height: `${height}%`,
                  }}
                >
                  <div className={`absolute -top-3.5 left-[-1.5px] px-1 py-0.5 text-[8px] font-bold text-white uppercase tracking-wider ${textBg}`}>
                    {det.class} {(det.confidence * 100).toFixed(0)}%
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Metrics Bar */}
      <div className="px-2 py-2 bg-slate-900/90 border-t border-slate-800/60 flex-1 flex flex-col justify-between">
        <div className="grid grid-cols-4 gap-1 text-[10px]">
          <div className="text-center">
            <span className="text-slate-500 block mb-0.5">Vehicles</span>
            <span className="font-bold text-white font-mono">{vehicleCount}</span>
          </div>
          <div className="text-center">
            <span className="text-slate-500 block mb-0.5 truncate" title="Demand Ratio">Demand Ratio</span>
            <span className={`font-bold font-mono ${occupancyPct >= 75 ? 'text-rose-400' : occupancyPct >= 40 ? 'text-amber-400' : 'text-emerald-400'}`}>
              {occupancyPct}%
            </span>
          </div>
          <div className="text-center">
            <span className="text-slate-500 block mb-0.5">Heavy</span>
            <span className="font-bold text-slate-300 font-mono">{heavyCount}</span>
          </div>
          <div className="text-center">
            <span className="text-slate-500 block mb-0.5">Peds</span>
            <span className="font-bold text-slate-300 font-mono">{pedCount}</span>
          </div>
        </div>

        {/* Class breakdown chips */}
        {Object.keys(classBreakdown).length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1.5 pt-1.5 border-t border-slate-800/60">
            {Object.entries(classBreakdown).map(([cls, count]) => (
              <span key={cls} className="px-1 py-0 text-[9px] font-mono font-semibold bg-slate-800 text-slate-300 rounded border border-slate-700/60">
                {cls}: {count}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export function VideoPanel({ systemStatus, trafficState, approachDetections, approachStatuses, signalDecision }) {
  const activeLane = signalDecision?.selected_lane || 'north';
  const isWarningState = systemStatus?.camera === 'warning' || systemStatus?.ai === 'offline';

  const totalVehicles = trafficState?.lanes
    ? Object.values(trafficState.lanes).reduce((sum, lane) => sum + (lane.vehicle_count || 0), 0)
    : 0;

  return (
    <div className="control-card rounded-xl p-4 flex flex-col justify-between h-full">
      {/* Panel Header */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-700/80">
        <div className="flex items-center gap-2">
          <div className={`p-1 rounded ${isWarningState ? 'bg-amber-500/20 text-amber-400' : 'bg-indigo-500/20 text-indigo-400'}`}>
            <Video className="w-4 h-4" />
          </div>
          <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wider">
            4-Approach YOLO Perception
          </h2>
        </div>
        <div className="flex items-center gap-2 text-[11px] font-mono">
          <span className="flex items-center gap-1 font-semibold text-emerald-400">
            <Eye className="w-3.5 h-3.5" />
            YOLOv8: {isWarningState ? 'FALLBACK' : 'ACTIVE'}
          </span>
          <span className="text-slate-400">
            Total: <strong className="text-white">{totalVehicles}</strong>
          </span>
        </div>
      </div>

      {/* 4-Approach Grid */}
      <div className="grid grid-cols-2 gap-3 my-3 flex-1">
        {APPROACHES.map((approach) => (
          <ApproachPanel
            key={approach.key}
            approach={approach}
            trafficState={trafficState}
            approachDetections={approachDetections}
            approachStatuses={approachStatuses}
            isActive={activeLane === approach.key}
          />
        ))}
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between text-xs text-slate-400 pt-1">
        <span className="flex items-center gap-1">
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
          <span>Real YOLO inference • Live Bounding Boxes</span>
        </span>
        <span className="text-[11px] text-slate-500">MP4 / AVI / JPG / PNG / WEBP</span>
      </div>
    </div>
  );
}
