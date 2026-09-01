import React from 'react';
import type { DistributedEvent } from '../../types';
import { formatVectorClock, getProcessBadgeColor, getEventTypeBadge } from '../../utils/formatters';

interface EventDetailsProps {
  event: DistributedEvent | null;
  onClose: () => void;
}

export const EventDetails: React.FC<EventDetailsProps> = ({ event, onClose }) => {
  if (!event) return null;

  const pColor = getProcessBadgeColor(event.process_id);
  const typeBadge = getEventTypeBadge(event.event_type);

  return (
    <div className="event-modal-backdrop" onClick={onClose}>
      <div className="event-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Event Details: {event.event_id}</h3>
          <button className="btn-close" onClick={onClose}>×</button>
        </div>

        <div className="modal-body">
          <div className="detail-item">
            <span className="detail-label">Process:</span>
            <span
              className="process-tag"
              style={{ backgroundColor: pColor.bg, color: pColor.text }}
            >
              P{event.process_id}
            </span>
          </div>

          <div className="detail-item">
            <span className="detail-label">Event Type:</span>
            <span
              className="type-tag"
              style={{ backgroundColor: typeBadge.bg, color: typeBadge.text }}
            >
              {event.event_type}
            </span>
          </div>

          <div className="detail-item">
            <span className="detail-label">Description:</span>
            <span className="text-gray-200">{event.description}</span>
          </div>

          <div className="detail-item">
            <span className="detail-label">Vector Clock:</span>
            <span className="font-mono text-emerald-400 font-bold">
              {formatVectorClock(event.vector_clock)}
            </span>
          </div>

          <div className="detail-item">
            <span className="detail-label">Sequence Number:</span>
            <span className="font-mono text-gray-300">#{event.sequence_number}</span>
          </div>

          {event.order_id && (
            <div className="detail-item">
              <span className="detail-label">Associated Order:</span>
              <span className="font-mono text-blue-400">Order #{event.order_id}</span>
            </div>
          )}

          {event.message_id && (
            <div className="detail-item">
              <span className="detail-label">Message ID:</span>
              <span className="font-mono text-gray-300">{event.message_id}</span>
            </div>
          )}

          {event.metadata && Object.keys(event.metadata).length > 0 && (
            <div className="metadata-box">
              <span className="detail-label">Payload / Metadata:</span>
              <pre className="json-box">{JSON.stringify(event.metadata, null, 2)}</pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
