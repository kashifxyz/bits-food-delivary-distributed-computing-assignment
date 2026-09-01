import React from 'react';
import type { ChannelSnapshot as ChannelSnapshotType } from '../../types';

interface Props {
  channels: Record<string, ChannelSnapshotType>;
}

export const ChannelSnapshotViewer: React.FC<Props> = ({ channels }) => {
  const channelList = Object.values(channels);

  return (
    <div className="channel-snapshot-grid">
      {channelList.map((ch) => (
        <div key={ch.channel_key} className="channel-card">
          <div className="channel-header">
            <span className="font-mono text-xs text-blue-400 font-bold">{ch.channel_key}</span>
            <span className={`text-xs px-2 py-0.5 rounded ${ch.messages.length > 0 ? 'bg-amber-900 text-amber-300' : 'bg-gray-800 text-gray-400'}`}>
              {ch.messages.length} In-Transit Msg
            </span>
          </div>

          {ch.messages.length === 0 ? (
            <div className="text-xs text-gray-500 italic mt-2">Channel state empty (no messages in flight)</div>
          ) : (
            <div className="mt-2 space-y-1">
              {ch.messages.map((m) => (
                <div key={m.id} className="in-transit-msg-item">
                  <div className="font-mono text-xs text-amber-400 font-bold">{m.id}</div>
                  <div className="text-xs text-gray-300">{m.message_type}</div>
                  <div className="text-xs text-gray-400">Order #{m.payload?.order_id || 'N/A'}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
};
