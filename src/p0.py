"""
p0.py

P0 — Central Order Processor & Coordinator
Author: Shaik Baleeghuddin Kashif

Responsibilities:
1. Coordinates the distributed food delivery platform.
2. Maintains Vector Clock for P0 (N=5 processes: P0, P1, P2, P3, P4).
3. Dispatches customer ORDER messages to P1 (Pizza Palace) and P2 (Burger Hub).
4. Initiates Chandy-Lamport Global Snapshots (e.g. SNAPSHOT_1 and SNAPSHOT_2)
   by sending MARKER messages downstream to outgoing neighbors (P1, P2).
5. Listens on Port 5005 (with fallback) to collect STATE messages from all 5 processes.
6. Evaluates and displays captured Global Snapshot states, performs causal
   consistency checks, and analyzes concurrent events.

Wire format matches snapshot.py's send_message(): JSON over TCP, newline-compatible.
"""

import argparse
import configparser
import json
import os
import signal
import socket
import sys
import threading
import time
from colorama import Fore, Style, init

from vector_clock import VectorClock
from snapshot import ChandyLamportSnapshot

init(autoreset=True)

PROCESS_NAME = "P0"
PROCESS_ID = 0
NUM_PROCESSES = 5
COORDINATOR = "P0"
OUTGOING_NEIGHBORS = ["P1", "P2"]

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "hosts.cfg")

running = True
server_socket = None


# ---------------------------------------------------------------------
# Configuration Loading
# ---------------------------------------------------------------------

def load_ports(path=CONFIG_PATH):
    """Reads the [ports] section of hosts.cfg -> {'P0': 5005, 'P1': 5001, ...}"""
    c = configparser.ConfigParser()
    if os.path.exists(path):
        c.read(path)
        if "ports" in c:
            return {k.split("_")[0].upper(): int(v) for k, v in c["ports"].items()}
    return {"P0": 5005, "P1": 5001, "P2": 5002, "P3": 5003, "P4": 5004}


def load_hosts(path=CONFIG_PATH):
    """Reads [process_hosts] & [nodes] -> {'P0': 'localhost', 'P1': '...', ...}"""
    c = configparser.ConfigParser()
    hosts = {}
    if os.path.exists(path):
        c.read(path)
        node_ips = {}
        if "nodes" in c:
            for k, v in c["nodes"].items():
                node_ips[k.upper()] = v.strip()
        if "process_hosts" in c:
            for k, v in c["process_hosts"].items():
                p_name = k.split("_")[0].upper()
                node_ref = v.strip().upper()
                resolved_ip = node_ips.get(node_ref, "")
                hosts[p_name] = resolved_ip if resolved_ip else "localhost"
    for p in ["P0", "P1", "P2", "P3", "P4"]:
        if p not in hosts or not hosts[p]:
            hosts[p] = "localhost"
    return hosts


PORTS = load_ports()
HOSTS = load_hosts()

# ---------------------------------------------------------------------
# Global State & Vector Clock
# ---------------------------------------------------------------------

vc = VectorClock(process_id=PROCESS_ID, num_processes=NUM_PROCESSES)

snapshot = ChandyLamportSnapshot(
    process_name=PROCESS_NAME,
    process_id=PROCESS_ID,
    vector_clock=vc,
    outgoing_neighbors=OUTGOING_NEIGHBORS,
    coordinator=COORDINATOR,
)

state_store = {}
orders_store = {}
order_counter = 100


# ---------------------------------------------------------------------
# Graceful Shutdown
# ---------------------------------------------------------------------

def shutdown_handler(signum=None, frame=None):
    global running, server_socket
    if not running:
        return
    running = False
    print(f"\n{Fore.YELLOW}[P0] Shutting down gracefully... Cleaning up sockets & state.{Style.RESET_ALL}")
    if server_socket:
        try:
            server_socket.close()
        except Exception:
            pass
    print(f"{Fore.GREEN}[P0] Shutdown complete. Goodbye!{Style.RESET_ALL}")
    sys.exit(0)


signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)


# ---------------------------------------------------------------------
# Network Communication
# ---------------------------------------------------------------------

def send_message(target_name, message):
    """Sends a JSON message over a one-shot TCP connection to the target process."""
    port = PORTS.get(target_name)
    host = HOSTS.get(target_name, "localhost")
    if not port:
        print(f"{Fore.RED}[{PROCESS_NAME}] Unknown target process: {target_name}{Style.RESET_ALL}")
        return False
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        sock.connect((host, port))
        sock.sendall((json.dumps(message) + "\n").encode())
        sock.close()
        return True
    except Exception as e:
        print(f"{Fore.RED}[{PROCESS_NAME}] Send error to {target_name} ({host}:{port}): {e}{Style.RESET_ALL}")
        return False


