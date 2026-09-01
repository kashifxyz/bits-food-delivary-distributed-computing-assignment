import React from 'react';
import type { ConsistencyResult as ConsistencyType } from '../../types';
import { CheckCircle2, XCircle } from 'lucide-react';

interface Props {
  result: ConsistencyType;
}

export const ConsistencyResult: React.FC<Props> = ({ result }) => {
  return (
    <div className={`consistency-card ${result.consistent ? 'consistent' : 'inconsistent'}`}>
      <div className="consistency-header">
        {result.consistent ? (
          <CheckCircle2 size={24} className="text-emerald-400" />
        ) : (
          <XCircle size={24} className="text-rose-500" />
        )}
        <div>
          <h4 className="consistency-title">
            Global Snapshot Consistency: {result.consistent ? 'CONSISTENT' : 'INCONSISTENT'}
          </h4>
          <p className="consistency-subtitle">{result.explanation}</p>
        </div>
      </div>

      {result.issues.length > 0 && (
        <div className="issues-box">
          <div className="font-semibold text-xs text-rose-400 mb-1">Detected Inconsistencies:</div>
          <ul className="list-disc list-inside text-xs text-rose-300">
            {result.issues.map((issue, idx) => (
              <li key={idx}>{issue}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};
