import React, { useState } from 'react';
import type { ProcessState, DistributedEvent } from '../types';
import { ProcessGrid } from '../components/processes/ProcessGrid';
import { EventTimeline } from '../components/events/EventTimeline';
import { runScenario } from '../services/api';
import { Play, Activity, CheckCircle, Clock, Zap } from 'lucide-react';

interface DashboardProps {
  processes: ProcessState[];
  events: DistributedEvent[];
  onRefresh: () => void;
}

export const Dashboard: React.FC<DashboardProps> = ({ processes, events, onRefresh }) => {
  const [runningScenario, setRunningScenario] = useState<string | null>(null);
  const [scenarioResult, setScenarioResult] = useState<any | null>(null);

  const handleRun = async (scenarioId: string) => {
    setRunningScenario(scenarioId);
    setScenarioResult(null);
    try {
      const res = await runScenario(scenarioId);
      setScenarioResult(res);
      onRefresh();
    } catch (e: any) {
      alert(e.message || 'Scenario failed');
    } finally {
      setRunningScenario(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="scenario-action-box">
        <div className="flex justify-between items-center mb-3">
          <div className="flex items-center gap-2">
            <Zap size={20} className="text-amber-400" />
            <h3 className="font-bold text-gray-200">Deterministic Scenario Controls (Academic Demonstration)</h3>
          </div>
          <span className="text-xs text-gray-400">Click any scenario to execute deterministic distributed sequence</span>
        </div>

        <div className="scenario-button-grid">
          <button
            className="btn btn-scenario"
            onClick={() => handleRun('tc01_basic_order')}
            disabled={!!runningScenario}
          >
            <Play size={14} />
            <span>TC01: Basic Order (P1→P2→P3→P1)</span>
          </button>

          <button
            className="btn btn-scenario"
            onClick={() => handleRun('tc02_vector_clock')}
            disabled={!!runningScenario}
          >
            <Clock size={14} />
            <span>TC02: Vector Clock Progression</span>
          </button>

          <button
            className="btn btn-scenario"
            onClick={() => handleRun('tc03_concurrent_events')}
            disabled={!!runningScenario}
          >
            <Activity size={14} />
            <span>TC03: Concurrent Events (P2 || P4)</span>
          </button>

          <button
            className="btn btn-scenario"
            onClick={() => handleRun('tc04_in_transit_snapshot')}
            disabled={!!runningScenario}
          >
            <Play size={14} />
            <span>TC04: In-Transit Msg Snapshot</span>
          </button>

          <button
            className="btn btn-scenario"
            onClick={() => handleRun('tc05_global_snapshot')}
            disabled={!!runningScenario}
          >
            <CheckCircle size={14} />
            <span>TC05: Global Chandy-Lamport Cut</span>
          </button>
        </div>

        {scenarioResult && (
          <div className="scenario-result-banner mt-3">
            <span className="font-bold text-emerald-400">Result ({scenarioResult.scenario}):</span>
            <span className="text-gray-300 ml-2">Status: {scenarioResult.status}</span>
            {scenarioResult.relation && (
              <span className="ml-3 px-2 py-0.5 rounded bg-purple-900 text-purple-300 font-bold">
                Causal Relation: {scenarioResult.relation}
              </span>
            )}
            {scenarioResult.explanation && (
              <p className="text-xs text-gray-400 mt-1">{scenarioResult.explanation}</p>
            )}
          </div>
        )}
      </div>

      <div>
        <h2 className="section-title">Independent Logical Process Nodes (N=4)</h2>
        <ProcessGrid processes={processes} />
      </div>

      <div>
        <h2 className="section-title">Global Causal Event Timeline</h2>
        <EventTimeline events={events} />
      </div>
    </div>
  );
};
