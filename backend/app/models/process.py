from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class ProcessStatus(str, Enum):
    ACTIVE = "ACTIVE"
    IDLE = "IDLE"
    BUSY = "BUSY"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"

class ProcessConfig(BaseModel):
    id: int
    name: str
    role: str
    description: str
    host: str = "127.0.0.1"
    port: int
    status: ProcessStatus = ProcessStatus.ACTIVE

class ProcessState(BaseModel):
    process_id: int
    name: str
    role: str
    status: ProcessStatus
    vector_clock: List[int]
    total_events: int
    current_orders: List[Dict[str, Any]] = Field(default_factory=list)
    local_data: Dict[str, Any] = Field(default_factory=dict)