# ---------------------------------------------------------------------
# Order Dispatching & Snapshot Initiation
# ---------------------------------------------------------------------

def send_order(target_restaurant: str, item_name: str, order_id: int = None) -> int:
    global order_counter
    if order_id is None:
        order_counter += 1
        order_id = order_counter

    vc.internal_event(f"Created Customer Order #{order_id} for {item_name}")

    orders_store[order_id] = {
        "order_id": order_id,
        "restaurant": target_restaurant,
        "item": item_name,
        "status": "DISPATCHED",
        "created_clock": vc.get_clock()
    }

    order_msg = {
        "type": "ORDER",
        "from": PROCESS_NAME,
        "to": target_restaurant,
        "payload": {
            "order_id": order_id,
            "item": item_name
        },
        "clock": vc.send_event()
    }

    print(
        f"{Fore.GREEN}[P0 Central Processor] DISPATCH ORDER #{order_id} ({item_name}) → {target_restaurant} | "
        f"Clock: {order_msg['clock']}{Style.RESET_ALL}"
    )

    send_message(target_restaurant, order_msg)
    return order_id


def trigger_snapshot(snapshot_id: str):
    print(f"\n{Fore.MAGENTA}{'='*60}")
    print(f"[SNAPSHOT INITIATION] P0 triggering {snapshot_id}")
    print(f"{'='*60}{Style.RESET_ALL}")

    snapshot.initiate_snapshot(snapshot_id, PORTS, HOSTS)

    state_store.setdefault(snapshot_id, {})
    state_store[snapshot_id][PROCESS_NAME] = {
        "process": PROCESS_NAME,
        "vector_clock": vc.get_clock(),
        "local_state": {
            "role": "Central Order Processor",
            "active_orders": list(orders_store.values()),
            "total_orders": len(orders_store)
        }
    }


def check_snapshot_consistency(snapshot_id: str):
    snaps = state_store.get(snapshot_id, {})
    print(f"\n{Fore.CYAN}--- Global Snapshot Report: {snapshot_id} ---{Style.RESET_ALL}")
    print(f"{'Process':<10} {'Recorded Vector Clock':<25} {'Local State Summary'}")
    print(f"{'-'*65}")
    for p_name in sorted([k for k in snaps.keys() if not k.startswith("_")]):
        p_data = snaps[p_name]
        clock_val = p_data.get("vector_clock", [])
        clock_str = str(clock_val)
        local_st = p_data.get("local_state", "")
        if isinstance(local_st, dict):
            local_st = f"Active Orders: {len(local_st.get('active_orders', []))}"
        print(f"{p_name:<10} {clock_str:<25} {str(local_st)[:30]}")

    inconsistencies = []
    p_names = [k for k in snaps.keys() if not k.startswith("_")]
    for i in range(len(p_names)):
        for j in range(i + 1, len(p_names)):
            p_a, p_b = p_names[i], p_names[j]
            c_a = snaps[p_a].get("vector_clock", [])
            c_b = snaps[p_b].get("vector_clock", [])
            if len(c_a) == NUM_PROCESSES and len(c_b) == NUM_PROCESSES:
                idx_a = int(p_a.replace("P", ""))
                idx_b = int(p_b.replace("P", ""))
                if c_a[idx_b] > c_b[idx_b]:
                    inconsistencies.append(
                        f"{p_a}'s recorded clock ({c_a}) observes events at {p_b} beyond {p_b}'s snapshot clock ({c_b})"
                    )

    if not inconsistencies:
        print(f"\n{Fore.GREEN}✓ Global Snapshot {snapshot_id} is CAUSALLY CONSISTENT! (No orphan or future dependencies){Style.RESET_ALL}\n")
    else:
        print(f"\n{Fore.RED}✗ Inconsistencies detected in {snapshot_id}:{Style.RESET_ALL}")
        for inc in inconsistencies:
            print(f"  - {inc}")


def analyze_concurrency(proc_a="P1", proc_b="P2", snapshot_id=None):
    if snapshot_id and snapshot_id in state_store:
        clock_a = state_store[snapshot_id].get(proc_a, {}).get("vector_clock")
        clock_b = state_store[snapshot_id].get(proc_b, {}).get("vector_clock")
    else:
        clock_a = None
        clock_b = None

    if clock_a and clock_b:
        any_less = any(clock_a[i] < clock_b[i] for i in range(NUM_PROCESSES))
        any_greater = any(clock_a[i] > clock_b[i] for i in range(NUM_PROCESSES))
        concurrent = any_less and any_greater
        print(f"\n{Fore.YELLOW}[CONCURRENCY CHECK] {proc_a} Clock: {clock_a} vs {proc_b} Clock: {clock_b}")
        if concurrent:
            print(f"{Fore.GREEN}✓ {proc_a} and {proc_b} events are CONCURRENT (clock_a || clock_b){Style.RESET_ALL}\n")
        else:
            print(f"{Fore.CYAN}ℹ {proc_a} and {proc_b} are causally ordered or same.{Style.RESET_ALL}\n")


