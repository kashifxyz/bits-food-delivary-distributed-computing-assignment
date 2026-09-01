import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from vector_clock import VectorClock
from colorama import Fore, Style, init

init(autoreset=True)

def print_test(name):
    print(f"\n{Fore.MAGENTA}{'='*50}")
    print(f"TEST: {name}")
    print(f"{'='*50}{Style.RESET_ALL}")

def print_pass(msg):
    print(f"{Fore.GREEN}✓ PASS: {msg}{Style.RESET_ALL}")

def print_fail(msg):
    print(f"{Fore.RED}✗ FAIL: {msg}{Style.RESET_ALL}")

def test_initial_clock():
    print_test("Initial Clock State")
    vc = VectorClock(process_id=0, num_processes=5)
    assert vc.get_clock() == [0, 0, 0, 0, 0], "Initial clock should be all zeros"
    print_pass("Initial clock is [0, 0, 0, 0, 0]")

def test_increment():
    print_test("Increment Own Slot")
    vc = VectorClock(process_id=1, num_processes=5)
    vc.increment()
    assert vc.get_clock()[1] == 1, "P1 slot should be 1 after increment"
    vc.increment()
    assert vc.get_clock()[1] == 2, "P1 slot should be 2 after second increment"
    print_pass("Increment works correctly")

def test_send_event():
    print_test("Send Event")
    vc = VectorClock(process_id=0, num_processes=5)
    clock = vc.send_event()
    assert clock[0] == 1, "P0 slot should be 1 after send"
    assert clock == vc.get_clock(), "Returned clock should match internal clock"
    print_pass("Send event increments and returns correct clock")

def test_receive_event():
    print_test("Receive Event — Merge and Increment")
    vc0 = VectorClock(process_id=0, num_processes=5)
    vc1 = VectorClock(process_id=1, num_processes=5)

    clock0 = vc0.send_event()
    vc1.receive_event(clock0)

    assert vc1.get_clock()[0] == 1, "P1 should know P0 is at 1 after merge"
    assert vc1.get_clock()[1] == 1, "P1 should increment own slot after receive"
    print_pass("Receive event merges and increments correctly")

def test_internal_event():
    print_test("Internal Event")
    vc = VectorClock(process_id=2, num_processes=5)
    vc.internal_event("Preparing food")
    assert vc.get_clock()[2] == 1, "P2 slot should be 1 after internal event"
    vc.internal_event("Food ready")
    assert vc.get_clock()[2] == 2, "P2 slot should be 2 after second internal event"
    print_pass("Internal event increments own slot correctly")

def test_concurrent_events():
    print_test("Concurrent Event Detection")
    vc1 = VectorClock(process_id=1, num_processes=5)
    vc2 = VectorClock(process_id=2, num_processes=5)

    vc0 = VectorClock(process_id=0, num_processes=5)
    clock0 = vc0.send_event()
    vc1.receive_event(clock0)
    vc2.receive_event(clock0)

    vc1.internal_event("Baking pizza independent")
    vc2.internal_event("Grilling patty independent")

    assert vc1.is_concurrent(vc2.get_clock()), "P1 and P2 events should be concurrent"
    print_pass("Concurrent events detected correctly")

def test_not_concurrent():
    print_test("Non-Concurrent Event Detection")
    vc0 = VectorClock(process_id=0, num_processes=5)
    vc1 = VectorClock(process_id=1, num_processes=5)

    clock0 = vc0.send_event()
    vc1.receive_event(clock0)

    assert not vc1.is_concurrent(vc0.get_clock()), "P1 happens after P0 so not concurrent"
    print_pass("Non-concurrent events detected correctly")

def test_full_order_flow():
    print_test("Full Order Flow — P0 → P1 → P3")
    vc0 = VectorClock(process_id=0, num_processes=5)
    vc1 = VectorClock(process_id=1, num_processes=5)
    vc3 = VectorClock(process_id=3, num_processes=5)

    clock0 = vc0.send_event()
    vc1.receive_event(clock0)
    vc1.internal_event("Order confirmed")
    vc1.internal_event("Preparing food")
    vc1.internal_event("Food ready for pickup")
    clock1 = vc1.send_event()
    vc3.receive_event(clock1)
    vc3.internal_event("Order picked up")
    vc3.internal_event("In transit")
    vc3.internal_event("Order delivered")

    assert vc3.get_clock()[0] == 1, "P3 should know P0 sent 1 message"
    assert vc3.get_clock()[1] >= 4, "P3 should know P1 had at least 4 events"
    assert vc3.get_clock()[3] == 4, "P3 should have 4 events (1 receive + 3 internal)"
    print_pass("Full order flow P0 → P1 → P3 vector clocks are correct")

def test_thread_safety():
    print_test("Thread Safety")
    import threading
    vc = VectorClock(process_id=0, num_processes=5)

    def do_increments():
        for _ in range(100):
            vc.increment()

    threads = [threading.Thread(target=do_increments) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert vc.get_clock()[0] == 500, f"Expected 500 increments, got {vc.get_clock()[0]}"
    print_pass("Thread safety — 500 concurrent increments all counted correctly")

if __name__ == "__main__":
    print(f"\n{Fore.MAGENTA}Running Vector Clock Tests{Style.RESET_ALL}")
    test_initial_clock()
    test_increment()
    test_send_event()
    test_receive_event()
    test_internal_event()
    test_concurrent_events()
    test_not_concurrent()
    test_full_order_flow()
    test_thread_safety()
    print(f"\n{Fore.GREEN}All tests passed!{Style.RESET_ALL}\n")