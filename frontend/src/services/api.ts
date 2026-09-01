import type { ProcessState, DistributedEvent, Order, GlobalSnapshot, ComparisonResult } from '../types';

const API_BASE = 'http://localhost:8000/api';

export async function fetchProcesses(): Promise<ProcessState[]> {
  const res = await fetch(`${API_BASE}/processes`);
  if (!res.ok) throw new Error('Failed to fetch processes');
  return res.json();
}

export async function fetchEvents(processId?: number, orderId?: number): Promise<DistributedEvent[]> {
  let url = `${API_BASE}/events`;
  const params = new URLSearchParams();
  if (processId) params.append('process_id', processId.toString());
  if (orderId) params.append('order_id', orderId.toString());
  if (params.toString()) url += `?${params.toString()}`;
  
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to fetch events');
  return res.json();
}

export async function compareEvents(eventA: string, eventB: string): Promise<ComparisonResult> {
  const res = await fetch(`${API_BASE}/events/compare?event_a=${encodeURIComponent(eventA)}&event_b=${encodeURIComponent(eventB)}`);
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Failed to compare events');
  }
  return res.json();
}

export async function fetchOrders(): Promise<Order[]> {
  const res = await fetch(`${API_BASE}/orders`);
  if (!res.ok) throw new Error('Failed to fetch orders');
  return res.json();
}

export async function createOrder(customer: string, restaurantId: number = 2, items: string[] = ['Paneer Butter Masala', 'Naan']): Promise<Order> {
  const res = await fetch(`${API_BASE}/orders`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ customer, restaurant_id: restaurantId, items })
  });
  if (!res.ok) throw new Error('Failed to create order');
  return res.json();
}

export async function fetchSnapshots(): Promise<GlobalSnapshot[]> {
  const res = await fetch(`${API_BASE}/snapshots`);
  if (!res.ok) throw new Error('Failed to fetch snapshots');
  return res.json();
}

export async function initiateSnapshot(initiatorId: number = 1): Promise<GlobalSnapshot> {
  const res = await fetch(`${API_BASE}/snapshots`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ initiator_id: initiatorId })
  });
  if (!res.ok) throw new Error('Failed to initiate snapshot');
  return res.json();
}

export async function fetchScenarios(): Promise<any[]> {
  const res = await fetch(`${API_BASE}/scenarios`);
  if (!res.ok) throw new Error('Failed to fetch scenarios');
  return res.json();
}

export async function runScenario(scenarioId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/scenarios/${scenarioId}/run`, {
    method: 'POST'
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Scenario execution failed');
  }
  return res.json();
}

export async function resetSystem(): Promise<void> {
  const res = await fetch(`${API_BASE}/processes/reset`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to reset system');
}
