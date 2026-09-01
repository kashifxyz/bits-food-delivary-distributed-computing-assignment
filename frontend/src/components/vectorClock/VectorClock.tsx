import React from 'react';
import { getProcessBadgeColor } from '../../utils/formatters';

interface VectorClockProps {
  clock: number[];
  processNames?: string[];
}

export const VectorClock: React.FC<VectorClockProps> = ({
  clock,
  processNames = ['P1 (Processor)', 'P2 (Rest. A)', 'P3 (Delivery)', 'P4 (Rest. B)']
}) => {
  return (
    <div className="vc-visual-container">
      {clock.map((val, idx) => {
        const pColor = getProcessBadgeColor(idx + 1);
        return (
          <div key={idx} className="vc-node" style={{ borderColor: pColor.border }}>
            <div className="vc-node-header" style={{ color: pColor.text }}>
              P{idx + 1}
            </div>
            <div className="vc-node-value">{val}</div>
            <div className="vc-node-label">{processNames[idx] || `Node ${idx + 1}`}</div>
          </div>
        );
      })}
    </div>
  );
};
