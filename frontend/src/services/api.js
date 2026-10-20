// API Service Abstraction Layer for AegisFlow AI Backend Integration

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

export async function fetchSystemStatus() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/status`);
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.warn('[AegisFlow API] Status fetch failed, falling back:', error.message);
    return null;
  }
}

export async function uploadTrafficVideo(file) {
  try {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_BASE_URL}/api/v1/video/upload`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) throw new Error(`Upload failed with status: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.warn('[AegisFlow API] Video upload failed:', error.message);
    throw error;
  }
}

export async function uploadTrafficImage(file) {
  try {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_BASE_URL}/api/v1/image/upload`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) throw new Error(`Upload failed with status: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.warn('[AegisFlow API] Image upload failed:', error.message);
    throw error;
  }
}

export async function fetchCurrentTrafficState() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/traffic-state`);
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.warn('[AegisFlow API] Traffic state fetch failed:', error.message);
    return null;
  }
}

export async function fetchSnapshot() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/snapshot`);
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.warn('[AegisFlow API] Snapshot fetch failed:', error.message);
    return null;
  }
}

export async function postOverride(selectedLane, duration) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/overrides`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ selected_lane: selectedLane, duration: duration })
    });
    if (!response.ok) throw new Error(`Override failed: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error('[AegisFlow API] Override failed:', error.message);
    throw error;
  }
}

export async function deleteOverride() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/overrides/current`, {
      method: 'DELETE'
    });
    if (!response.ok) throw new Error(`Delete override failed: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error('[AegisFlow API] Delete override failed:', error.message);
    throw error;
  }
}

export async function triggerEmergency(lane) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/demo/emergency/${lane}`, {
      method: 'POST'
    });
    if (!response.ok) throw new Error(`Emergency trigger failed: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error('[AegisFlow API] Emergency trigger failed:', error.message);
    throw error;
  }
}

export async function clearEmergency() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/demo/emergency/clear`, {
      method: 'POST'
    });
    if (!response.ok) throw new Error(`Emergency clear failed: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error('[AegisFlow API] Emergency clear failed:', error.message);
    throw error;
  }
}


// ═══════════════════════════════════════════════════════════
//  4-APPROACH PER-DIRECTION UPLOAD FUNCTIONS
// ═══════════════════════════════════════════════════════════

/**
 * @deprecated The 4-approach video upload API is deprecated. Use the canonical one-camera pipeline.
 */
export async function uploadApproachVideo(approach, file) {
  try {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_BASE_URL}/api/v1/video/upload/${approach}`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) throw new Error(`Approach video upload failed: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.warn(`[AegisFlow API] Approach video upload failed for ${approach}:`, error.message);
    throw error;
  }
}

/**
 * @deprecated The 4-approach image upload API is deprecated. Use the canonical one-camera pipeline.
 */
export async function uploadApproachImage(approach, file) {
  try {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_BASE_URL}/api/v1/image/upload/${approach}`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) throw new Error(`Approach image upload failed: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.warn(`[AegisFlow API] Approach image upload failed for ${approach}:`, error.message);
    throw error;
  }
}

export async function resetApproach(approach) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/traffic/reset/${approach}`, {
      method: 'POST'
    });
    if (!response.ok) throw new Error(`Reset approach failed: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error(`[AegisFlow API] Reset approach failed for ${approach}:`, error.message);
    throw error;
  }
}

export async function resetTrafficState() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/traffic/reset`, {
      method: 'POST'
    });
    if (!response.ok) throw new Error(`Reset traffic state failed: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error('[AegisFlow API] Reset traffic state failed:', error.message);
    throw error;
  }
}


// ---------------------------------------------------------------------------
// Four-direction manual scan
// ---------------------------------------------------------------------------

export const scanImageUrl = (approach, version) =>
  `${API_BASE_URL}/api/v1/scan/${approach}/image?annotated=true&v=${version || ''}`;

export const videoStreamUrl = () => `${API_BASE_URL}/api/v1/video/stream`;

async function scanRequest(path, method = 'POST', body) {
  const response = await fetch(`${API_BASE_URL}/api/v1/scan${path}`, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || `Scan request failed: ${response.status}`);
  }
  return data;
}

export const fetchScanStatus = () => scanRequest('', 'GET');
export const startScan = (source) => scanRequest('/start', 'POST', { source: source ?? null });
export const stopScan = () => scanRequest('/stop');
export const newScan = () => scanRequest('/new');
export const captureApproach = (approach) => scanRequest(`/${approach}/capture`);
export const confirmApproach = (approach) => scanRequest(`/${approach}/confirm`);
export const retakeApproach = (approach) => scanRequest(`/${approach}/retake`);
export const applyScan = () => scanRequest('/apply');
