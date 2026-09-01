import React from 'react';
import type { ProcessState } from '../../types';
import { ProcessStatus } from './ProcessStatus';
import { formatVectorClock, getProcessBadgeColor } from '../../utils/formatters';

interface ProcessCardProps {
  process: ProcessState;
}

export const ProcessCard: React.FC<ProcessCardProps> = ({ process }) => {
  const colors = getProcessBadgeColor(process.process_id);
  const activeOrdersCount = process.current_orders ? process.current_orders.length : 0;

  return (
    <div className="process-card" style={{ borderColor: colors.border }}>
      <div className="process-header">
        <div className="process-title-group">
          <div className="process-avatar" style={{ backgroundColor: colors.bg, color: colors.text }}>
            P{process.process_id}
          </div>
          <div>
            <h3 className="process-name">{process.name} — {process.role}</h3>
            <p className="process-id">Node ID: #{process.process_id}</p>
          </div>
        </div>
        <ProcessStatus status={process.status} />
      </div>

      <div className="process-body">
        <div className="metric-row">
          <span className="metric-label">Vector Clock:</span>
          <span className="vector-badge">{formatVectorClock(process.vector_clock)}</span>
        </div>

        <div className="metric-row">
          <span className="metric-label">Local Events:</span>
          <span className="metric-value font-mono">{process.total_events}</span>
        </div>

        <div className="metric-row">
          <span className="metric-label">Active Orders:</span>
          <span className="metric-value font-mono">{activeOrdersCount}</span>
        </div>

        {process.local_data && (
          <div className="process-extra">
            <div className="text-xs text-gray-400">Local State:</div>
            <div className="text-xs font-mono text-gray-300">
              {process.process_id === 3
                ? `Completed Deliveries: ${process.local_data.completed_deliveries || 0}`
                : `Availability: ${process.local_data.availability || 'ONLINE'}`}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
