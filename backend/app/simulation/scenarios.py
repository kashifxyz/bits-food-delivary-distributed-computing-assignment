import asyncio
import logging
from typing import Dict, Any, List
from backend.app.models.message import MessageType
from backend.app.models.order import OrderStatus
from backend.app.models.vector_clock import is_concurrent, compare_clocks

logger = logging.getLogger("Scenarios")

class ScenarioRunner:
    def __init__(self, process_manager):
        self.pm = process_manager

    async def run_tc01_basic_order_flow(self, order_id: int = 101) -> Dict[str, Any]:
        """
        TC01: Basic Order Lifecycle
        P1 -> P2 -> P3 -> P1
        """
        p1 = self.pm.get_process(1)
        p2 = self.pm.get_process(2)
        p3 = self.pm.get_process(3)

        # 1. P1 creates order locally
        e1 = await p1.log_internal_event(f"Order #{order_id} created by Customer-1", order_id=order_id)
        p1.orders[order_id] = {
            "order_id": order_id, "customer": "Customer-1", "status": "CREATED",
            "restaurant_id": 2, "delivery_partner_id": 3, "items": ["Burger", "Fries"]
        }
        await asyncio.sleep(0.05)

        # 2. P1 sends order to P2
        msg1 = await p1.send_msg(
            receiver_id=2,
            message_type=MessageType.ORDER_CREATED,
            payload={"order_id": order_id, "customer": "Customer-1", "items": ["Burger", "Fries"]},
            order_id=order_id
        )
        await asyncio.sleep(0.1)

        # 3. P2 internal events: Accept & Prepare
        e2 = await p2.log_internal_event(f"Restaurant A accepted Order #{order_id}", order_id=order_id)
        e3 = await p2.log_internal_event(f"Restaurant A preparing food for Order #{order_id}", order_id=order_id)
        await asyncio.sleep(0.05)

        # 4. P2 sends FOOD_READY to P3
        msg2 = await p2.send_msg(
            receiver_id=3,
            message_type=MessageType.FOOD_READY,
            payload={"order_id": order_id, "restaurant_id": 2},
            order_id=order_id
        )
        await asyncio.sleep(0.1)

        # 5. P3 internal event: Pick up
        e4 = await p3.log_internal_event(f"Delivery Partner P3 picked up Order #{order_id}", order_id=order_id)
        await asyncio.sleep(0.05)

        # 6. P3 delivers and notifies P1
        msg3 = await p3.send_msg(
            receiver_id=1,
            message_type=MessageType.ORDER_DELIVERED,
            payload={"order_id": order_id, "status": "DELIVERED"},
            order_id=order_id
        )
        await asyncio.sleep(0.1)

        e5 = await p1.log_internal_event(f"Order #{order_id} finalized and closed", order_id=order_id)

        return {
            "scenario": "TC01 — Basic Order Flow",
            "status": "SUCCESS",
            "order_id": order_id,
            "final_vector_clocks": {p.name: p.vector_clock.get_clock() for p in self.pm.get_all_processes()}
        }

    async def run_tc02_vector_clock_progression(self) -> Dict[str, Any]:
        """
        TC02: Vector Clock Progression across P1, P2, P3, P4
        """
        p1 = self.pm.get_process(1)
        p2 = self.pm.get_process(2)
        p3 = self.pm.get_process(3)
        p4 = self.pm.get_process(4)

        # P1 tick internal -> [1,0,0,0]
        await p1.log_internal_event("P1 periodic health check")
        
        # P1 sends to P2 -> P1:[2,0,0,0], P2 receives -> P2:[2,1,0,0]
        await p1.send_msg(2, MessageType.STATUS_UPDATE, {"ping": "P1->P2"})
        await asyncio.sleep(0.1)

        # P2 internal -> P2:[2,2,0,0]
        await p2.log_internal_event("P2 inventory audit")

        # P2 sends to P3 -> P2:[2,3,0,0], P3 receives -> P3:[2,3,1,0]
        await p2.send_msg(3, MessageType.STATUS_UPDATE, {"ping": "P2->P3"})
        await asyncio.sleep(0.1)

        # P4 independent internal -> P4:[0,0,0,1]
        await p4.log_internal_event("P4 daily special menu update")

        return {
            "scenario": "TC02 — Vector Clock Progression",
            "status": "SUCCESS",
            "clocks": {p.name: p.vector_clock.get_clock() for p in self.pm.get_all_processes()}
        }

    async def run_tc03_concurrent_events(self) -> Dict[str, Any]:
        """
        TC03: Deterministic Concurrent Events
        P2 performs internal action (e.g. food prep) while P4 independently performs availability update.
        """
        p2 = self.pm.get_process(2)
        p4 = self.pm.get_process(4)

        # Generate independent events at P2 and P4 without inter-process message exchange
        ev_p2 = await p2.log_internal_event("Restaurant A started preparing special dessert", metadata={"tag": "P2_CONCURRENT"})
        ev_p4 = await p4.log_internal_event("Restaurant B updated table reservation & availability", metadata={"tag": "P4_CONCURRENT"})

        comparison = self.pm.event_manager.compare_events(ev_p2.event_id, ev_p4.event_id)

        return {
            "scenario": "TC03 — Concurrent Events",
            "status": "SUCCESS",
            "event_a": {
                "id": ev_p2.event_id,
                "process": "P2",
                "description": ev_p2.description,
                "vector_clock": ev_p2.vector_clock
            },
            "event_b": {
                "id": ev_p4.event_id,
                "process": "P4",
                "description": ev_p4.description,
                "vector_clock": ev_p4.vector_clock
            },
            "relation": comparison["relation"],
            "explanation": comparison["explanation"]
        }

    async def run_tc04_in_transit_message_snapshot(self) -> Dict[str, Any]:
        """
        TC04: In-transit message recorded during Global Snapshot.
        Sends a message from P2 to P3, then immediately initiates Chandy-Lamport snapshot.
        """
        p1 = self.pm.get_process(1)
        p2 = self.pm.get_process(2)

        # P2 sends an order update message to P3
        msg = await p2.send_msg(
            receiver_id=3,
            message_type=MessageType.FOOD_READY,
            payload={"order_id": 999, "note": "Express in-transit item"},
            order_id=999
        )

        # Immediately initiate global snapshot from P1
        snapshot = await self.pm.snapshot_manager.initiate_snapshot(initiator_id=1)
        await asyncio.sleep(0.3)

        latest_snap = self.pm.snapshot_manager.get_snapshot(snapshot.snapshot_id)

        return {
            "scenario": "TC04 — In-Transit Message Snapshot",
            "status": "SUCCESS",
            "snapshot_id": snapshot.snapshot_id,
            "snapshot_status": latest_snap.status if latest_snap else "UNKNOWN",
            "consistency": latest_snap.consistency.model_dump() if latest_snap and latest_snap.consistency else None
        }

    async def run_tc05_global_snapshot(self) -> Dict[str, Any]:
        """
        TC05: Complete distributed execution across all 4 processes followed by Chandy-Lamport snapshot.
        """
        p1 = self.pm.get_process(1)
        p2 = self.pm.get_process(2)
        p3 = self.pm.get_process(3)
        p4 = self.pm.get_process(4)

        # Multi-process activity
        await p1.log_internal_event("P1 initialized batch order schedule")
        await p4.log_internal_event("P4 started bakery oven")
        await p1.send_msg(2, MessageType.ORDER_CREATED, {"order_id": 201, "customer": "Alice"}, order_id=201)
        await p4.send_msg(3, MessageType.DELIVERY_REQUEST, {"order_id": 301, "pickup": "P4"}, order_id=301)
        await asyncio.sleep(0.1)

        # Initiate Chandy-Lamport Snapshot from P2
        snapshot = await self.pm.snapshot_manager.initiate_snapshot(initiator_id=2)
        await asyncio.sleep(0.3)

        latest_snap = self.pm.snapshot_manager.get_snapshot(snapshot.snapshot_id)

        return {
            "scenario": "TC05 — Global Snapshot",
            "status": "SUCCESS",
            "snapshot_id": snapshot.snapshot_id,
            "process_states_count": len(latest_snap.process_states) if latest_snap else 0,
            "channel_states_count": len(latest_snap.channel_states) if latest_snap else 0,
            "consistency": latest_snap.consistency.model_dump() if latest_snap and latest_snap.consistency else None
        }
