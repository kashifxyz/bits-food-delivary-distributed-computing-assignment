"""
p3.py - P3 : Delivery Partner 1 (Fleet Runner A)
--------------------------------------------------
Role:
    - Receives a DELIVERY handoff message from P1 (Restaurant A - Pizza Palace)
      for Order #1.
    - Runs 3 internal events: Order picked up -> In transit -> Order delivered.
    - Sends a DELIVERY confirmation back to P0 once delivered.
    - Participates in the Chandy-Lamport snapshot algorithm: on receiving a
      MARKER (forwarded to it by P1), records its local state and sends a
      STATE message back to P0. P3 is a leaf node in the flow
      (P0 -> P1 -> P3), so it does not forward the marker any further.

Run:
    python p3.py
"""

import socket
import threading
import json
import time
from colorama import Fore, Style, init

from vector_clock import VectorClock

init(autoreset=True)

# ----------------------------------------------------------------------
# Identity / config
# ----------------------------------------------------------------------
PROCESS_ID = 3
PROCESS_NAME = "P3"
UPSTREAM_RESTAURANT = "P1"          # Order handoff arrives from this process
FLEET_NAME = "Fleet Runner A"

LISTEN_HOST = "0.0.0.0"             # bind on all interfaces (Node 3 - slave2)
LISTEN_PORT = 5003

NODES = {
    "P0": {"host": "127.0.0.1", "port": 5000},
    "P1": {"host": "127.0.0.1", "port": 5001},
    "P2": {"host": "127.0.0.1", "port": 5002},
    "P3": {"host": "127.0.0.1", "port": 5003},
    "P4": {"host": "127.0.0.1", "port": 5004},
}

vc = VectorClock(process_id=PROCESS_ID, num_processes=5)

# ----------------------------------------------------------------------
# Local mutable state (guarded by locks since it's touched from multiple
# connection-handler threads)
# ----------------------------------------------------------------------
state_lock = threading.Lock()
order_status = "WAITING_FOR_ORDER"
current_order_label = None

snap_lock = threading.Lock()
recorded_snapshots = {}  # snapshot_id -> True once this process has recorded

def log_send(target, label, clock):
    print(f"{Fore.GREEN}[SEND] {PROCESS_NAME} → {target} | {label} | Clock: {clock}{Style.RESET_ALL}")


def log_recv(source, label, clock):
    print(f"{Fore.CYAN}[RECV] {PROCESS_NAME} ← {source} | {label} | Clock: {clock}{Style.RESET_ALL}")


def log_snapshot(label, clock):
    print(f"{Fore.MAGENTA}[SNAPSHOT] {PROCESS_NAME} | {label} | Clock: {clock}{Style.RESET_ALL}")


def log_error(msg):
    print(f"{Fore.RED}[ERROR] {PROCESS_NAME} | {msg}{Style.RESET_ALL}")


# ----------------------------------------------------------------------
# Networking
# ----------------------------------------------------------------------
def send_message(target_name, msg_type, data, clock):
    """Open a short-lived TCP connection, send one newline-delimited JSON
    message, then close. Simple request/response style suitable for the
    assignment's message volume."""
    node = NODES[target_name]
    message = {"type": msg_type, "data": data, "clock": clock, "from": PROCESS_NAME}
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(10)
            s.connect((node["host"], node["port"]))
            s.sendall((json.dumps(message) + "\n").encode("utf-8"))
    except Exception as e:
        log_error(f"failed to send {msg_type} to {target_name}: {e}")


def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((LISTEN_HOST, LISTEN_PORT))
    server.listen(20)
    print(f"{Fore.BLUE}{PROCESS_NAME} ({FLEET_NAME}) listening on port {LISTEN_PORT}...{Style.RESET_ALL}")
    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_connection, args=(conn,), daemon=True).start()


