import pytest
from backend.app.models.message import Message, MessageType

def test_message_creation():
    msg = Message(
        sender_id=1,
        receiver_id=2,
        message_type=MessageType.ORDER_CREATED,
        payload={"order_id": 101, "customer": "Alice"},
        vector_clock=[1, 0, 0, 0]
    )
    assert msg.id.startswith("MSG-")
    assert msg.sender_id == 1
    assert msg.receiver_id == 2
    assert msg.message_type == MessageType.ORDER_CREATED
    assert msg.vector_clock == [1, 0, 0, 0]

def test_marker_message():
    msg = Message(
        sender_id=2,
        receiver_id=3,
        message_type=MessageType.MARKER,
        payload={"marker": True},
        vector_clock=[2, 3, 0, 0],
        snapshot_id="SNAP-100"
    )
    assert msg.message_type == MessageType.MARKER
    assert msg.snapshot_id == "SNAP-100"
