import React, { useState } from 'react';
import type { DistributedEvent, ComparisonResult } from '../../types';
import { compareEvents } from '../../services/api';
import { formatVectorClock } from '../../utils/formatters';
import { GitCompare } from 'lucide-react';

interface ClockComparisonProps {
  events: DistributedEvent[];
}

export const ClockComparison: React.FC<ClockComparisonProps> = ({ events }) => {
  const [eventAId, setEventAId] = useState<string>('');
  const [eventBId, setEventBId] = useState<string>('');
  const [result, setResult] = useState<ComparisonResult | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const handleCompare = async () => {
    if (!eventAId || !eventBId) {
      setError('Please select two distinct events.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await compareEvents(eventAId, eventBId);
      setResult(res);
    } catch (err: any) {
      setError(err.message || 'Comparison failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="comparison-card">
      <div className="card-header">
        <GitCompare size={20} className="text-blue-400" />
        <h3 className="card-title">Causal Relationship & Vector Clock Comparator</h3>
      </div>

      <div className="comparison-selectors">
        <div className="selector-box">
          <label>Event A:</label>
          <select value={eventAId} onChange={(e) => setEventAId(e.target.value)}>
            <option value="">-- Select Event A --</option>
            {events.map((ev) => (
              <option key={ev.event_id} value={ev.event_id}>
                {ev.event_id} (P{ev.process_id}: {ev.description}) {formatVectorClock(ev.vector_clock)}
              </option>
            ))}
          </select>
        </div>

        <div className="selector-box">
          <label>Event B:</label>
          <select value={eventBId} onChange={(e) => setEventBId(e.target.value)}>
            <option value="">-- Select Event B --</option>
            {events.map((ev) => (
              <option key={ev.event_id} value={ev.event_id}>
                {ev.event_id} (P{ev.process_id}: {ev.description}) {formatVectorClock(ev.vector_clock)}
              </option>
            ))}
          </select>
        </div>

        <button className="btn btn-primary" onClick={handleCompare} disabled={loading || !eventAId || !eventBId}>
          {loading ? 'Evaluating...' : 'Evaluate Causal Relation'}
        </button>
      </div>

      {error && <div className="alert-error">{error}</div>}

      {result && (
        <div className="comparison-result-box">
          <div className="result-header">
            <span className="result-label">Relationship:</span>
            <span className={`relation-badge relation-${result.relation.toLowerCase()}`}>
              {result.relation}
            </span>
          </div>

          <div className="result-explanation">
            <p>{result.explanation}</p>
          </div>

          <div className="result-clocks-grid">
            <div className="clock-col">
              <span className="font-semibold text-blue-400">Event A ({result.event_a.event_id})</span>
              <div className="font-mono text-sm text-gray-200 mt-1">
                Vector Clock: {formatVectorClock(result.event_a.vector_clock)}
              </div>
              <div className="text-xs text-gray-400">P{result.event_a.process_id}: {result.event_a.description}</div>
            </div>

            <div className="clock-col">
              <span className="font-semibold text-purple-400">Event B ({result.event_b.event_id})</span>
              <div className="font-mono text-sm text-gray-200 mt-1">
                Vector Clock: {formatVectorClock(result.event_b.vector_clock)}
              </div>
              <div className="text-xs text-gray-400">P{result.event_b.process_id}: {result.event_b.description}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