# ---------------------------------------------------------------------
# Incoming Message Dispatching & Server Listener
# ---------------------------------------------------------------------

def dispatch(msg):
    mtype = msg.get("type")
    sender = msg.get("from", "UNKNOWN")

    if mtype == "STATE":
        data = msg.get("data")
        snapshot_id = msg.get("snapshot_id") or (data.get("snapshot_id") if isinstance(data, dict) else data) or "SNAPSHOT_1"
        if "clock" in msg:
            vc.receive_event(msg["clock"])
        
        snapshot.handle_state(msg, state_store)
        
        collected_procs = [k for k in state_store.get(snapshot_id, {}).keys() if not k.startswith("_")]
        collected_count = len(collected_procs)
        print(
            f"{Fore.CYAN}[STATE RECEIVED] {sender} → P0 for {snapshot_id} | "
            f"Progress: {collected_count}/{NUM_PROCESSES} processes recorded ({', '.join(sorted(collected_procs))}){Style.RESET_ALL}"
        )

        if collected_count == NUM_PROCESSES:
            print(f"{Fore.GREEN}★ All {NUM_PROCESSES} process states collected for {snapshot_id}!{Style.RESET_ALL}")
            check_snapshot_consistency(snapshot_id)

    elif mtype in ["DELIVERY", "DELIVERY_COMPLETE", "ORDER_DELIVERED"]:
        if "clock" in msg:
            vc.receive_event(msg["clock"])
        data_text = str(msg.get("data") or msg.get("payload") or "")
        vc.internal_event(f"Delivery confirmation received from {sender}: {data_text}")
        print(f"{Fore.GREEN}[DELIVERY COMPLETE] Order fulfilled via {sender}: {data_text}{Style.RESET_ALL}")

    elif mtype == "MARKER":
        snapshot.handle_marker(msg, PORTS, HOSTS)

    else:
        if "clock" in msg:
            vc.receive_event(msg["clock"])
        print(f"[{PROCESS_NAME}] Received message of type '{mtype}' from {sender}")


def handle_conn(conn):
    data = b""
    with conn:
        while running:
            try:
                chunk = conn.recv(4096)
            except (ConnectionResetError, OSError):
                break
            if not chunk:
                break
            data += chunk
            while b"\n" in data:
                line, data = data.split(b"\n", 1)
                if not line.strip():
                    continue
                try:
                    msg = json.loads(line.decode())
                    dispatch(msg)
                except json.JSONDecodeError:
                    pass
        if data.strip():
            try:
                msg = json.loads(data.decode())
                dispatch(msg)
            except json.JSONDecodeError:
                pass


def start_listener(port, auto_fallback=True):
    global server_socket
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    current_port = port
    try:
        server.bind(("0.0.0.0", current_port))
    except OSError as e:
        if e.errno == 48 and auto_fallback and current_port == 5000:
            fallback_port = 5005
            print(
                f"{Fore.YELLOW}[P0 Warning] Port 5000 is reserved by macOS AirPlay Receiver.\n"
                f"Automatically falling back to port {fallback_port}...{Style.RESET_ALL}"
            )
            current_port = fallback_port
            PORTS["P0"] = fallback_port
            server.bind(("0.0.0.0", current_port))
        else:
            raise e

    server.listen(16)
    server_socket = server

    def accept_loop():
        while running:
            try:
                conn, _addr = server.accept()
            except OSError:
                break
            threading.Thread(target=handle_conn, args=(conn,), daemon=True).start()

    threading.Thread(target=accept_loop, daemon=True).start()
    return server, current_port


# ---------------------------------------------------------------------
# Full Automated Demonstration Flow
# ---------------------------------------------------------------------

