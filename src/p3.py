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
import configparser
import os
import signal
import sys
from colorama import Fore, Style, init

from vector_clock import VectorClock

init(autoreset=True)

# ----------------------------------------------------------------------
# Identity / config
# ----------------------------------------------------------------------
PROCESS_ID = 3
PROCESS_NAME = "P3"
UPSTREAM_RESTAURANT = "P1"
FLEET_NAME = "Fleet Runner A"

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "hosts.cfg")

running = True
server_socket = None


def shutdown_handler(signum=None, frame=None):
    global running, server_socket
    if not running:
        return
    running = False
    print(f"\n[{PROCESS_NAME}] Shutting down gracefully...")
    if server_socket:
        try:
            server_socket.close()
        except Exception:
            pass
    print(f"[{PROCESS_NAME}] Stopped.")
    sys.exit(0)


signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)


def load_network_config(path=CONFIG_PATH):
    """Reads [ports], [nodes], and [process_hosts] from hosts.cfg"""
    c = configparser.ConfigParser()
    ports = {"P0": 5005, "P1": 5001, "P2": 5002, "P3": 5003, "P4": 5004}
    hosts = {"P0": "localhost", "P1": "localhost", "P2": "localhost", "P3": "localhost", "P4": "localhost"}

    if os.path.exists(path):
        c.read(path)
        if "ports" in c:
            for k, v in c["ports"].items():
                ports[k.split("_")[0].upper()] = int(v)

        node_ips = {}
        if "nodes" in c:
            for k, v in c["nodes"].items():
                node_ips[k.upper()] = v.strip()

        if "process_hosts" in c:
            for k, v in c["process_hosts"].items():
                p_name = k.split("_")[0].upper()
                node_ref = v.strip().upper()
                resolved = node_ips.get(node_ref, "")
                hosts[p_name] = resolved if resolved else "localhost"

    return ports, hosts


PORTS, HOSTS = load_network_config()
LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = PORTS.get(PROCESS_NAME, 5003)

vc = VectorClock(process_id=PROCESS_ID, num_processes=5)

# ----------------------------------------------------------------------
# Local mutable state
# ----------------------------------------------------------------------
state_lock = threading.Lock()
order_status = "WAITING_FOR_ORDER"
current_order_label = None

snap_lock = threading.Lock()
recorded_snapshots = {}

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
    target_host = HOSTS.get(target_name, "localhost")
    target_port = PORTS.get(target_name)
    if not target_port:
        log_error(f"unknown target: {target_name}")
        return
    message = {"type": msg_type, "data": data, "clock": clock, "from": PROCESS_NAME}
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            s.connect((target_host, target_port))
            s.sendall((json.dumps(message) + "\n").encode("utf-8"))
    except Exception as e:
        log_error(f"failed to send {msg_type} to {target_name} ({target_host}:{target_port}): {e}")


def start_server():
    global server_socket
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((LISTEN_HOST, LISTEN_PORT))
    server.listen(20)
    server_socket = server
    print(f"{Fore.BLUE}{PROCESS_NAME} ({FLEET_NAME}) listening on port {LISTEN_PORT} (Host: {HOSTS[PROCESS_NAME]})...{Style.RESET_ALL}")
    
    def accept_loop():
        while running:
            try:
                conn, addr = server.accept()
            except OSError:
                break
            threading.Thread(target=handle_connection, args=(conn,), daemon=True).start()

    threading.Thread(target=accept_loop, daemon=True).start()
    return server


def handle_connection(conn):
    with conn:
        buffer = b""
        while running:
            try:
                chunk = conn.recv(4096)
            except (ConnectionResetError, OSError):
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
        # Handle non-newline framed messages
        if buffer.strip():
            try:
                msg = json.loads(buffer.decode("utf-8"))
                dispatch(msg)
            except json.JSONDecodeError:
                pass


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
    global order_status, current_order_label

    payload = msg.get("payload") or msg.get("data")
    if isinstance(payload, dict):
        order_label = f"Order #{payload.get('order_id', 101)} ({payload.get('item', 'Item')})"
    else:
        order_label = str(payload or "Order")

    source = msg.get("from", "?")

    clock = vc.receive_event(msg.get("clock", vc.get_clock()))
    log_recv(source, f"{order_label} handed off for delivery", clock)

    with state_lock:
        order_status = "RECEIVED_FROM_RESTAURANT"
        current_order_label = order_label

    threading.Thread(target=process_delivery, args=(order_label, source), daemon=True).start()


def process_delivery(order_label, restaurant):
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
    source = msg.get("from", "?")
    data = msg.get("data")
    snapshot_id = msg.get("snapshot_id") or (data.get("snapshot_id") if isinstance(data, dict) else data) or "SNAPSHOT_1"

    clock = vc.receive_event(msg.get("clock", vc.get_clock()))
    log_recv(source, f"MARKER for {snapshot_id}", clock)

    with snap_lock:
        already_recorded = snapshot_id in recorded_snapshots
        if not already_recorded:
            recorded_snapshots[snapshot_id] = True

    if already_recorded:
        log_snapshot(f"{snapshot_id} channel {source}->{PROCESS_NAME} closed (duplicate marker)", vc.get_clock())
        return

    with state_lock:
        snapshot_state = {
            "process": PROCESS_NAME,
            "role": FLEET_NAME,
            "snapshot_id": snapshot_id,
            "vector_clock": vc.get_clock(),
            "local_state": f"Status: {order_status}, Current: {current_order_label}",
            "order_status": order_status,
            "current_order": current_order_label,
            "incoming_channel_state": f"{source}->{PROCESS_NAME}: recorded empty on marker receipt",
        }

    log_snapshot(f"{snapshot_id} local state recorded (order_status={snapshot_state['order_status']})",
                 snapshot_state["vector_clock"])

    state_clock = vc.send_event()
    log_send("P0", f"STATE for {snapshot_id}", state_clock)
    
    state_message_payload = {
        "snapshot_id": snapshot_id,
        "process": PROCESS_NAME,
        "vector_clock": vc.get_clock(),
        "local_state": f"Status: {order_status}, Order: {current_order_label}",
        "data": snapshot_state
    }
    send_message("P0", "STATE", state_message_payload, state_clock)


# ----------------------------------------------------------------------
if __name__ == "__main__":
    print(f"{Fore.BLUE}=== {PROCESS_NAME} : Delivery Partner 1 ({FLEET_NAME}) starting up ==={Style.RESET_ALL}")
    start_server()
    try:
        while running:
            time.sleep(1)
    except (KeyboardInterrupt, EOFError):
        shutdown_handler()
