// API Service Abstraction Layer for AegisFlow AI Backend Integration

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

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
    formData.append('video', file);

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
