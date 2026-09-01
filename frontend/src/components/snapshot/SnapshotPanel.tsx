import React, { useState } from 'react';
import type { GlobalSnapshot } from '../../types';
import { initiateSnapshot } from '../../services/api';
import { ProcessSnapshotCard } from './ProcessSnapshot';
import { ChannelSnapshotViewer } from './ChannelSnapshot';
import { ConsistencyResult } from './ConsistencyResult';
import { Camera } from 'lucide-react';

interface SnapshotPanelProps {
  snapshots: GlobalSnapshot[];
  onSnapshotTaken?: () => void;
}

export const SnapshotPanel: React.FC<SnapshotPanelProps> = ({ snapshots, onSnapshotTaken }) => {
  const [initiatorId, setInitiatorId] = useState<number>(1);
  const [takingSnapshot, setTakingSnapshot] = useState<boolean>(false);
  const [selectedSnapshotId, setSelectedSnapshotId] = useState<string>('');

  const currentSnapshot = selectedSnapshotId
    ? snapshots.find((s) => s.snapshot_id === selectedSnapshotId)
    : snapshots[snapshots.length - 1];

  const handleTakeSnapshot = async () => {
    setTakingSnapshot(true);
    try {
      const snap = await initiateSnapshot(initiatorId);
      setSelectedSnapshotId(snap.snapshot_id);
      if (onSnapshotTaken) onSnapshotTaken();
    } catch (e) {
      alert('Snapshot failed');
    } finally {
      setTakingSnapshot(false);
    }
  };

  return (
    <div className="snapshot-panel">
      <div className="snapshot-action-bar">
        <div className="flex items-center gap-3">
          <label className="text-sm text-gray-300">Initiate from Process:</label>
          <select
            value={initiatorId}
            onChange={(e) => setInitiatorId(Number(e.target.value))}
            className="select-input"
          >
            <option value="1">P1 — Order Processor</option>
            <option value="2">P2 — Restaurant A</option>
            <option value="3">P3 — Delivery Partner</option>
            <option value="4">P4 — Restaurant B</option>
          </select>

          <button
            className="btn btn-primary"
            onClick={handleTakeSnapshot}
            disabled={takingSnapshot}
          >
            <Camera size={16} />
            <span>{takingSnapshot ? 'Recording...' : 'Take Chandy-Lamport Snapshot'}</span>
          </button>
        </div>

        {snapshots.length > 0 && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-400">History:</span>
            <select
              value={currentSnapshot?.snapshot_id || ''}
              onChange={(e) => setSelectedSnapshotId(e.target.value)}
              className="select-input"
            >
              {snapshots.map((s) => (
                <option key={s.snapshot_id} value={s.snapshot_id}>
                  {s.snapshot_id} (P{s.initiated_by}) - {s.status}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {currentSnapshot ? (
        <div className="snapshot-details mt-6 space-y-6">
          <div className="snapshot-meta-banner">
            <div>
              <h3 className="text-lg font-bold text-gray-200">
                Global Snapshot: {currentSnapshot.snapshot_id}
              </h3>
              <p className="text-xs text-gray-400">
                Initiated by P{currentSnapshot.initiated_by} • Status: {currentSnapshot.status} • Recorded at: {currentSnapshot.started_at}
              </p>
            </div>
          </div>

          {currentSnapshot.consistency && (
            <ConsistencyResult result={currentSnapshot.consistency} />
          )}

          <div>
            <h4 className="section-subtitle">Recorded Process States (4 Logical Nodes)</h4>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mt-3">
              {Object.values(currentSnapshot.process_states).map((ps) => (
                <ProcessSnapshotCard key={ps.process_id} snapshot={ps} />
              ))}
            </div>
          </div>

          <div>
            <h4 className="section-subtitle">Recorded Channel States (Directed FIFO Channels & In-Transit Messages)</h4>
            <div className="mt-3">
              <ChannelSnapshotViewer channels={currentSnapshot.channel_states} />
            </div>
          </div>
        </div>
      ) : (
        <div className="empty-state">
          <Camera size={48} className="text-gray-600 mb-2" />
          <p className="text-gray-400">No snapshots recorded yet.</p>
          <p className="text-xs text-gray-500">Click &quot;Take Chandy-Lamport Snapshot&quot; above to capture a global consistent cut.</p>
        </div>
      )}
    </div>
  );
};
