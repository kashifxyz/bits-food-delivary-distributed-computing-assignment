from typing import List, Optional, Dict, Any
from backend.app.distributed.process_manager import process_manager
from backend.app.models.order import Order, OrderStatus
from backend.app.models.message import MessageType

class OrderService:
    def __init__(self, pm=process_manager):
        self.pm = pm
        self._orders: Dict[int, Order] = {}

    def get_all_orders(self) -> List[Order]:
        # Aggregate orders from P1 or all processes
        p1 = self.pm.get_process(1)
        if p1:
            return [Order(**o) for o in p1.orders.values()]
        return []

    def get_order(self, order_id: int) -> Optional[Order]:
        p1 = self.pm.get_process(1)
        if p1 and order_id in p1.orders:
            return Order(**p1.orders[order_id])
        return None

    async def create_order(self, customer: str, restaurant_id: int = 2, items: List[str] = None) -> Order:
        order_id = len(self.get_all_orders()) + 101
        p1 = self.pm.get_process(1)
        
        # P1 creates order internal event
        await p1.log_internal_event(f"New order #{order_id} placed by {customer}", order_id=order_id)
        
        order_data = {
            "order_id": order_id,
            "customer": customer,
            "restaurant_id": restaurant_id,
            "delivery_partner_id": 3,
            "items": items or ["Veg Biryani", "Raita"],
            "status": OrderStatus.CREATED
        }
        p1.orders[order_id] = order_data
        
        # P1 sends ORDER_CREATED message to target restaurant
        await p1.send_msg(
            receiver_id=restaurant_id,
            message_type=MessageType.ORDER_CREATED,
            payload=order_data,
            order_id=order_id
        )
        
        return Order(**order_data)

    async def trigger_order_action(self, order_id: int, action: str) -> Dict[str, Any]:
        """Manually trigger intermediate actions on an active order for demonstration."""
        p2 = self.pm.get_process(2)
        p3 = self.pm.get_process(3)
        p1 = self.pm.get_process(1)
        
        if action == "ACCEPT" and p2:
            await p2.log_internal_event(f"P2 accepted Order #{order_id}", order_id=order_id)
            await p2.send_msg(1, MessageType.ORDER_ACCEPTED, {"order_id": order_id}, order_id=order_id)
        elif action == "PREPARE" and p2:
            await p2.log_internal_event(f"P2 started food prep for #{order_id}", order_id=order_id)
        elif action == "READY" and p2:
            await p2.send_msg(3, MessageType.FOOD_READY, {"order_id": order_id}, order_id=order_id)
        elif action == "PICKUP" and p3:
            await p3.log_internal_event(f"P3 picked up food for #{order_id}", order_id=order_id)
        elif action == "DELIVER" and p3:
            await p3.send_msg(1, MessageType.ORDER_DELIVERED, {"order_id": order_id}, order_id=order_id)
        else:
            raise ValueError(f"Unknown or unsupported action: {action}")
            
        return {"order_id": order_id, "action": action, "status": "SUCCESS"}

order_service = OrderService()
