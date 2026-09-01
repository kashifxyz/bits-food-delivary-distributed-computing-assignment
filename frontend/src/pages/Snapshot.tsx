import React, { useState, useEffect, useCallback } from 'react';
import type { GlobalSnapshot } from '../types';
import { fetchSnapshots } from '../services/api';
import { SnapshotPanel } from '../components/snapshot/SnapshotPanel';

export const SnapshotPage: React.FC = () => {
  const [snapshots, setSnapshots] = useState<GlobalSnapshot[]>([]);

  const loadSnapshots = useCallback(async () => {
    try {
      const data = await fetchSnapshots();
      setSnapshots(data);
    } catch (e) {
      console.error(e);
    }
  }, []);

  useEffect(() => {
    loadSnapshots();
  }, [loadSnapshots]);

  return (
    <div className="space-y-6">
      <h2 className="section-title">Chandy-Lamport Distributed Global Snapshot</h2>
      <SnapshotPanel snapshots={snapshots} onSnapshotTaken={loadSnapshots} />
    </div>
  );
};
