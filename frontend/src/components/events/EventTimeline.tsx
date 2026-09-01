import React, { useState } from 'react';
import type { DistributedEvent } from '../../types';
import { EventRow } from './EventRow';
import { EventDetails } from './EventDetails';
import { Search, Filter } from 'lucide-react';

interface EventTimelineProps {
  events: DistributedEvent[];
  onSelectEventForComparison?: (event: DistributedEvent) => void;
}

export const EventTimeline: React.FC<EventTimelineProps> = ({ events, onSelectEventForComparison }) => {
  const [filterProcess, setFilterProcess] = useState<number | 'ALL'>('ALL');
  const [filterType, setFilterType] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedEvent, setSelectedEvent] = useState<DistributedEvent | null>(null);

  const filteredEvents = events.filter((e) => {
    if (filterProcess !== 'ALL' && e.process_id !== filterProcess) return false;
    if (filterType !== 'ALL' && e.event_type !== filterType) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      return (
        e.event_id.toLowerCase().includes(q) ||
        e.description.toLowerCase().includes(q) ||
        (e.order_id && e.order_id.toString().includes(q))
      );
    }
    return true;
  });

  return (
    <div className="timeline-container">
      <div className="timeline-controls">
        <div className="search-bar">
          <Search size={16} className="text-gray-400" />
          <input
            type="text"
            placeholder="Search events, descriptions, orders..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>

        <div className="filter-group">
          <Filter size={16} className="text-gray-400" />
          <select
            value={filterProcess}
            onChange={(e) => setFilterProcess(e.target.value === 'ALL' ? 'ALL' : Number(e.target.value))}
          >
            <option value="ALL">All Processes</option>
            <option value="1">P1 — Order Processor</option>
            <option value="2">P2 — Restaurant A</option>
            <option value="3">P3 — Delivery Partner</option>
            <option value="4">P4 — Restaurant B</option>
          </select>

          <select value={filterType} onChange={(e) => setFilterType(e.target.value)}>
            <option value="ALL">All Event Types</option>
            <option value="INTERNAL">INTERNAL</option>
            <option value="SEND">SEND</option>
            <option value="RECEIVE">RECEIVE</option>
            <option value="MARKER">MARKER</option>
            <option value="SNAPSHOT_START">SNAPSHOT_START</option>
          </select>
        </div>
      </div>

      <div className="table-responsive">
        <table className="timeline-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Process</th>
              <th>Type</th>
              <th>Description</th>
              <th>Vector Clock [P1, P2, P3, P4]</th>
              <th>Order</th>
              <th>Wall Clock</th>
            </tr>
          </thead>
          <tbody>
            {filteredEvents.length === 0 ? (
              <tr>
                <td colSpan={7} className="text-center py-8 text-gray-500">
                  No events recorded yet. Run a scenario or place an order.
                </td>
              </tr>
            ) : (
              filteredEvents.map((ev) => (
                <EventRow
                  key={ev.event_id}
                  event={ev}
                  onSelect={(e) => {
                    setSelectedEvent(e);
                    if (onSelectEventForComparison) onSelectEventForComparison(e);
                  }}
                />
              ))
            )}
          </tbody>
        </table>
      </div>

      {selectedEvent && (
        <EventDetails event={selectedEvent} onClose={() => setSelectedEvent(null)} />
      )}
    </div>
  );
};
