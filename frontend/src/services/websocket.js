// WebSocket Service Abstraction for Real-Time Traffic Updates

const WS_BASE_URL = import.meta.env.VITE_WS_URL || 'ws://127.0.0.1:8000/ws/traffic';

export function createTrafficWebSocket({ onMessage, onError, onStatusChange }) {
  let socket = null;
  let reconnectInterval = null;
  let isIntentionallyClosed = false;

  function connect() {
    try {
      onStatusChange?.('CONNECTING');
      socket = new WebSocket(WS_BASE_URL);

      socket.onopen = () => {
        console.log('[AegisFlow WS] Connection established');
        onStatusChange?.('CONNECTED');
        if (reconnectInterval) {
          clearInterval(reconnectInterval);
          reconnectInterval = null;
        }
      };

      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          onMessage?.(payload);
        } catch (err) {
          console.error('[AegisFlow WS] Message parsing error:', err);
        }
      };

      socket.onerror = (error) => {
        console.warn('[AegisFlow WS] Connection error:', error);
        onError?.(error);
      };

      socket.onclose = () => {
        onStatusChange?.('DISCONNECTED');
        if (!isIntentionallyClosed && !reconnectInterval) {
          reconnectInterval = setInterval(() => {
            console.log('[AegisFlow WS] Attempting reconnection...');
            connect();
          }, 5000);
        }
      };
    } catch (err) {
      console.warn('[AegisFlow WS] Initialization exception:', err);
      onStatusChange?.('DISCONNECTED');
    }
  }

  connect();

  return {
    disconnect: () => {
      isIntentionallyClosed = true;
      if (reconnectInterval) clearInterval(reconnectInterval);
      if (socket) socket.close();
    },
    send: (data) => {
      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify(data));
      }
    },
  };
}
