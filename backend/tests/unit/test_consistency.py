from backend.app.models.snapshot import GlobalSnapshot, ProcessSnapshot, ChannelSnapshot
from backend.app.snapshot.consistency import ConsistencyChecker
from backend.app.models.message import Message, MessageType

def test_consistent_snapshot():
    # 4 process snapshots with monotonically consistent vector clocks
    p_snaps = {
        1: ProcessSnapshot(process_id=1, process_name="P1", role="Order Processor", vector_clock=[2, 1, 0, 0]),
        2: ProcessSnapshot(process_id=2, process_name="P2", role="Restaurant A", vector_clock=[2, 2, 0, 0]),
        3: ProcessSnapshot(process_id=3, process_name="P3", role="Delivery Partner", vector_clock=[2, 2, 1, 0]),
        4: ProcessSnapshot(process_id=4, process_name="P4", role="Restaurant B", vector_clock=[0, 0, 0, 1])
    }
    ch_snaps = {
        "1->2": ChannelSnapshot(sender_id=1, receiver_id=2, channel_key="1->2", messages=[]),
        "2->3": ChannelSnapshot(sender_id=2, receiver_id=3, channel_key="2->3", messages=[])
    }
    
    snap = GlobalSnapshot(
        snapshot_id="SNAP-TEST-01",
        initiated_by=1,
        status="COMPLETED",
        process_states=p_snaps,
        channel_states=ch_snaps
    )
    
    res = ConsistencyChecker.verify(snap)
    assert res.consistent is True
    assert len(res.issues) == 0

def test_inconsistent_snapshot_detected():
    # P1 claims it received from P2 with clock[2]=5, but P2's snapshot is only at clock[2]=2
    p_snaps = {
        1: ProcessSnapshot(process_id=1, process_name="P1", role="Order Processor", vector_clock=[2, 5, 0, 0]),
        2: ProcessSnapshot(process_id=2, process_name="P2", role="Restaurant A", vector_clock=[2, 2, 0, 0]),
        3: ProcessSnapshot(process_id=3, process_name="P3", role="Delivery Partner", vector_clock=[2, 2, 1, 0]),
        4: ProcessSnapshot(process_id=4, process_name="P4", role="Restaurant B", vector_clock=[0, 0, 0, 1])
    }
    snap = GlobalSnapshot(
        snapshot_id="SNAP-TEST-02",
        initiated_by=1,
        status="COMPLETED",
        process_states=p_snaps,
        channel_states={}
    )
    
    res = ConsistencyChecker.verify(snap)
    assert res.consistent is False
    assert len(res.issues) > 0