def run_automated_flow():
    """
    Executes the complete scenario across all 5 processes:
    1. P0 dispatches Order #101 to P1 (Pizza Palace).
    2. P0 dispatches Order #102 to P2 (Burger Hub).
    3. Triggers SNAPSHOT_1 while orders are being prepared / processed in parallel.
    4. Waits for downstream food prep & delivery by P3 and P4.
    5. Triggers SNAPSHOT_2 after completion to capture final global cut.
    """
    print(f"\n{Fore.MAGENTA}=======================================================")
    print(f"  STARTING P0 AUTOMATED DISTRIBUTED WORKFLOW")
    print(f"======================================================={Style.RESET_ALL}\n")
    time.sleep(1.0)

    # Step 1: Dispatch Order 101 to P1
    print(f"{Fore.YELLOW}[STEP 1] Dispatching Order #101 to P1 (Pizza Palace)...{Style.RESET_ALL}")
    send_order("P1", "Margherita Pizza", order_id=101)
    time.sleep(0.8)

    # Step 2: Dispatch Order 102 to P2
    print(f"\n{Fore.YELLOW}[STEP 2] Dispatching Order #102 to P2 (Burger Hub)...{Style.RESET_ALL}")
    send_order("P2", "Double Cheeseburger", order_id=102)
    time.sleep(1.0)

    # Step 3: Trigger Snapshot 1 (mid-execution cut)
    print(f"\n{Fore.YELLOW}[STEP 3] Triggering SNAPSHOT_1 during concurrent order processing...{Style.RESET_ALL}")
    trigger_snapshot("SNAPSHOT_1")
    time.sleep(4.0)

    # Step 4: Trigger Snapshot 2 (post-delivery cut)
    print(f"\n{Fore.YELLOW}[STEP 4] Triggering SNAPSHOT_2 post order workflow...{Style.RESET_ALL}")
    trigger_snapshot("SNAPSHOT_2")
    time.sleep(4.0)

    print(f"\n{Fore.MAGENTA}=======================================================")
    print(f"  AUTOMATED WORKFLOW COMPLETED — P0 READY")
    print(f"======================================================={Style.RESET_ALL}\n")


# ---------------------------------------------------------------------
# Interactive CLI Menu
# ---------------------------------------------------------------------

def interactive_menu():
    while running:
        try:
            print(f"\n{Fore.CYAN}=== P0 Central Order Processor Menu ==={Style.RESET_ALL}")
            print("  1. Send Order to P1 (Pizza Palace)")
            print("  2. Send Order to P2 (Burger Hub)")
            print("  3. Trigger Chandy-Lamport Snapshot (e.g. SNAPSHOT_1)")
            print("  4. View Collected Snapshots & Verify Consistency")
            print("  5. View Current P0 Vector Clock")
            print("  6. Run Full Automated Demo Scenario (Orders + 2 Snapshots)")
            print("  0. Exit")
            choice = input("Select an option [0-6]: ").strip()

            if choice == "1":
                item = input("Enter Pizza item [default: Margherita Pizza]: ").strip() or "Margherita Pizza"
                send_order("P1", item)
            elif choice == "2":
                item = input("Enter Burger item [default: Double Cheeseburger]: ").strip() or "Double Cheeseburger"
                send_order("P2", item)
            elif choice == "3":
                snap_id = input("Enter Snapshot ID [default: SNAPSHOT_1]: ").strip() or "SNAPSHOT_1"
                trigger_snapshot(snap_id)
            elif choice == "4":
                if not state_store:
                    print(f"{Fore.YELLOW}No snapshots recorded yet.{Style.RESET_ALL}")
                else:
                    for s_id in state_store.keys():
                        check_snapshot_consistency(s_id)
            elif choice == "5":
                print(f"\n{Fore.GREEN}Current P0 Vector Clock: {vc.get_clock()}{Style.RESET_ALL}\n")
            elif choice == "6":
                run_automated_flow()
            elif choice == "0":
                shutdown_handler()
                break
            else:
                print("Invalid choice, please try again.")
        except (KeyboardInterrupt, EOFError):
            shutdown_handler()
            break


# ---------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="P0 — Central Order Processor & Coordinator")
    parser.add_argument("--port", type=int, help="Override P0 listening port")
    parser.add_argument("--auto", action="store_true", help="Run automated order and snapshot flow on start")
    parser.add_argument("--order", choices=["P1", "P2"], help="Send single order to target restaurant")
    parser.add_argument("--item", default="Margherita Pizza", help="Item name for single order")
    parser.add_argument("--snapshot", help="Trigger snapshot with specified ID")
    args = parser.parse_args()

    requested_port = args.port or PORTS[PROCESS_NAME]
    server, active_port = start_listener(requested_port, auto_fallback=(args.port is None))

    print(f"\n{Fore.MAGENTA}=======================================================")
    print(f" [{PROCESS_NAME}] Central Order Processor listening on port {active_port}")
    print(f" Hosts: {HOSTS}")
    print(f" Initial Clock: {vc.get_clock()}")
    print(f"======================================================={Style.RESET_ALL}\n")

    try:
        if args.auto:
            time.sleep(1.0)
            run_automated_flow()
        elif args.order:
            send_order(args.order, args.item)
        elif args.snapshot:
            trigger_snapshot(args.snapshot)
        else:
            if sys.stdin.isatty():
                interactive_menu()
            else:
                while running:
                    time.sleep(1)
    except (KeyboardInterrupt, EOFError):
        shutdown_handler()
