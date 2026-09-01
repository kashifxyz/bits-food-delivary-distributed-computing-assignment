import { useState, useEffect, useCallback } from 'react';
import type { DistributedEvent } from '../types';
import { fetchEvents } from '../services/api';

export function useEvents(processId?: number, orderId?: number) {
  const [events, setEvents] = useState<DistributedEvent[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await fetchEvents(processId, orderId);
      setEvents(data);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Error fetching events');
    } finally {
      setLoading(false);
    }
  }, [processId, orderId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const addEvent = useCallback((newEvent: DistributedEvent) => {
    setEvents((prev) => [newEvent, ...prev.filter((e) => e.event_id !== newEvent.event_id)]);
  }, []);

  return { events, loading, error, refresh, addEvent };
}
