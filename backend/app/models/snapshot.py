import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from backend.app.models.message import Message

class ProcessSnapshot(BaseModel):
    process_id: int
    process_name: str
    role: str
    vector_clock: List[int]
    recorded_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    local_state: Dict[str, Any] = Field(default_factory=dict)

class ChannelSnapshot(BaseModel):
    sender_id: int
    receiver_id: int
    channel_key: str = Field(description="e.g. '1->2'")
    messages: List[Message] = Field(default_factory=list, description="In-transit messages captured during snapshot")
    is_recording: bool = False
    recording_completed: bool = False

class ConsistencyCheckResult(BaseModel):
    consistent: bool
    issues: List[str] = Field(default_factory=list)
    explanation: str = ""
    analyzed_events_count: int = 0
    checked_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class GlobalSnapshot(BaseModel):
    snapshot_id: str = Field(default_factory=lambda: f"SNAP-{uuid.uuid4().hex[:6].upper()}")
    initiated_by: int = Field(..., description="Process ID that initiated the snapshot")
    status: str = Field(default="IN_PROGRESS", description="IN_PROGRESS, COMPLETED, FAILED")
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    process_states: Dict[int, ProcessSnapshot] = Field(default_factory=dict)
    channel_states: Dict[str, ChannelSnapshot] = Field(default_factory=dict)
    consistency: Optional[ConsistencyCheckResult] = None
