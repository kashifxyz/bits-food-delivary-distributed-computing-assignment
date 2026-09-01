import React from 'react';
import type { ProcessState } from '../../types';
import { getProcessBadgeColor, formatVectorClock } from '../../utils/formatters';

interface ProcessNodeProps {
  process: ProcessState;
  x: number;
  y: number;
}

export const ProcessNode: React.FC<ProcessNodeProps> = ({ process, x, y }) => {
  const colors = getProcessBadgeColor(process.process_id);

  return (
    <g transform={`translate(${x}, ${y})`} className="network-node">
      <circle r="48" fill="#111827" stroke={colors.border} strokeWidth="3" />
      <circle r="42" fill={colors.bg} />
      
      <text
        textAnchor="middle"
        y="-8"
        fill={colors.text}
        fontSize="16"
        fontWeight="bold"
        className="select-none font-mono"
      >
        P{process.process_id}
      </text>

      <text
        textAnchor="middle"
        y="12"
        fill="#9ca3af"
        fontSize="10"
        className="select-none"
      >
        {process.name}
      </text>

      <rect
        x="-55"
        y="54"
        width="110"
        height="22"
        rx="4"
        fill="#1f2937"
        stroke="#374151"
      />
      <text
        textAnchor="middle"
        y="69"
        fill="#34d399"
        fontSize="11"
        fontWeight="600"
        fontFamily="monospace"
        className="select-none"
      >
        {formatVectorClock(process.vector_clock)}
      </text>
    </g>
  );
};
