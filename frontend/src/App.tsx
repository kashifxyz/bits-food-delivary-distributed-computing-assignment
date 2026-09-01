import React, { useState, useCallback } from 'react';
import { DashboardLayout } from './components/layout/DashboardLayout';
import { Dashboard } from './pages/Dashboard';
import { NetworkPage } from './pages/Network';
import { EventsPage } from './pages/Events';
import { VectorClocksPage } from './pages/VectorClocks';
import { SnapshotPage } from './pages/Snapshot';
import { OrdersPage } from './pages/Orders';
import { useProcesses } from './hooks/useProcesses';
import { useEvents } from './hooks/useEvents';
import { useWebSocket } from './hooks/useWebSocket';

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<string>('dashboard');

  const { processes, refresh: refreshProcesses } = useProcesses();
  const { events, refresh: refreshEvents, addEvent } = useEvents();

  // Real-time WebSocket streaming
  useWebSocket(
    useCallback((newEvent) => {
      addEvent(newEvent);
      refreshProcesses();
    }, [addEvent, refreshProcesses])
  );

  const handleGlobalRefresh = () => {
    refreshProcesses();
    refreshEvents();
  };

  return (
    <DashboardLayout
      currentTab={currentTab}
      onTabChange={setCurrentTab}
      onRefresh={handleGlobalRefresh}
    >
      {currentTab === 'dashboard' && (
        <Dashboard
          processes={processes}
          events={events}
          onRefresh={handleGlobalRefresh}
        />
      )}
      {currentTab === 'network' && <NetworkPage processes={processes} />}
      {currentTab === 'events' && <EventsPage events={events} />}
      {currentTab === 'vector-clocks' && (
        <VectorClocksPage processes={processes} events={events} />
      )}
      {currentTab === 'snapshots' && <SnapshotPage />}
      {currentTab === 'orders' && <OrdersPage />}
    </DashboardLayout>
  );
};

export default App;
