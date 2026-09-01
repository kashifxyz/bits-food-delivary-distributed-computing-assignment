import React from 'react';
import type { DistributedEvent } from '../types';
import { EventTimeline } from '../components/events/EventTimeline';

interface Props {
  events: DistributedEvent[];
}

export const EventsPage: React.FC<Props> = ({ events }) => {
  return (
    <div className="space-y-6">
      <h2 className="section-title">Causal Event Ledger</h2>
      <EventTimeline events={events} />
    </div>
  );
};
