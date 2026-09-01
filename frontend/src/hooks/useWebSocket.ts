import { useEffect } from 'react';
import { wsClient } from '../services/websocket';
import type { DistributedEvent } from '../types';

export function useWebSocket(onEventCreated?: (event: DistributedEvent) => void) {
  useEffect(() => {
    wsClient.connect();
    
    const unsubscribe = wsClient.subscribe((payload) => {
      if (payload.type === 'EVENT_CREATED' && onEventCreated) {
        onEventCreated(payload.data);
      }
    });

    return () => {
      unsubscribe();
    };
  }, [onEventCreated]);

  return {};
}
