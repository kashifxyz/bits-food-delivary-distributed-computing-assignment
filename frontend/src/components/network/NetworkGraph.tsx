import React from 'react';
import type { ProcessState } from '../../types';
import { ProcessNode } from './ProcessNode';
import { MessageEdge } from './MessageAnimation';

interface NetworkGraphProps {
  processes: ProcessState[];
}

export const NetworkGraph: React.FC<NetworkGraphProps> = ({ processes }) => {
  const nodePositions: Record<number, { x: number; y: number }> = {
    1: { x: 350, y: 80 },
    2: { x: 560, y: 240 },
    3: { x: 350, y: 400 },
    4: { x: 140, y: 240 },
  };

  const getProc = (id: number) => processes.find((p) => p.process_id === id) || {
    process_id: id,
    name: `P${id}`,
    role: 'Process',
    status: 'ACTIVE',
    vector_clock: [0, 0, 0, 0],
    total_events: 0,
    current_orders: [],
    local_data: {}
  } as ProcessState;

  return (
    <div className="network-container">
      <div className="network-header">
        <h3 className="text-lg font-bold text-gray-200">Distributed Directed Communication Mesh</h3>
        <p className="text-xs text-gray-400">
          Reliable FIFO Directed Channels: P1 ↔ P2 ↔ P3 ↔ P4
        </p>
      </div>

      <div className="svg-canvas-wrapper">
        <svg viewBox="0 0 700 480" className="network-svg">
          <defs>
            <marker
              id="arrowhead"
              markerWidth="10"
              markerHeight="7"
              refX="38"
              refY="3.5"
              orient="auto"
            >
              <polygon points="0 0, 10 3.5, 0 7" fill="#4b5563" />
            </marker>
          </defs>

          <MessageEdge x1={nodePositions[1].x} y1={nodePositions[1].y} x2={nodePositions[2].x} y2={nodePositions[2].y} label="P1 → P2" />
          <MessageEdge x1={nodePositions[2].x} y1={nodePositions[2].y} x2={nodePositions[3].x} y2={nodePositions[3].y} label="P2 → P3" />
          <MessageEdge x1={nodePositions[3].x} y1={nodePositions[3].y} x2={nodePositions[1].x} y2={nodePositions[1].y} label="P3 → P1" />
          <MessageEdge x1={nodePositions[1].x} y1={nodePositions[1].y} x2={nodePositions[4].x} y2={nodePositions[4].y} label="P1 → P4" />
          <MessageEdge x1={nodePositions[4].x} y1={nodePositions[4].y} x2={nodePositions[2].x} y2={nodePositions[2].y} label="P4 → P2" />
          <MessageEdge x1={nodePositions[4].x} y1={nodePositions[4].y} x2={nodePositions[3].x} y2={nodePositions[3].y} label="P4 → P3" />

          {[1, 2, 3, 4].map((id) => (
            <ProcessNode
              key={id}
              process={getProc(id)}
              x={nodePositions[id].x}
              y={nodePositions[id].y}
            />
          ))}
        </svg>
      </div>
    </div>
  );
};
