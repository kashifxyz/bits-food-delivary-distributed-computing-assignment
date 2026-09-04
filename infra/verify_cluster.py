"""
verify_cluster.py — Network diagnostics for the three-node cluster.
Owner: Sohail (Infrastructure)

Run this BEFORE the demo. It proves every port is bound and reachable, so a
failure during the presentation is a code bug, not a firewall surprise.

RECOMMENDED FLOW (two commands, checks all five endpoints at once)

    On Node 2 and Node 3:   python3 verify_cluster.py agent
    On Node 1:              python3 verify_cluster.py check

  'agent' listens on every port that belongs to that machine and answers
  health probes. Leave it running, then Ctrl-C when the check is done.
  'check' probes all five process endpoints and prints a pass/fail table.

SINGLE-PORT MODE (kept for quick manual checks)

    python3 verify_cluster.py listen 5001
    python3 verify_cluster.py ping 10.0.0.16 5001
"""

import socket
import sys
import threading
import time

from cluster_config import (
    PROCESS_LAYOUT,
    all_process_ids,
    describe,
    get_my_node,
    get_process_info,
    load_cluster,
    processes_on_node,
)

PROBE = b"DC-GROUP2-HEALTHCHECK"
ACK = b"ACK-PORT-OPEN"
TICK = "[ok]"
CROSS = "[--]"


# ---------------------------------------------------------------------------
# agent — listen on every port this machine owns
# ---------------------------------------------------------------------------

def _port_agent(port, label, stop_event):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        srv.bind(("0.0.0.0", port))
    except OSError as exc:
        print("{} port {:<5} {:<40} BIND FAILED: {}".format(CROSS, port, label, exc))
        return
    srv.listen(4)
    srv.settimeout(0.5)
    print("{} port {:<5} {:<40} listening".format(TICK, port, label))

    while not stop_event.is_set():
        try:
            conn, addr = srv.accept()
        except socket.timeout:
            continue
        except OSError:
            break
        try:
            conn.settimeout(5)
            data = conn.recv(64)
            if data.startswith(PROBE):
                conn.sendall(ACK)
                print("     probe on port {} from {}".format(port, addr[0]))
        except OSError:
            pass
        finally:
            conn.close()
    srv.close()


def run_agent(node_key=None):
    node_key = node_key or get_my_node()
    if node_key is None:
        sys.exit(
            "[ERROR] Could not tell which node this machine is.\n"
            "        Re-run setup_cluster.py, or pass the node explicitly:\n"
            "          python3 verify_cluster.py agent node2"
        )

    pids = processes_on_node(node_key)
    if not pids:
        sys.exit("[ERROR] No processes are assigned to {}.".format(node_key))

    print(describe())
    print("Health-check agent for {} — Ctrl-C to stop\n".format(node_key))

    stop_event = threading.Event()
    threads = []
    for pid in pids:
        info = PROCESS_LAYOUT[pid]
        thread = threading.Thread(
            target=_port_agent, args=(info["port"], info["name"], stop_event), daemon=True)
        thread.start()
        threads.append(thread)

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopping agent.")
        stop_event.set()
        for thread in threads:
            thread.join(timeout=2)


# ---------------------------------------------------------------------------
# check — probe every process endpoint in the cluster
# ---------------------------------------------------------------------------

def probe(ip, port, timeout=3.0):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((ip, port))
        sock.sendall(PROBE)
        reply = sock.recv(64)
        if reply.startswith(ACK):
            return True, "reachable"
        return True, "connected (no ACK — real process may be running here)"
    except socket.timeout:
        return False, "timed out (firewall or wrong IP)"
    except ConnectionRefusedError:
        return False, "connection refused (nothing listening)"
    except OSError as exc:
        return False, str(exc)
    finally:
        sock.close()


def run_check():
    load_cluster()
    print(describe())
    print("Probing all five process endpoints\n")
    print("  {:<4} {:<38} {:<16} {:<6} {}".format("PID", "PROCESS", "IP", "PORT", "RESULT"))
    print("  " + "-" * 92)

    failures = []
    for pid in all_process_ids():
        info = get_process_info(pid)
        ok, detail = probe(info["ip"], info["port"])
        print("  {:<4} {:<38} {:<16} {:<6} {} {}".format(
            "P{}".format(pid), info["name"], info["ip"], info["port"],
            TICK if ok else CROSS, detail))
        if not ok:
            failures.append((pid, info, detail))

    print()
    if not failures:
        print("All five endpoints reachable. The cluster is ready.")
        return 0

    print("{} of 5 endpoints unreachable.\n".format(len(failures)))
    print("Checklist:")
    print("  1. Is the agent running on the node that hosts the failed process?")
    print("       python3 verify_cluster.py agent")
    print("  2. Did you run setup_cluster.py with the SAME IP order on every node?")
    print("  3. Are ports 5000-5004 open?")
    print("       sudo ufw status          (and: sudo ufw allow 5000:5004/tcp)")
    print("       sudo iptables -L -n | grep -E '5000|5004'")
    print("  4. Can the nodes see each other at all?")
    print("       ping -c 3 <other_node_ip>")
    return 1


# ---------------------------------------------------------------------------
# single-port modes
# ---------------------------------------------------------------------------

def run_listen(port):
    stop = threading.Event()
    try:
        _port_agent(port, "manual listener", stop)
    except KeyboardInterrupt:
        stop.set()


def run_ping(ip, port):
    ok, detail = probe(ip, port)
    print("{} {}:{} — {}".format(TICK if ok else CROSS, ip, port, detail))
    return 0 if ok else 1


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    mode = sys.argv[1].lower()

    if mode == "agent":
        run_agent(sys.argv[2] if len(sys.argv) > 2 else None)
        return 0
    if mode == "check":
        return run_check()
    if mode == "listen" and len(sys.argv) == 3:
        run_listen(int(sys.argv[2]))
        return 0
    if mode == "ping" and len(sys.argv) == 4:
        return run_ping(sys.argv[2], int(sys.argv[3]))

    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
