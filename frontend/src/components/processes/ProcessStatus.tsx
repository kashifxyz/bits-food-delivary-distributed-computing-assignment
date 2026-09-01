import React from 'react';
import type { ProcessStatus as StatusType } from '../../types';

interface ProcessStatusProps {
  status: StatusType;
}

export const ProcessStatus: React.FC<ProcessStatusProps> = ({ status }) => {
  let statusClass = 'status-active';
  if (status === 'PAUSED') statusClass = 'status-paused';
  if (status === 'STOPPED') statusClass = 'status-stopped';

  return (
    <div className={`status-pill ${statusClass}`}>
      <span className="status-dot"></span>
      <span className="status-text">{status}</span>
    </div>
  );
};
