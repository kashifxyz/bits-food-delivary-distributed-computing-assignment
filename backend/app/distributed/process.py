import asyncio
import logging
import uuid
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from backend.app.models.event import Event, EventType
from backend.app.models.message import Message, MessageType
from backend.app.models.order import Order, OrderStatus
from backend.app.models.process import ProcessStatus, ProcessState
from backend.app.models.snapshot import ProcessSnapshot
from backend.app.vector_clock.vector_clock import VectorClock
from backend.app.distributed.event_manager import EventManager, event_manager as global_event_manager

if TYPE_CHECKING:
    from backend.app.distributed.message_bus import MessageBus
    from backend.app.snapshot.snapshot_manager import SnapshotManager

logger = logging.getLogger("DistributedProcess")

class DistributedProcess:
    """
    Independent Logical Process in the Distributed Food Delivery System.
    Maintains local state, its own vector clock, local sequence numbers,
    and communicates exclusively via message passing across directed channels.
    """
    def __init__(
        self,
        process_id: int,
        name: str,
        role: str,
        description: str,
        num_processes: int = 4,
        message_bus: Optional['MessageBus'] = None,
        event_mgr: Optional[EventManager] = None
    ):
        self.process_id = process_id
        self.name = name
        self.role = role
        self.description = description
        self.num_processes = num_processes
        self.status = ProcessStatus.ACTIVE
        
        self.vector_clock = VectorClock(process_id=process_id, num_processes=num_processes)
        self.message_bus = message_bus
        self.event_manager = event_mgr or global_event_manager
        
        self.sequence_number = 0
        self.orders: Dict[int, Dict[str, Any]] = {}
        self.local_data: Dict[str, Any] = {
            "availability": "OPEN" if process_id in [2, 4] else "READY",
            "active_tasks": [],
            "completed_deliveries": 0 if process_id == 3 else 0
        }
        
        # Listener loop task for incoming channels
        self._listener_tasks: List[asyncio.Task] = []
        self._running = False
        self._snapshot_manager: Optional['SnapshotManager'] = None

    def set_message_bus(self, message_bus: 'MessageBus'):
        self.message_bus = message_bus

    def set_snapshot_manager(self, snapshot_mgr: 'SnapshotManager'):
        self._snapshot_manager = snapshot_mgr

    async def log_internal_event(self, description: str, order_id: Optional[int] = None, metadata: Dict[str, Any] = None) -> Event:
        """Records an internal event and advances logical clock."""
        self.sequence_number += 1
        new_clock = self.vector_clock.tick_internal()
        event = Event(
            process_id=self.process_id,
            event_type=EventType.INTERNAL,
            description=description,
            order_id=order_id,
            vector_clock=new_clock,
            sequence_number=self.sequence_number,
            metadata=metadata or {}
        )
        await self.event_manager.record_event(event)
        return event

    async def send_msg(
        self,
        receiver_id: int,
        message_type: MessageType,
        payload: Dict[str, Any],
        order_id: Optional[int] = None,
        snapshot_id: Optional[str] = None
    ) -> Message:
        """Advances clock and sends a message through the directed channel."""
        if not self.message_bus:
            raise RuntimeError(f"Process P{self.process_id} has no MessageBus configured")
            
        self.sequence_number += 1
        
        # Send event rule: advance sender's clock component
        clock_snapshot = self.vector_clock.tick_send()
        
        message = Message(
            sender_id=self.process_id,
            receiver_id=receiver_id,
            message_type=message_type,
            payload=payload,
            vector_clock=clock_snapshot,
            snapshot_id=snapshot_id
        )
        
        # Record SEND event
        event_type = EventType.MARKER if message_type == MessageType.MARKER else EventType.SEND
        desc = f"Sent {message_type.value} to P{receiver_id}" if message_type != MessageType.MARKER else f"Sent MARKER to P{receiver_id}"
        if order_id:
            desc += f" (Order #{order_id})"
            
        event = Event(
            process_id=self.process_id,
            event_type=event_type,
            description=desc,
            message_id=message.id,
            order_id=order_id,
            vector_clock=clock_snapshot,
            sequence_number=self.sequence_number,
            metadata={"receiver_id": receiver_id, "payload": payload}
        )
        await self.event_manager.record_event(event)
        
        # Dispatch to message bus
        await self.message_bus.send_message(message)
        return message

    async def receive_msg(self, message: Message) -> Event:
        """
        Receives and processes an incoming message.
        Updates vector clock: L[k] = max(L[k], R[k]), then L[receiver] += 1
        """
        self.sequence_number += 1
        
        if message.message_type == MessageType.MARKER:
            # Handle snapshot marker via snapshot manager if registered
            if self._snapshot_manager:
                await self._snapshot_manager.handle_marker_received(self.process_id, message.sender_id, message)
            
            # For marker, advance vector clock as internal/marker receive
            new_clock = self.vector_clock.tick_receive(message.vector_clock)
            event = Event(
                process_id=self.process_id,
                event_type=EventType.MARKER,
                description=f"Received MARKER from P{message.sender_id} for snapshot {message.snapshot_id}",
                message_id=message.id,
                vector_clock=new_clock,
                sequence_number=self.sequence_number,
                metadata={"sender_id": message.sender_id, "snapshot_id": message.snapshot_id}
            )
            await self.event_manager.record_event(event)
            return event
        
        # Normal message receive:
        new_clock = self.vector_clock.tick_receive(message.vector_clock)
        order_id = message.payload.get("order_id")
        
        desc = f"Received {message.message_type.value} from P{message.sender_id}"
        if order_id:
            desc += f" (Order #{order_id})"
            
        event = Event(
            process_id=self.process_id,
            event_type=EventType.RECEIVE,
            description=desc,
            message_id=message.id,
            order_id=order_id,
            vector_clock=new_clock,
            sequence_number=self.sequence_number,
            metadata={"sender_id": message.sender_id, "payload": message.payload}
        )
        await self.event_manager.record_event(event)
        
        # Update local domain state
        await self._apply_message_to_local_state(message)
        return event

    async def _apply_message_to_local_state(self, message: Message):
        payload = message.payload
        order_id = payload.get("order_id")
        m_type = message.message_type
        
        if order_id:
            if order_id not in self.orders:
                self.orders[order_id] = {
                    "order_id": order_id,
                    "customer": payload.get("customer", f"Customer-{order_id}"),
                    "status": "CREATED",
                    "items": payload.get("items", []),
                    "restaurant_id": payload.get("restaurant_id", 2),
                    "delivery_partner_id": payload.get("delivery_partner_id", 3)
                }
            
            # State transitions based on role and message type
            if m_type == MessageType.ORDER_CREATED:
                self.orders[order_id]["status"] = "CREATED"
            elif m_type == MessageType.ORDER_ACCEPTED:
                self.orders[order_id]["status"] = "ACCEPTED"
            elif m_type == MessageType.FOOD_PREPARING:
                self.orders[order_id]["status"] = "PREPARING"
            elif m_type == MessageType.FOOD_READY:
                self.orders[order_id]["status"] = "READY"
            elif m_type == MessageType.DELIVERY_REQUEST:
                self.orders[order_id]["status"] = "DISPATCHING"
            elif m_type == MessageType.FOOD_PICKED_UP:
                self.orders[order_id]["status"] = "PICKED_UP"
            elif m_type == MessageType.ORDER_DELIVERED:
                self.orders[order_id]["status"] = "DELIVERED"
                if self.process_id == 3:
                    self.local_data["completed_deliveries"] = self.local_data.get("completed_deliveries", 0) + 1

    def capture_process_snapshot(self) -> ProcessSnapshot:
        """Captures local process state and vector clock for Chandy-Lamport snapshot."""
        return ProcessSnapshot(
            process_id=self.process_id,
            process_name=self.name,
            role=self.role,
            vector_clock=self.vector_clock.get_clock(),
            local_state={
                "status": self.status.value,
                "orders": {k: dict(v) for k, v in self.orders.items()},
                "local_data": dict(self.local_data),
                "sequence_number": self.sequence_number
            }
        )

    def get_state(self) -> ProcessState:
        return ProcessState(
            process_id=self.process_id,
            name=self.name,
            role=self.role,
            status=self.status,
            vector_clock=self.vector_clock.get_clock(),
            total_events=self.sequence_number,
            current_orders=list(self.orders.values()),
            local_data=self.local_data
        )

    def reset(self):
        self.vector_clock.reset()
        self.sequence_number = 0
        self.orders.clear()
        self.local_data = {
            "availability": "OPEN" if self.process_id in [2, 4] else "READY",
            "active_tasks": [],
            "completed_deliveries": 0 if self.process_id == 3 else 0
        }
        self.status = ProcessStatus.ACTIVE
