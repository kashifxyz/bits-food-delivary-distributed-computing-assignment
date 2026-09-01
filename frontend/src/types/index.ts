export type ProcessStatus = 'ACTIVE' | 'IDLE' | 'BUSY' | 'PAUSED' | 'STOPPED';

export interface ProcessState {
  process_id: number;
  name: string;
  role: string;
  status: ProcessStatus;
  vector_clock: number[];
  total_events: number;
  current_orders: Record<string, any>[];
  local_data: Record<string, any>;
}

export type EventType = 'INTERNAL' | 'SEND' | 'RECEIVE' | 'MARKER' | 'SNAPSHOT_START' | 'SNAPSHOT_COMPLETE';

export interface DistributedEvent {
  event_id: string;
  process_id: number;
  event_type: EventType;
  description: string;
  message_id?: string;
  order_id?: number;
  vector_clock: number[];
  sequence_number: number;
  wall_clock_timestamp: string;
  metadata?: Record<string, any>;
}

export type MessageType =
  | 'ORDER_CREATED'
  | 'ORDER_ACCEPTED'
  | 'ORDER_REJECTED'
  | 'FOOD_PREPARING'
  | 'FOOD_READY'
  | 'DELIVERY_REQUEST'
  | 'DELIVERY_ACCEPTED'
  | 'FOOD_PICKED_UP'
  | 'ORDER_DELIVERED'
  | 'STATUS_UPDATE'
  | 'MARKER';

export interface DistributedMessage {
  id: string;
  sender_id: number;
  receiver_id: number;
  message_type: MessageType;
  payload: Record<string, any>;
  vector_clock: number[];
  snapshot_id?: string;
  created_at: string;
}

export interface Order {
  order_id: number;
  customer: string;
  restaurant_id: number;
  delivery_partner_id: number;
  items: string[];
  status: 'CREATED' | 'ACCEPTED' | 'PREPARING' | 'READY' | 'PICKED_UP' | 'DELIVERED' | 'CANCELLED';
  created_at: string;
  updated_at: string;
}

export interface ProcessSnapshot {
  process_id: number;
  process_name: string;
  role: string;
  vector_clock: number[];
  recorded_at: string;
  local_state: Record<string, any>;
}

export interface ChannelSnapshot {
  sender_id: number;
  receiver_id: number;
  channel_key: string;
  messages: DistributedMessage[];
  is_recording: boolean;
  recording_completed: boolean;
}

export interface ConsistencyResult {
  consistent: boolean;
  issues: string[];
  explanation: string;
  analyzed_events_count: number;
  checked_at: string;
}

export interface GlobalSnapshot {
  snapshot_id: string;
  initiated_by: number;
  status: 'IN_PROGRESS' | 'COMPLETED' | 'FAILED';
  started_at: string;
  completed_at?: string;
  process_states: Record<string, ProcessSnapshot>;
  channel_states: Record<string, ChannelSnapshot>;
  consistency?: ConsistencyResult;
}

export type CausalRelation = 'BEFORE' | 'AFTER' | 'CONCURRENT' | 'SAME';

export interface ComparisonResult {
  event_a: DistributedEvent;
  event_b: DistributedEvent;
  relation: CausalRelation;
  explanation: string;
}
