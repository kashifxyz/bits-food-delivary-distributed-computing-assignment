import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class MessageType(str, Enum):
    ORDER_CREATED = "ORDER_CREATED"
    ORDER_ACCEPTED = "ORDER_ACCEPTED"
    ORDER_REJECTED = "ORDER_REJECTED"
    FOOD_PREPARING = "FOOD_PREPARING"
    FOOD_READY = "FOOD_READY"
    DELIVERY_REQUEST = "DELIVERY_REQUEST"
    DELIVERY_ACCEPTED = "DELIVERY_ACCEPTED"
    FOOD_PICKED_UP = "FOOD_PICKED_UP"
    ORDER_DELIVERED = "ORDER_DELIVERED"
    STATUS_UPDATE = "STATUS_UPDATE"
    MARKER = "MARKER"

class Message(BaseModel):
    id: str = Field(default_factory=lambda: f"MSG-{uuid.uuid4().hex[:8].upper()}")
    sender_id: int = Field(..., description="Process ID of sender (1-4)")
    receiver_id: int = Field(..., description="Process ID of receiver (1-4)")
    message_type: MessageType = Field(..., description="Type of distributed message")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Payload data e.g. order details")
    vector_clock: List[int] = Field(..., description="Vector timestamp attached by sender")
    snapshot_id: Optional[str] = Field(default=None, description="Snapshot ID if this is a MARKER message")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
