import sys
import os
import time
import subprocess
import socket
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import p0
from vector_clock import VectorClock

def test_p0_order_dispatch_and_snapshot():
    # Configure custom test ports to avoid local macOS port 5000 AirPlay collision
    test_ports = {"P0": 6000, "P1": 6001, "P2": 6002, "P3": 6003, "P4": 6004}
    p0.PORTS = test_ports
    
    # Start test listener for P0
    server_p0 = p0.start_listener(test_ports["P0"])

    # Mock P1 listener that receives ORDER and responds with STATE
    def mock_p1_listener():
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", test_ports["P1"]))
        s.listen(5)
        while True:
            try:
                conn, _ = s.accept()
                with conn:
                    data = conn.recv(4096)
                    if data:
                        msg = json.loads(data.decode())
                        if msg.get("type") == "MARKER":
                            # Respond with STATE message back to P0
                            state_msg = {
                                "type": "STATE",
                                "snapshot_id": msg["snapshot_id"],
                                "data": {
                                    "process": "P1",
                                    "vector_clock": [1, 3, 0, 0, 0],
                                    "local_state": "Preparing food"
                                },
                                "clock": [1, 4, 0, 0, 0],
                                "from": "P1"
                            }
                            # Send to P0
                            s_out = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            s_out.connect(("127.0.0.1", test_ports["P0"]))
                            s_out.send(json.dumps(state_msg).encode())
                            s_out.close()
            except Exception:
                break

    import threading
    t1 = threading.Thread(target=mock_p1_listener, daemon=True)
    t1.start()
    time.sleep(0.3)

    # Dispatch order to P1
    order_id = p0.send_order("P1", "Margherita Pizza", order_id=101)
    assert order_id == 101
    assert p0.vc.get_clock()[0] >= 2

    # Trigger Snapshot
    p0.trigger_snapshot("SNAP_UNIT_TEST")
    time.sleep(0.5)

    # Verify P0 state store recorded P0 and P1
    assert "SNAP_UNIT_TEST" in p0.state_store
    assert "P0" in p0.state_store["SNAP_UNIT_TEST"]
    assert "P1" in p0.state_store["SNAP_UNIT_TEST"]

    p0.check_snapshot_consistency("SNAP_UNIT_TEST")
    print("\n✓ Integration test between P0 and mock P1 passed successfully!\n")

if __name__ == "__main__":
    test_p0_order_dispatch_and_snapshot()
