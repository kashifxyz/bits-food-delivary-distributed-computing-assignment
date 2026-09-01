import React from 'react';
import { Activity, RefreshCw, Layers, ShieldCheck } from 'lucide-react';
import { resetSystem } from '../../services/api';

interface NavbarProps {
  onRefresh?: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ onRefresh }) => {
  const [resetting, setResetting] = React.useState(false);

  const handleReset = async () => {
    if (confirm('Reset entire distributed system and event history?')) {
      setResetting(true);
      try {
        await resetSystem();
        if (onRefresh) onRefresh();
      } catch (e) {
        alert('Reset failed');
      } finally {
        setResetting(false);
      }
    }
  };

  return (
    <header className="navbar">
      <div className="navbar-brand">
        <div className="brand-icon">
          <Layers className="icon-pulse" size={24} />
        </div>
        <div>
          <h1 className="brand-title">Distributed System Monitor</h1>
          <p className="brand-subtitle">Online Food Delivery • Vector Clocks • Chandy-Lamport Snapshots</p>
        </div>
      </div>

      <div className="navbar-actions">
        <div className="system-badge">
          <ShieldCheck size={16} className="text-emerald-400" />
          <span>4 Active Nodes</span>
        </div>

        <button className="btn btn-secondary" onClick={onRefresh} title="Refresh System State">
          <RefreshCw size={16} />
          <span>Sync</span>
        </button>

        <button className="btn btn-danger" onClick={handleReset} disabled={resetting}>
          <Activity size={16} />
          <span>{resetting ? 'Resetting...' : 'Reset System'}</span>
        </button>
      </div>
    </header>
  );
};
