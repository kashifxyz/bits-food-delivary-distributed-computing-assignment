import pytest
import asyncio
from backend.app.distributed.channel import Channel
from backend.app.models.message import Message, MessageType

@pytest.mark.asyncio
async def test_channel_fifo_send_receive():
    ch = Channel(sender_id=1, receiver_id=2)
    m1 = Message(sender_id=1, receiver_id=2, message_type=MessageType.ORDER_CREATED, vector_clock=[1,0,0,0])
    m2 = Message(sender_id=1, receiver_id=2, message_type=MessageType.STATUS_UPDATE, vector_clock=[2,0,0,0])
    
    await ch.send(m1)
    await ch.send(m2)
    
    r1 = await ch.receive()
    r2 = await ch.receive()
    
    assert r1.id == m1.id
    assert r2.id == m2.id

@pytest.mark.asyncio
async def test_channel_snapshot_recording():
    ch = Channel(sender_id=1, receiver_id=2)
    m_in_flight = Message(sender_id=1, receiver_id=2, message_type=MessageType.FOOD_READY, vector_clock=[1,2,0,0])
    
    ch.start_recording()
    assert ch.is_recording() is True
    
    await ch.send(m_in_flight)
    received = await ch.receive()
    assert received.id == m_in_flight.id
    
    recorded = ch.stop_recording()
    assert len(recorded) == 1
    assert recorded[0].id == m_in_flight.id
