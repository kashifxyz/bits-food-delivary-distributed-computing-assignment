"""
P2 — Burger Hub (Restaurant B)

Event flow per order:
  RECEIVE  ORDER from P0
  INTERNAL "Order confirmed"
  INTERNAL "Preparing food"
  INTERNAL "Food ready for pickup"
  SEND     DELIVERY -> P4 (Fleet Runner B)

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

from vector_clock import VectorClock
from snapshot import ChandyLamportSnapshot

PROCESS_NAME = "P2"
PROCESS_ID = 2
NUM_PROCESSES = 5
RESTAURANT_NAME = "Burger Hub"
DELIVERY_PARTNER = "P4"
COORDINATOR = "P0"

CONFIG_PATH = "config/hosts.cfg"


def load_ports(path=CONFIG_PATH):
    """Reads the [ports] section of hosts.cfg -> {'P0': 5000, 'P1': 5001, ...}"""
    c = configparser.ConfigParser()
    c.read(path)
    return {k.split("_")[0].upper(): int(v) for k, v in c["ports"].items()}


PORTS = load_ports()

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
# Networking — same one-shot-socket convention as snapshot.py so P1 talks
# the same protocol it already uses for MARKER/STATE.
# NOTE: hardcodes "localhost" like snapshot.py does today. This only works
# for single-node testing; needs a host lookup once NODE*_IP are filled in
# and snapshot.py's send_message is updated to accept a host.
# ---------------------------------------------------------------------

def send_message(target_name, message):
    port = PORTS[target_name]
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("localhost", port))
        sock.send(json.dumps(message).encode())
        sock.close()
    except Exception as e:
        print(f"[{PROCESS_NAME}] send error to {target_name}: {e}")


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
    if mtype == "ORDER":
        threading.Thread(target=handle_order, args=(msg,), daemon=True).start()
    elif mtype == "MARKER":
        snapshot.handle_marker(msg, PORTS)
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
    print(f"[{PROCESS_NAME} {RESTAURANT_NAME}] listening on port {port} ...")
    while True:
        time.sleep(1)
