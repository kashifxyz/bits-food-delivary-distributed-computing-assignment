from typing import Optional
from pydantic import BaseModel, Field
from backend.app.models.message import Message, MessageType

class MarkerMessage(BaseModel):
    snapshot_id: str
    initiator_id: int
    sender_id: int
    receiver_id: int

def create_marker(snapshot_id: str, sender_id: int, receiver_id: int, clock: list[int]) -> Message:
    return Message(
        sender_id=sender_id,
        receiver_id=receiver_id,
        message_type=MessageType.MARKER,
        payload={"marker_info": f"Chandy-Lamport Marker for {snapshot_id}"},
        vector_clock=clock,
        snapshot_id=snapshot_id
    )
