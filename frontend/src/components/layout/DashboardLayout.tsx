import React from 'react';
import type { ReactNode } from 'react';
import { Navbar } from './Navbar';
import { Sidebar } from './Sidebar';

interface DashboardLayoutProps {
  currentTab: string;
  onTabChange: (tab: string) => void;
  onRefresh?: () => void;
  children: ReactNode;
}

export const DashboardLayout: React.FC<DashboardLayoutProps> = ({
  currentTab,
  onTabChange,
  onRefresh,
  children
}) => {
  return (
    <div className="app-container">
      <Navbar onRefresh={onRefresh} />
      <div className="main-wrapper">
        <Sidebar currentTab={currentTab} onTabChange={onTabChange} />
        <main className="content-area">{children}</main>
      </div>
    </div>
  );
};
