import React from 'react';
import { LayoutDashboard, Radio, Clock, Camera, ShoppingBag, GitGraph } from 'lucide-react';

interface SidebarProps {
  currentTab: string;
  onTabChange: (tab: string) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ currentTab, onTabChange }) => {
  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'network', label: 'Network Topology', icon: GitGraph },
    { id: 'events', label: 'Event Timeline', icon: Radio },
    { id: 'vector-clocks', label: 'Vector Clocks', icon: Clock },
    { id: 'snapshots', label: 'Global Snapshots', icon: Camera },
    { id: 'orders', label: 'Order Lifecycle', icon: ShoppingBag },
  ];

  return (
    <aside className="sidebar">
      <div className="sidebar-section-title">MONITORING VIEWS</div>
      <nav className="sidebar-nav">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentTab === item.id;
          return (
            <button
              key={item.id}
              className={`sidebar-link ${isActive ? 'active' : ''}`}
              onClick={() => onTabChange(item.id)}
            >
              <Icon size={18} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

      <div className="sidebar-footer">
        <div className="footer-card">
          <div className="text-xs font-semibold text-gray-400">DISTRIBUTED SPECS</div>
          <div className="text-xs text-gray-300 mt-1">Algorithm: Chandy-Lamport</div>
          <div className="text-xs text-gray-300">Causality: Vector Clocks (N=4)</div>
        </div>
      </div>
    </aside>
  );
};
