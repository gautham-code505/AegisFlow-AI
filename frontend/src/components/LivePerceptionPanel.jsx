import React, { useState, useRef } from 'react';
import { Camera, Upload, Play, Square, Video, Image as ImageIcon } from 'lucide-react';
import { uploadTrafficVideo } from '../services/api';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

export function LivePerceptionPanel({ systemStatus, trafficState }) {
  const [uploadStatus, setUploadStatus] = useState('IDLE');
  const [selectedFile, setSelectedFile] = useState(null);
  const [inputType, setInputType] = useState('camera'); // 'camera' or 'video'
  const fileInputRef = useRef(null);

  const isVisionOnline = systemStatus?.vision === 'PROCESSING';
  const source = systemStatus?.camera || 'NO INPUT';
  const hasTracking = trafficState?.has_tracking_data;
  
  // Stream URL adds a timestamp to bust cache when restarting
  const streamUrl = isVisionOnline ? `${API_BASE_URL}/api/v1/video/stream?t=${Date.now()}` : null;

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setSelectedFile(file);
    }
  };

  const handleStartProcessing = async () => {
    if (inputType === 'video' && !selectedFile) return;
    setUploadStatus('UPLOADING');
    try {
      if (inputType === 'video') {
        await uploadTrafficVideo(selectedFile);
      } else if (inputType === 'camera') {
        const response = await fetch(`${API_BASE_URL}/api/v1/camera/start`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ source: 2 })
        });
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.detail || `HTTP error ${response.status}`);
        }
      }
      setUploadStatus('PROCESSING');
    } catch (error) {
      console.error('Failed to start processing:', error);
      alert(`Camera start failed: ${error.message}`);
      setUploadStatus('ERROR');
    }
  };

  // Derive counts from trafficState
  let totalVehicles = trafficState?.total_vehicles || 0;
  let unassignedCount = trafficState?.unassigned_vehicles || 0;
  
  const approachCounts = { north: 0, east: 0, south: 0, west: 0 };
  let carCount = 0;
  let heavyCount = 0;
  let pedCount = 0;
  
  if (trafficState?.total_classes) {
    Object.entries(trafficState.total_classes).forEach(([cls, count]) => {
      if (['car', 'motorcycle'].includes(cls)) {
        carCount += count;
      } else if (['bus', 'truck'].includes(cls)) {
        heavyCount += count;
      } else if (cls === 'person') {
        pedCount += count;
      }
    });
  }

  if (trafficState?.lanes) {
    Object.entries(trafficState.lanes).forEach(([lane, data]) => {
      const l = lane.toLowerCase();
      if (approachCounts[l] !== undefined) {
        approachCounts[l] = data.vehicle_count || 0;
      }
    });
  }

  return (
    <div className="bg-slate-900/60 rounded-xl border border-slate-700/80 shadow-lg overflow-hidden flex flex-col md:flex-row h-[480px]">
      
      {/* LEFT: Video Stream Area */}
      <div className="relative flex-1 bg-black flex flex-col items-center justify-center min-h-[300px] border-r border-slate-700/80">
        {/* Header Bar */}
        <div className="absolute top-0 left-0 right-0 p-3 bg-gradient-to-b from-black/80 to-transparent z-10 flex justify-between items-center">
          <div className="flex items-center gap-2">
            <div className={`w-2.5 h-2.5 rounded-full animate-pulse ${isVisionOnline ? 'bg-emerald-500' : 'bg-slate-500'}`} />
            <span className="text-sm font-bold text-slate-100 tracking-wider">LIVE PERCEPTION</span>
          </div>
          {isVisionOnline && (
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2 text-xs font-semibold px-2 py-1 bg-slate-800/80 text-emerald-400 rounded border border-slate-700">
                <Camera className="w-3.5 h-3.5" />
                <span>{source}</span>
              </div>
            </div>
          )}
        </div>
        
        {/* Stream Content */}
        {isVisionOnline ? (
          <img 
            src={streamUrl} 
            alt="Live perception stream" 
            className="w-full h-full object-contain"
            onError={(e) => { e.target.style.display = 'none'; }}
          />
        ) : (
          <div className="text-center text-slate-500 flex flex-col items-center">
            {inputType === 'camera' ? (
              <>
                <Camera className="w-12 h-12 mb-3 opacity-50" />
                <p className="font-semibold text-lg">No Active Camera</p>
                <p className="text-sm mt-1">Start the camera to begin live perception</p>
              </>
            ) : (
              <>
                <Video className="w-12 h-12 mb-3 opacity-50" />
                <p className="font-semibold text-lg">No Active Video</p>
                <p className="text-sm mt-1">Choose a traffic video to begin perception</p>
              </>
            )}
          </div>
        )}
      </div>

      {/* RIGHT: Controls & Data */}
      <div className="w-full md:w-80 bg-slate-800/50 flex flex-col">
        
        {/* Control Section */}
        <div className="p-4 border-b border-slate-700/80">
          <div className="flex justify-between items-center mb-3">
            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider">Input Source</h3>
          </div>
          
          <div className="flex bg-slate-900 rounded-lg p-1 mb-3 border border-slate-700/50">
            <button
              onClick={() => { setInputType('camera'); setSelectedFile(null); }}
              className={`flex-1 text-xs font-bold py-1.5 rounded-md flex justify-center items-center gap-1.5 transition-colors ${inputType === 'camera' ? 'bg-slate-700 text-white' : 'text-slate-400 hover:text-slate-300'}`}
            >
              <Camera className="w-3.5 h-3.5" />
              Live Camera
            </button>
            <button
              onClick={() => { setInputType('video'); setSelectedFile(null); }}
              className={`flex-1 text-xs font-bold py-1.5 rounded-md flex justify-center items-center gap-1.5 transition-colors ${inputType === 'video' ? 'bg-slate-700 text-white' : 'text-slate-400 hover:text-slate-300'}`}
            >
              <Video className="w-3.5 h-3.5" />
              Video
            </button>
          </div>

          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            accept="video/mp4,video/avi,video/mov"
            className="hidden"
          />
          
          <div className="space-y-3">
            {inputType === 'video' && (
              <button
                onClick={() => fileInputRef.current?.click()}
                className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-slate-700/50 hover:bg-slate-700 text-slate-200 rounded-lg border border-slate-600 transition-colors text-sm font-medium"
              >
                <Video className="w-4 h-4" />
                <span className="truncate">{selectedFile ? selectedFile.name : 'Choose Traffic Video (.mp4)'}</span>
              </button>
            )}
            
            <div className="flex gap-2">
              <button
                onClick={handleStartProcessing}
                disabled={(inputType === 'video' && !selectedFile) || uploadStatus === 'UPLOADING' || isVisionOnline}
                className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:hover:bg-emerald-600 text-white rounded-lg transition-colors text-sm font-bold"
              >
                {uploadStatus === 'UPLOADING' ? (
                  <span className="animate-pulse">Starting...</span>
                ) : (
                  <>
                    <Play className="w-4 h-4 fill-current" />
                    <span>{inputType === 'video' ? 'Start Processing' : 'Start Camera'}</span>
                  </>
                )}
              </button>
              
              <button
                disabled={!isVisionOnline}
                onClick={async () => {
                  try { await fetch(`${API_BASE_URL}/api/v1/camera/stop`, { method: 'POST' }); } catch(e) {}
                  setUploadStatus('IDLE');
                }}
                className="flex items-center justify-center px-4 py-2 bg-rose-600/20 hover:bg-rose-600/40 text-rose-400 disabled:opacity-50 border border-rose-500/30 rounded-lg transition-colors"
              >
                <Square className="w-4 h-4 fill-current" />
              </button>
            </div>
          </div>
        </div>

        {/* Data Section */}
        <div className="flex-1 p-4 overflow-y-auto">
          <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-4">Detections</h3>
          
          <div className="grid grid-cols-2 gap-3 mb-6">
            <div className="bg-slate-900/80 rounded-lg p-3 border border-slate-700/50">
              <div className="text-xs text-slate-400 mb-1">Total Vehicles</div>
              <div className="text-2xl font-bold text-indigo-400">{isVisionOnline ? totalVehicles : '-'}</div>
            </div>
            <div className="bg-slate-900/80 rounded-lg p-3 border border-slate-700/50">
              <div className="text-xs text-slate-400 mb-1">Tracking</div>
              <div className={`text-[10px] font-bold mt-2 ${
                  hasTracking ? 'text-emerald-400' : 
                  (source === 'IMAGE' ? 'text-amber-400' : 'text-slate-500')
                }`}>
                {hasTracking ? 'ACTIVE (ByteTrack)' : (source === 'IMAGE' ? 'NOT APPLICABLE — SINGLE FRAME' : 'DISABLED')}
              </div>
            </div>
          </div>
          
          {/* Approaches */}
          <div className="space-y-2 mb-6">
            {Object.entries(approachCounts).map(([app, count]) => (
              <div key={app} className="flex justify-between items-center text-sm">
                <span className="font-semibold text-slate-300 uppercase">{app}</span>
                <span className="font-mono text-slate-100 bg-slate-900 px-2 py-0.5 rounded border border-slate-700">
                  {isVisionOnline ? count : '-'}
                </span>
              </div>
            ))}
            <div className="flex justify-between items-center text-sm mt-3 pt-3 border-t border-slate-700/50">
              <span className="font-semibold text-slate-400 uppercase">Unassigned</span>
              <span className="font-mono text-amber-400/80 bg-slate-900 px-2 py-0.5 rounded border border-slate-700">
                {isVisionOnline ? unassignedCount : '-'}
              </span>
            </div>
          </div>
          
          {/* Classes */}
          <div className="space-y-2">
            <div className="flex justify-between items-center text-sm">
              <span className="text-slate-400">Cars</span>
              <span className="font-mono text-slate-300">{isVisionOnline ? carCount : '-'}</span>
            </div>
            <div className="flex justify-between items-center text-sm">
              <span className="text-slate-400">Heavy (Bus/Truck)</span>
              <span className="font-mono text-slate-300">{isVisionOnline ? heavyCount : '-'}</span>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
