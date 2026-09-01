import React from 'react';
import type { ProcessState } from '../../types';
import { ProcessCard } from './ProcessCard';

interface ProcessGridProps {
  processes: ProcessState[];
}

export const ProcessGrid: React.FC<ProcessGridProps> = ({ processes }) => {
  return (
    <div className="process-grid">
      {processes.map((proc) => (
        <ProcessCard key={proc.process_id} process={proc} />
      ))}
    </div>
  );
};
