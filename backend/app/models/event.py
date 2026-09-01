import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field

class EventType(str, Enum):
    INTERNAL = "INTERNAL"
    SEND = "SEND"
    RECEIVE = "RECEIVE"
    MARKER = "MARKER"
    SNAPSHOT_START = "SNAPSHOT_START"
    SNAPSHOT_COMPLETE = "SNAPSHOT_COMPLETE"

class Event(BaseModel):
    event_id: str = Field(default_factory=lambda: f"E{uuid.uuid4().hex[:6].upper()}")
    process_id: int = Field(..., description="Logical Process ID (1, 2, 3, or 4)")
    event_type: EventType = Field(..., description="Type of event")
    description: str = Field(..., description="Human-readable event description")
    message_id: Optional[str] = Field(default=None, description="Associated message ID if send/receive")
    order_id: Optional[int] = Field(default=None, description="Associated order ID if any")
    vector_clock: List[int] = Field(..., description="Vector Clock at time of event")
    sequence_number: int = Field(default=0, description="Process local sequence number")
    wall_clock_timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Display only wall-clock timestamp"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)
