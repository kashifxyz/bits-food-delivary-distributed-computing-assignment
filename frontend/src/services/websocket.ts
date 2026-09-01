type WebSocketCallback = (eventData: any) => void;

class WebSocketClient {
  private ws: WebSocket | null = null;
  private listeners: WebSocketCallback[] = [];
  private url = 'ws://localhost:8000/ws/events';
  private reconnectInterval: any = null;

  connect() {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        console.log('[WS] Connected to Distributed Monitor WebSocket');
        if (this.reconnectInterval) {
          clearInterval(this.reconnectInterval);
          this.reconnectInterval = null;
        }
      };

      this.ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          this.listeners.forEach((listener) => listener(payload));
        } catch (e) {
          console.error('[WS] Parse error:', e);
        }
      };

      this.ws.onclose = () => {
        console.warn('[WS] Disconnected. Attempting reconnect...');
        this.reconnect();
      };

      this.ws.onerror = (err) => {
        console.error('[WS] Error:', err);
        this.ws?.close();
      };
    } catch (e) {
      this.reconnect();
    }
  }

  private reconnect() {
    if (!this.reconnectInterval) {
      this.reconnectInterval = setInterval(() => {
        this.connect();
      }, 2000);
    }
  }

  subscribe(callback: WebSocketCallback) {
    this.listeners.push(callback);
    return () => {
      this.listeners = this.listeners.filter((l) => l !== callback);
    };
  }
}

export const wsClient = new WebSocketClient();
