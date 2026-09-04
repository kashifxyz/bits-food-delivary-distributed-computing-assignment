"""
P3 - Delivery Partner 1 (Fleet Runner A)
Runs on Node 3 (slave2).

Responsibilities:
- Receive an ORDER message from P1 (Restaurant A).
- Perform the delivery lifecycle as internal events:
      Order picked up -> In transit -> Order delivered
- Notify P0 that the order has been delivered.
- Participate in the Chandy-Lamport snapshot algorithm: on receiving a
  MARKER from P0, record local state and send it back to P0 as a STATE
  message (P3 is a leaf process, so there is nothing to forward to).
"""

import json
import socket
import threading
import time

from vector_clock import VectorClock

PROCESS_NAME = "P3"
PROCESS_ID = 3
NUM_PROCESSES = 5

# Update the IP addresses below to the actual Prayogshala node IPs when
# deploying across nodes. Defaults to localhost for local testing, where
# all processes run on the same machine on different ports.
NODE_IP = {
    "P0": "localhost",  # Node 1 (master)
    "P1": "localhost",  # Node 2 (slave1)
    "P2": "localhost",  # Node 2 (slave1)
    "P3": "localhost",  # Node 3 (slave2)
    "P4": "localhost",  # Node 3 (slave2)
}

PORTS = {
    "P0": 5000,
    "P1": 5001,
    "P2": 5002,
    "P3": 5003,
    "P4": 5004,
}

HOST = "0.0.0.0"

vc = VectorClock(PROCESS_ID, NUM_PROCESSES)

# --- Chandy-Lamport snapshot state ---
snapshot_lock = threading.Lock()
snapshot_in_progress = False
recorded_state = None


def send_message(target: str, msg_type: str, data, clock: list) -> None:
    """Send a JSON message to the target process over a TCP socket."""
    message = {
        "type": msg_type,
        "data": data,
        "clock": clock,
        "from": PROCESS_NAME,
    }
    try:
        with socket.create_connection((NODE_IP[target], PORTS[target]), timeout=5) as s:
            s.sendall(json.dumps(message).encode())
    except Exception as e:
        print(f"[ERROR] {PROCESS_NAME} could not send message to {target}: {e}")


def handle_order(msg: dict) -> None:
    """Process an incoming order from P1 and run it through the delivery lifecycle."""
    order_data = msg["data"]
    clock = vc.receive_event(msg["clock"])
    print(f"[RECV] {PROCESS_NAME} \u2190 {msg['from']} | {order_data} | Clock: {clock}")

    # --- Delivery lifecycle: internal events ---
    time.sleep(1)
    clock = vc.internal_event(f"Order picked up | {order_data}")
    print(f"[INTERNAL] {PROCESS_NAME} | Order picked up | {order_data} | Clock: {clock}")

    time.sleep(1)
    clock = vc.internal_event(f"In transit | {order_data}")
    print(f"[INTERNAL] {PROCESS_NAME} | In transit | {order_data} | Clock: {clock}")

    time.sleep(1)
    clock = vc.internal_event(f"Order delivered | {order_data}")
    print(f"[INTERNAL] {PROCESS_NAME} | Order delivered | {order_data} | Clock: {clock}")

    # --- Notify P0 that delivery is complete ---
    clock = vc.send_event()
    delivery_msg = f"{order_data} delivered by {PROCESS_NAME}"
    send_message("P0", "DELIVERY", delivery_msg, clock)
    print(f"[SEND] {PROCESS_NAME} \u2192 P0 | {delivery_msg} | Clock: {clock}")


def handle_marker(msg: dict) -> None:
    """Chandy-Lamport: record local state on first marker and report it to P0."""
    global snapshot_in_progress, recorded_state

    with snapshot_lock:
        if snapshot_in_progress:
            print(f"[SNAPSHOT] {PROCESS_NAME} | Duplicate marker ignored | Clock: {vc.get_clock()}")
            return

        snapshot_in_progress = True
        recorded_state = vc.get_clock()
        print(f"[SNAPSHOT] {PROCESS_NAME} | Local state recorded | Clock: {recorded_state}")

    # P3 has no downstream process to forward the marker to (leaf process),
    # so just report the recorded state back to P0.
    clock = vc.send_event()
    send_message(
        "P0",
        "STATE",
        {"process": PROCESS_NAME, "local_state": recorded_state},
        clock,
    )
    print(f"[SEND] {PROCESS_NAME} \u2192 P0 | STATE reported: {recorded_state} | Clock: {clock}")

    with snapshot_lock:
        snapshot_in_progress = False
        recorded_state = None


def handle_client(conn: socket.socket, addr) -> None:
    try:
        data = b""
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            data += chunk
        if not data:
            return

        msg = json.loads(data.decode())
        msg_type = msg.get("type")

        if msg_type == "ORDER":
            handle_order(msg)
        elif msg_type == "MARKER":
            handle_marker(msg)
        else:
            print(f"[WARN] {PROCESS_NAME} received unknown message type: {msg_type}")
    except Exception as e:
        print(f"[ERROR] {PROCESS_NAME} failed to handle message from {addr}: {e}")
    finally:
        conn.close()


def start_server() -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORTS[PROCESS_NAME]))
    server.listen(5)
    print(f"{PROCESS_NAME} (Delivery Partner 1 - Fleet Runner A) listening on port {PORTS[PROCESS_NAME]}...")

    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()


if __name__ == "__main__":
    start_server()


