import React from 'react';

interface EdgeProps {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  label?: string;
  inTransitCount?: number;
}

export const MessageEdge: React.FC<EdgeProps> = ({ x1, y1, x2, y2, label, inTransitCount = 0 }) => {
  const midX = (x1 + x2) / 2;
  const midY = (y1 + y2) / 2;

  return (
    <g className="network-edge">
      <line
        x1={x1}
        y1={y1}
        x2={x2}
        y2={y2}
        stroke={inTransitCount > 0 ? '#f59e0b' : '#374151'}
        strokeWidth={inTransitCount > 0 ? '2.5' : '1.5'}
        strokeDasharray={inTransitCount > 0 ? '6 4' : 'none'}
        markerEnd="url(#arrowhead)"
      />

      {inTransitCount > 0 && (
        <circle cx={midX} cy={midY} r="8" fill="#f59e0b" className="animate-ping" />
      )}

      {label && (
        <text
          x={midX}
          y={midY - 8}
          textAnchor="middle"
          fill={inTransitCount > 0 ? '#fbbf24' : '#6b7280'}
          fontSize="10"
          className="select-none font-mono"
        >
          {label} {inTransitCount > 0 ? `(${inTransitCount} msg)` : ''}
        </text>
      )}
    </g>
  );
};
