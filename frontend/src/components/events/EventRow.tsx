import React from 'react';
import type { DistributedEvent } from '../../types';
import { formatTimestamp, formatVectorClock, getProcessBadgeColor, getEventTypeBadge } from '../../utils/formatters';

interface EventRowProps {
  event: DistributedEvent;
  isSelected?: boolean;
  onSelect?: (event: DistributedEvent) => void;
}

export const EventRow: React.FC<EventRowProps> = ({ event, isSelected, onSelect }) => {
  const pColor = getProcessBadgeColor(event.process_id);
  const typeBadge = getEventTypeBadge(event.event_type);

  return (
    <tr
      className={`event-row ${isSelected ? 'selected' : ''}`}
      onClick={() => onSelect && onSelect(event)}
    >
      <td className="font-mono text-xs text-blue-400 font-bold">{event.event_id}</td>
      <td>
        <span
          className="process-tag"
          style={{ backgroundColor: pColor.bg, color: pColor.text, borderColor: pColor.border }}
        >
          P{event.process_id}
        </span>
      </td>
      <td>
        <span
          className="type-tag"
          style={{ backgroundColor: typeBadge.bg, color: typeBadge.text }}
        >
          {event.event_type}
        </span>
      </td>
      <td className="event-desc">{event.description}</td>
      <td className="font-mono text-xs text-emerald-400 font-bold">
        {formatVectorClock(event.vector_clock)}
      </td>
      <td className="font-mono text-xs text-gray-400">
        {event.order_id ? `#${event.order_id}` : '—'}
      </td>
      <td className="text-xs text-gray-400">{formatTimestamp(event.wall_clock_timestamp)}</td>
    </tr>
  );
};
