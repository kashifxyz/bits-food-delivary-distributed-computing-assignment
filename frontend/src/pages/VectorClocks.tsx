import React from 'react';
import type { ProcessState, DistributedEvent } from '../types';
import { ClockComparison } from '../components/vectorClock/ClockComparison';
import { formatVectorClock, getProcessBadgeColor } from '../utils/formatters';

interface Props {
  processes: ProcessState[];
  events: DistributedEvent[];
}

export const VectorClocksPage: React.FC<Props> = ({ processes, events }) => {
  return (
    <div className="space-y-6">
      <div className="card-box">
        <h3 className="card-title mb-4">Current Node Vector Clocks</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {processes.map((p) => {
            const pColor = getProcessBadgeColor(p.process_id);
            return (
              <div key={p.process_id} className="vc-card" style={{ borderColor: pColor.border }}>
                <div className="flex justify-between items-center mb-2">
                  <span className="font-bold text-gray-200">P{p.process_id} ({p.name})</span>
                  <span className="text-xs text-gray-400">{p.role}</span>
                </div>
                <div className="font-mono text-lg font-bold text-emerald-400">
                  {formatVectorClock(p.vector_clock)}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <ClockComparison events={events} />
    </div>
  );
};
