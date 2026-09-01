from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Any, Dict
from pydantic import BaseModel, Field

class OrderStatus(str, Enum):
    CREATED = "CREATED"
    ACCEPTED = "ACCEPTED"
    PREPARING = "PREPARING"
    READY = "READY"
    PICKED_UP = "PICKED_UP"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"

class Order(BaseModel):
    order_id: int = Field(..., description="Unique Order Identifier")
    customer: str = Field(default="Customer-1", description="Customer Name/ID")
    restaurant_id: int = Field(default=2, description="Target Restaurant Process ID (P2 or P4)")
    delivery_partner_id: int = Field(default=3, description="Delivery Partner Process ID (P3)")
    items: list[str] = Field(default_factory=lambda: ["Paneer Butter Masala", "Garlic Naan"], description="Order items")
    status: OrderStatus = Field(default=OrderStatus.CREATED, description="Current lifecycle state")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    history: list[Dict[str, Any]] = Field(default_factory=list, description="State transition log")
