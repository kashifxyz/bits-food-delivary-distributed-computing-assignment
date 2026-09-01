import React, { useState } from 'react';
import type { Order } from '../../types';
import { createOrder } from '../../services/api';
import { OrderStatusBadge } from './OrderStatus';
import { PlusCircle, ShoppingBag } from 'lucide-react';

interface OrderPanelProps {
  orders: Order[];
  onOrderCreated?: () => void;
}

const LIFECYCLE_STEPS = ['CREATED', 'ACCEPTED', 'PREPARING', 'READY', 'PICKED_UP', 'DELIVERED'];

export const OrderPanel: React.FC<OrderPanelProps> = ({ orders, onOrderCreated }) => {
  const [customer, setCustomer] = useState('Customer-1');
  const [restaurantId, setRestaurantId] = useState(2);
  const [items, setItems] = useState('Paneer Butter Masala, Garlic Naan');
  const [creating, setCreating] = useState(false);

  const handleCreateOrder = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    try {
      const itemList = items.split(',').map((s) => s.trim()).filter(Boolean);
      await createOrder(customer, restaurantId, itemList);
      if (onOrderCreated) onOrderCreated();
    } catch (err) {
      alert('Order creation failed');
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="orders-panel space-y-6">
      <div className="card-box">
        <h3 className="card-title flex items-center gap-2">
          <PlusCircle size={18} className="text-blue-400" />
          <span>Dispatch New Food Delivery Order</span>
        </h3>

        <form onSubmit={handleCreateOrder} className="order-form mt-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="text-xs text-gray-400">Customer Name / ID</label>
              <input
                type="text"
                className="input-field"
                value={customer}
                onChange={(e) => setCustomer(e.target.value)}
                required
              />
            </div>

            <div>
              <label className="text-xs text-gray-400">Target Restaurant Process</label>
              <select
                className="input-field"
                value={restaurantId}
                onChange={(e) => setRestaurantId(Number(e.target.value))}
              >
                <option value="2">P2 — Restaurant A (Primary)</option>
                <option value="4">P4 — Restaurant B (Independent)</option>
              </select>
            </div>

            <div>
              <label className="text-xs text-gray-400">Food Items (comma-separated)</label>
              <input
                type="text"
                className="input-field"
                value={items}
                onChange={(e) => setItems(e.target.value)}
                required
              />
            </div>
          </div>

          <button type="submit" className="btn btn-primary mt-4" disabled={creating}>
            <ShoppingBag size={16} />
            <span>{creating ? 'Creating Order...' : 'Submit Order to P1'}</span>
          </button>
        </form>
      </div>

      <div className="card-box">
        <h3 className="card-title">Active & Completed Orders</h3>

        {orders.length === 0 ? (
          <div className="empty-state py-8">
            <p className="text-gray-400">No active orders yet.</p>
          </div>
        ) : (
          <div className="space-y-4 mt-4">
            {orders.map((ord) => {
              const currentStepIdx = LIFECYCLE_STEPS.indexOf(ord.status);

              return (
                <div key={ord.order_id} className="order-card-item">
                  <div className="flex justify-between items-start">
                    <div>
                      <h4 className="font-bold text-gray-100">
                        Order #{ord.order_id} — {ord.customer}
                      </h4>
                      <p className="text-xs text-gray-400 mt-0.5">
                        Restaurant: P{ord.restaurant_id} • Delivery Partner: P{ord.delivery_partner_id} • Items: {ord.items.join(', ')}
                      </p>
                    </div>
                    <OrderStatusBadge status={ord.status} />
                  </div>

                  <div className="stepper-wrapper mt-4">
                    {LIFECYCLE_STEPS.map((step, idx) => {
                      const isDone = idx <= currentStepIdx;
                      const isCurrent = idx === currentStepIdx;

                      return (
                        <div key={step} className="stepper-step">
                          <div className={`step-dot ${isDone ? 'step-done' : ''} ${isCurrent ? 'step-current' : ''}`}>
                            {idx + 1}
                          </div>
                          <span className={`step-label ${isDone ? 'text-gray-200' : 'text-gray-500'}`}>
                            {step}
                          </span>
                          {idx < LIFECYCLE_STEPS.length - 1 && (
                            <div className={`step-line ${idx < currentStepIdx ? 'line-done' : ''}`} />
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
