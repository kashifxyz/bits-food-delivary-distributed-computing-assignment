import React from 'react';
import type { ProcessSnapshot as ProcessSnapshotType } from '../../types';
import { formatVectorClock, getProcessBadgeColor } from '../../utils/formatters';

interface Props {
  snapshot: ProcessSnapshotType;
}

export const ProcessSnapshotCard: React.FC<Props> = ({ snapshot }) => {
  const pColor = getProcessBadgeColor(snapshot.process_id);

  return (
    <div className="snapshot-proc-card" style={{ borderColor: pColor.border }}>
      <div className="snapshot-proc-header">
        <span className="process-tag" style={{ backgroundColor: pColor.bg, color: pColor.text }}>
          P{snapshot.process_id}
        </span>
        <span className="font-bold text-sm text-gray-200">{snapshot.process_name}</span>
      </div>

      <div className="mt-2 space-y-1 text-xs">
        <div className="flex justify-between">
          <span className="text-gray-400">Role:</span>
          <span className="text-gray-200">{snapshot.role}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-400">Recorded Clock:</span>
          <span className="font-mono text-emerald-400 font-bold">
            {formatVectorClock(snapshot.vector_clock)}
          </span>
        </div>
      </div>

      <div className="mt-3 bg-gray-950 p-2 rounded text-xs font-mono text-gray-300 max-h-28 overflow-y-auto">
        <pre>{JSON.stringify(snapshot.local_state, null, 2)}</pre>
      </div>
    </div>
  );
};
