"""
P1 — Pizza Palace (Restaurant A)

Event flow per order:
  RECEIVE  ORDER from P0
  INTERNAL "Order confirmed"
  INTERNAL "Preparing food"
  INTERNAL "Food ready for pickup"
  SEND     DELIVERY -> P3 (Fleet Runner A)

Also plugs into Abhirup's ChandyLamportSnapshot for MARKER/STATE handling —
that class does the actual snapshot bookkeeping; this file just routes
incoming MARKER messages into it.

Wire format matches snapshot.py's send_message(): one JSON object per TCP
connection, no newline framing, socket closes right after send.
"""

import json
import socket
import threading
import time
import configparser
import os

from vector_clock import VectorClock
from snapshot import ChandyLamportSnapshot

PROCESS_NAME = "P1"
PROCESS_ID = 1
NUM_PROCESSES = 5
RESTAURANT_NAME = "Pizza Palace"
DELIVERY_PARTNER = "P3"
COORDINATOR = "P0"

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "hosts.cfg")


def load_network_config(path=CONFIG_PATH):
    """Reads [ports], [nodes], and [process_hosts] from hosts.cfg"""
    c = configparser.ConfigParser()
    ports = {"P0": 5000, "P1": 5001, "P2": 5002, "P3": 5003, "P4": 5004}
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

vc = VectorClock(process_id=PROCESS_ID, num_processes=NUM_PROCESSES)
snapshot = ChandyLamportSnapshot(
    process_name=PROCESS_NAME,
    process_id=PROCESS_ID,
    vector_clock=vc,
    outgoing_neighbors=[DELIVERY_PARTNER],
    coordinator=COORDINATOR,
)

state_store = {}  # only really used on P0, kept here just in case


# ---------------------------------------------------------------------
# Networking — resolved host lookup from hosts.cfg with sendall()
# ---------------------------------------------------------------------

def send_message(target_name, message):
    port = PORTS.get(target_name)
    host = HOSTS.get(target_name, "localhost")
    if not port:
        print(f"[{PROCESS_NAME}] unknown target: {target_name}")
        return
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3.0)
        sock.connect((host, port))
        sock.sendall(json.dumps(message).encode())
        sock.close()
    except Exception as e:
        print(f"[{PROCESS_NAME}] send error to {target_name} ({host}:{port}): {e}")


def handle_order(msg):
    vc.receive_event(msg["clock"])
    order_id = msg["payload"]["order_id"]
    item = msg["payload"]["item"]
    print(f"[{PROCESS_NAME} {RESTAURANT_NAME}] RECEIVE ORDER {order_id} from {msg['from']} | Clock: {vc.get_clock()}")

    vc.internal_event("Order confirmed")
    time.sleep(0.5)  # simulate confirmation delay

    vc.internal_event("Preparing food")
    time.sleep(1.0)  # simulate prep time

    vc.internal_event("Food ready for pickup")

    delivery_msg = {
        "type": "DELIVERY",
        "from": PROCESS_NAME,
        "to": DELIVERY_PARTNER,
        "payload": {"order_id": order_id, "item": item, "restaurant": RESTAURANT_NAME},
        "clock": vc.send_event(),
    }
    send_message(DELIVERY_PARTNER, delivery_msg)


def dispatch(msg):
    mtype = msg.get("type")
    sender = msg.get("from", "")
    
    # Record channel messages if snapshot is currently active
    if mtype != "MARKER":
        snapshot.record_channel_message(sender, msg)

    if mtype == "ORDER":
        threading.Thread(target=handle_order, args=(msg,), daemon=True).start()
    elif mtype == "MARKER":
        snapshot.handle_marker(msg, PORTS, HOSTS)
    elif mtype == "STATE":
        snapshot.handle_state(msg, state_store)
    else:
        print(f"[{PROCESS_NAME}] unknown message type: {mtype}")


def handle_conn(conn):
    data = b""
    with conn:
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            data += chunk
    if data:
        try:
            msg = json.loads(data.decode())
            dispatch(msg)
        except json.JSONDecodeError as e:
            print(f"[{PROCESS_NAME}] bad json: {e}")


def start_listener(port):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", port))
    server.listen(16)

    def accept_loop():
        while True:
            try:
                conn, _addr = server.accept()
            except OSError:
                break
            threading.Thread(target=handle_conn, args=(conn,), daemon=True).start()

    threading.Thread(target=accept_loop, daemon=True).start()
    return server


if __name__ == "__main__":
    port = PORTS[PROCESS_NAME]
    start_listener(port)
    print(f"[{PROCESS_NAME} {RESTAURANT_NAME}] listening on port {port} (Host: {HOSTS[PROCESS_NAME]}) ...")
    while True:
        time.sleep(1)
