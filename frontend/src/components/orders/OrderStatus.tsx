import React from 'react';

interface Props {
  status: string;
}

export const OrderStatusBadge: React.FC<Props> = ({ status }) => {
  let color = 'bg-gray-800 text-gray-300 border-gray-700';
  if (status === 'CREATED') color = 'bg-blue-950 text-blue-300 border-blue-800';
  if (status === 'ACCEPTED') color = 'bg-indigo-950 text-indigo-300 border-indigo-800';
  if (status === 'PREPARING') color = 'bg-amber-950 text-amber-300 border-amber-800';
  if (status === 'READY') color = 'bg-yellow-950 text-yellow-300 border-yellow-800';
  if (status === 'PICKED_UP') color = 'bg-purple-950 text-purple-300 border-purple-800';
  if (status === 'DELIVERED') color = 'bg-emerald-950 text-emerald-300 border-emerald-800';

  return (
    <span className={`px-2.5 py-1 rounded text-xs font-semibold border ${color}`}>
      {status}
    </span>
  );
};
