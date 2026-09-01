import React, { useState, useEffect, useCallback } from 'react';
import type { Order } from '../types';
import { fetchOrders } from '../services/api';
import { OrderPanel } from '../components/orders/OrderPanel';

export const OrdersPage: React.FC = () => {
  const [orders, setOrders] = useState<Order[]>([]);

  const loadOrders = useCallback(async () => {
    try {
      const data = await fetchOrders();
      setOrders(data);
    } catch (e) {
      console.error(e);
    }
  }, []);

  useEffect(() => {
    loadOrders();
    const interval = setInterval(loadOrders, 3000);
    return () => clearInterval(interval);
  }, [loadOrders]);

  return (
    <div className="space-y-6">
      <h2 className="section-title">Order Lifecycle Management</h2>
      <OrderPanel orders={orders} onOrderCreated={loadOrders} />
    </div>
  );
};
