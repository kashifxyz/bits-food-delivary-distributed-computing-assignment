import { useState, useEffect, useCallback } from 'react';
import type { ProcessState } from '../types';
import { fetchProcesses } from '../services/api';

export function useProcesses() {
  const [processes, setProcesses] = useState<ProcessState[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await fetchProcesses();
      setProcesses(data);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Error fetching processes');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 2500);
    return () => clearInterval(interval);
  }, [refresh]);

  return { processes, loading, error, refresh };
}