def handle_connection(conn):
    with conn:
        buffer = b""
        while True:
            try:
                chunk = conn.recv(4096)
            except ConnectionResetError:
                break
            if not chunk:
                break
            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                if not line.strip():
                    continue
                try:
                    msg = json.loads(line.decode("utf-8"))
                except json.JSONDecodeError:
                    log_error(f"received malformed JSON: {line!r}")
                    continue
                dispatch(msg)


def dispatch(msg):
    mtype = msg.get("type")
    if mtype == "DELIVERY":
        handle_delivery_handoff(msg)
    elif mtype == "MARKER":
        handle_marker(msg)
    else:
        log_error(f"unexpected message type '{mtype}' from {msg.get('from')}")


# ----------------------------------------------------------------------
# Order handling
# ----------------------------------------------------------------------
def handle_delivery_handoff(msg):
    """Triggered when P1 hands off a cooked order to this delivery partner."""
    global order_status, current_order_label

    order_label = msg.get("data", "Order")
    source = msg.get("from", "?")

    clock = vc.receive_event(msg.get("clock", vc.get_clock()))
    log_recv(source, f"{order_label} handed off for delivery", clock)

    with state_lock:
        order_status = "RECEIVED_FROM_RESTAURANT"
        current_order_label = order_label

    threading.Thread(target=process_delivery, args=(order_label, source), daemon=True).start()


def process_delivery(order_label, restaurant):
    """Order picked up -> In transit -> Order delivered, then notify P0."""
    global order_status

    with state_lock:
        order_status = "PICKED_UP"
    vc.internal_event(f"{order_label} picked up from {restaurant}")
    time.sleep(1)

    with state_lock:
        order_status = "IN_TRANSIT"
    vc.internal_event(f"{order_label} in transit ({FLEET_NAME})")
    time.sleep(1)

    with state_lock:
        order_status = "DELIVERED"
    vc.internal_event(f"{order_label} delivered to customer")
    time.sleep(0.5)

    clock = vc.send_event()
    label = f"{order_label} delivered by {PROCESS_NAME} ({FLEET_NAME})"
    log_send("P0", label, clock)
    send_message("P0", "DELIVERY", label, clock)


# ----------------------------------------------------------------------
# Chandy-Lamport snapshot participation
# ----------------------------------------------------------------------
def handle_marker(msg):
    """P1 forwards the MARKER it received from P0 downstream to P3.
    P3 records its local state (first marker) and reports STATE back to P0.
    P3 has no further downstream process, so the marker is not forwarded
    any further."""
    source = msg.get("from", "?")
    data = msg.get("data")
    snapshot_id = data.get("snapshot_id") if isinstance(data, dict) else data

    clock = vc.receive_event(msg.get("clock", vc.get_clock()))
    log_recv(source, f"MARKER for {snapshot_id}", clock)

    with snap_lock:
        already_recorded = snapshot_id in recorded_snapshots
        if not already_recorded:
            recorded_snapshots[snapshot_id] = True

    if already_recorded:
        # A duplicate marker on an already-recorded snapshot just means the
        # incoming channel is now empty; nothing new to record or send.
        log_snapshot(f"{snapshot_id} channel {source}->{PROCESS_NAME} closed (duplicate marker)", vc.get_clock())
        return

    with state_lock:
        snapshot_state = {
            "process": PROCESS_NAME,
            "role": FLEET_NAME,
            "snapshot_id": snapshot_id,
            "vector_clock": vc.get_clock(),
            "order_status": order_status,
            "current_order": current_order_label,
            "incoming_channel_state": f"{source}->{PROCESS_NAME}: recorded empty on marker receipt",
        }

    log_snapshot(f"{snapshot_id} local state recorded (order_status={snapshot_state['order_status']})",
                 snapshot_state["vector_clock"])

    state_clock = vc.send_event()
    log_send("P0", f"STATE for {snapshot_id}", state_clock)
    send_message("P0", "STATE", snapshot_state, state_clock)


# ----------------------------------------------------------------------
if __name__ == "__main__":
    print(f"{Fore.BLUE}=== {PROCESS_NAME} : Delivery Partner 1 ({FLEET_NAME}) starting up ==={Style.RESET_ALL}")
    start_server()