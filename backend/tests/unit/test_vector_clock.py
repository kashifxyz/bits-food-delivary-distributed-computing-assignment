import pytest
from backend.app.vector_clock.vector_clock import VectorClock
from backend.app.models.vector_clock import CausalRelation, happens_before, is_concurrent, are_equal, compare_clocks

def test_initialization():
    vc = VectorClock(process_id=1, num_processes=4)
    assert vc.get_clock() == [0, 0, 0, 0]
    
    with pytest.raises(ValueError):
        VectorClock(process_id=5, num_processes=4)

def test_internal_event():
    vc = VectorClock(process_id=2, num_processes=4)
    res = vc.tick_internal()
    assert res == [0, 1, 0, 0]
    assert vc.get_clock() == [0, 1, 0, 0]
    
    res2 = vc.tick_internal()
    assert res2 == [0, 2, 0, 0]

def test_send_event():
    vc = VectorClock(process_id=1, num_processes=4)
    sent_clock = vc.tick_send()
    assert sent_clock == [1, 0, 0, 0]
    assert vc.get_clock() == [1, 0, 0, 0]

def test_receive_event():
    vc2 = VectorClock(process_id=2, num_processes=4)
    # Incoming clock from P1 after send: [1, 0, 0, 0]
    received_clock = [1, 0, 0, 0]
    
    new_clock = vc2.tick_receive(received_clock)
    # max([0,0,0,0], [1,0,0,0]) = [1,0,0,0], then P2 increments its own -> [1, 1, 0, 0]
    assert new_clock == [1, 1, 0, 0]
    assert vc2.get_clock() == [1, 1, 0, 0]

def test_happens_before():
    a = [1, 0, 0, 0]
    b = [2, 1, 0, 0]
    assert happens_before(a, b) is True
    assert happens_before(b, a) is False
    
    # Same clocks do not happen before each other
    assert happens_before([1, 1, 0, 0], [1, 1, 0, 0]) is False

def test_concurrency():
    # P2 event [2, 3, 0, 0] vs P4 event [0, 0, 0, 2]
    e_p2 = [2, 3, 0, 0]
    e_p4 = [0, 0, 0, 2]
    
    assert happens_before(e_p2, e_p4) is False
    assert happens_before(e_p4, e_p2) is False
    assert is_concurrent(e_p2, e_p4) is True
    assert compare_clocks(e_p2, e_p4) == CausalRelation.CONCURRENT

def test_compare_clocks():
    assert compare_clocks([1, 0, 0, 0], [2, 1, 0, 0]) == CausalRelation.BEFORE
    assert compare_clocks([2, 1, 0, 0], [1, 0, 0, 0]) == CausalRelation.AFTER
    assert compare_clocks([1, 1, 0, 0], [1, 1, 0, 0]) == CausalRelation.SAME
    assert compare_clocks([1, 2, 0, 0], [0, 1, 3, 0]) == CausalRelation.CONCURRENT
