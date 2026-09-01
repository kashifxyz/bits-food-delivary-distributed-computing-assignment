import React from 'react';
import type { ProcessState } from '../types';
import { NetworkGraph } from '../components/network/NetworkGraph';

interface Props {
  processes: ProcessState[];
}

export const NetworkPage: React.FC<Props> = ({ processes }) => {
  return (
    <div className="space-y-6">
      <NetworkGraph processes={processes} />
    </div>
  );
};
