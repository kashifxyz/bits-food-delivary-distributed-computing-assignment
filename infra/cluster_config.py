"""
cluster_config.py — Cluster topology resolution.
Owner: Sohail (Infrastructure)

Every process (p0.py .. p4.py) imports this instead of hardcoding IPs.
The topology lives in cluster.json, generated per machine by setup_cluster.py.

Typical use:
    from cluster_config import get_my_bind_address, get_target_address

    server.bind(get_my_bind_address(1))          # -> ("0.0.0.0", 5001)
    ip, port = get_target_address(3)             # -> ("10.0.0.17", 5003)
"""

import json
import os
import socket
import sys

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cluster.json")

NUM_PROCESSES = 5

# Static part of the topology. Only the IPs vary per lab session; the
# process -> node -> port mapping is fixed by the team's design.
PROCESS_LAYOUT = {
    0: {"name": "P0 Central Order Processor", "short": "P0", "node": "node1", "port": 5005},
    1: {"name": "P1 Restaurant A (Pizza Palace)", "short": "P1", "node": "node2", "port": 5001},
    2: {"name": "P2 Restaurant B (Burger Hub)", "short": "P2", "node": "node2", "port": 5002},
    3: {"name": "P3 Delivery Partner 1 (Fleet Runner A)", "short": "P3", "node": "node3", "port": 5003},
    4: {"name": "P4 Delivery Partner 2 (Fleet Runner B)", "short": "P4", "node": "node3", "port": 5004},
}

NODE_ROLES = {
    "node1": "Master — Central Coordinator",
    "node2": "Slave 1 — Restaurants",
    "node3": "Slave 2 — Delivery Partners",
}

_cache = None


class ClusterConfigError(RuntimeError):
    """Raised when the cluster topology cannot be resolved."""


def load_cluster(force_reload=False):
    """Load and cache cluster.json. Exits with a clear message if missing."""
    global _cache
    if _cache is not None and not force_reload:
        return _cache

    if not os.path.exists(CONFIG_FILE):
        sys.stderr.write(
            "\n[ERROR] cluster.json not found in {}\n"
            "        This machine has not been initialised.\n\n"
            "        Run:  python3 setup_cluster.py <NODE1_IP> <NODE2_IP> <NODE3_IP>\n\n"
            .format(os.path.dirname(CONFIG_FILE))
        )
        sys.exit(1)

    try:
        with open(CONFIG_FILE, "r") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        raise ClusterConfigError("cluster.json is unreadable or malformed: {}".format(exc))

    if "nodes" not in data:
        raise ClusterConfigError("cluster.json is missing the 'nodes' section. Re-run setup_cluster.py.")

    _cache = data
    return _cache


def _require_pid(process_id):
    try:
        pid = int(process_id)
    except (TypeError, ValueError):
        raise ValueError("process_id must be an integer 0-4, got {!r}".format(process_id))
    if pid not in PROCESS_LAYOUT:
        raise ValueError("Invalid process_id {}. Valid IDs are 0, 1, 2, 3, 4.".format(pid))
    return pid


def get_process_info(process_id):
    """Return a dict with name, short, node, port and resolved ip for a process."""
    pid = _require_pid(process_id)
    data = load_cluster()
    layout = PROCESS_LAYOUT[pid]
    node_key = layout["node"]

    ip = data["nodes"].get(node_key)
    if not ip:
        raise ClusterConfigError(
            "No IP recorded for {} in cluster.json. Re-run setup_cluster.py.".format(node_key)
        )

    info = dict(layout)
    info["ip"] = ip
    info["process_id"] = pid
    info["node_role"] = NODE_ROLES[node_key]
    return info


def get_target_address(process_id):
    """(ip, port) for connecting OUT to a remote process."""
    info = get_process_info(process_id)
    return (info["ip"], info["port"])


def get_my_bind_address(process_id):
    """("0.0.0.0", port) so the listener accepts traffic from other VMs.

    Binding to 127.0.0.1 would make the process unreachable from the other
    nodes, which is the most common mistake in this setup.
    """
    info = get_process_info(process_id)
    return ("0.0.0.0", info["port"])


def get_process_name(process_id, short=False):
    info = PROCESS_LAYOUT[_require_pid(process_id)]
    return info["short"] if short else info["name"]


def all_process_ids():
    return sorted(PROCESS_LAYOUT.keys())


def peers_of(process_id):
    """Every process id other than this one."""
    pid = _require_pid(process_id)
    return [p for p in all_process_ids() if p != pid]


def get_my_node():
    """Which node this machine is ('node1'/'node2'/'node3'), or None if unknown."""
    data = load_cluster()
    return data.get("my_node")


def processes_on_node(node_key):
    """Process ids hosted on a given node key."""
    return [pid for pid, info in sorted(PROCESS_LAYOUT.items()) if info["node"] == node_key]


def local_ips():
    """Best-effort list of this machine's own IPv4 addresses."""
    found = set()
    try:
        hostname = socket.gethostname()
        for res in socket.getaddrinfo(hostname, None, socket.AF_INET):
            found.add(res[4][0])
    except socket.gaierror:
        pass
    # Also catch the address used for outbound routing.
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        found.add(probe.getsockname()[0])
    except OSError:
        pass
    finally:
        probe.close()
    found.discard("127.0.0.1")
    return sorted(found)


def describe():
    """Human-readable topology summary, used by setup and verify scripts."""
    data = load_cluster()
    my_node = data.get("my_node")
    lines = ["", "Cluster topology (from cluster.json)", "-" * 62]
    for node_key in ("node1", "node2", "node3"):
        marker = "  <-- THIS MACHINE" if node_key == my_node else ""
        lines.append("{}  {:<15}  {}{}".format(
            node_key, data["nodes"].get(node_key, "?"), NODE_ROLES[node_key], marker))
        for pid in processes_on_node(node_key):
            info = PROCESS_LAYOUT[pid]
            lines.append("           port {}   {}".format(info["port"], info["name"]))
    lines.append("-" * 62)
    if not my_node:
        lines.append("This machine did not match any configured node IP.")
        lines.append("That is fine if you are running everything on one host for testing.")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    print(describe())
