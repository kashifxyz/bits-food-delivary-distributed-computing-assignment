"""
setup_cluster.py — One-command cluster initialisation.
Owner: Sohail (Infrastructure)

Run this ONCE on each of your three Prayogshala VMs, every time the lab is
re-provisioned (private IPs change when VMs are recreated).

    python3 setup_cluster.py <NODE1_IP> <NODE2_IP> <NODE3_IP>

Order matters and must be identical on all three machines:
    NODE1 = Master        (P0)
    NODE2 = Slave 1       (P1, P2)
    NODE3 = Slave 2       (P3, P4)

Single-machine mode, for teammates developing before their lab is up:

    python3 setup_cluster.py --local

Writes cluster.json in the repo directory. That file is gitignored — it is
machine-specific and must never be committed.
"""

import ipaddress
import json
import os
import sys

from cluster_config import (
    CONFIG_FILE,
    NODE_ROLES,
    PROCESS_LAYOUT,
    local_ips,
    processes_on_node,
)

USAGE = __doc__


def validate_ip(raw, label):
    value = raw.strip()
    try:
        ipaddress.IPv4Address(value)
    except ipaddress.AddressValueError:
        sys.exit("[ERROR] {} is not a valid IPv4 address: {!r}".format(label, raw))
    return value


def detect_my_node(node_ips):
    """Work out which of the three nodes this machine is, by matching local IPs."""
    mine = set(local_ips())
    for key, ip in node_ips.items():
        if ip in mine:
            return key
    if len(set(node_ips.values())) == 1 and next(iter(node_ips.values())) == "127.0.0.1":
        return "node1"  # single-host mode: treat as all-in-one
    return None


def prompt_for_ips():
    print("=" * 62)
    print(" Prayogshala Cluster Setup")
    print("=" * 62)
    print("Find each VM's private IP with:  hostname -I | awk '{print $1}'")
    print()
    return (
        input("Node 1 IP (Master, hosts P0)            : "),
        input("Node 2 IP (Slave 1, hosts P1 and P2)    : "),
        input("Node 3 IP (Slave 2, hosts P3 and P4)    : "),
    )


def write_config(node_ips, my_node, single_host):
    payload = {
        "nodes": node_ips,
        "my_node": my_node,
        "single_host": single_host,
        "num_processes": len(PROCESS_LAYOUT),
        "generated_by": "setup_cluster.py",
    }
    with open(CONFIG_FILE, "w") as fh:
        json.dump(payload, fh, indent=4)
        fh.write("\n")
    return payload


def summarise(node_ips, my_node, single_host):
    print()
    print("[OK] cluster.json written to {}".format(CONFIG_FILE))
    print()
    for key in ("node1", "node2", "node3"):
        marker = "   <-- THIS MACHINE" if key == my_node else ""
        procs = ", ".join(
            "{}:{}".format(PROCESS_LAYOUT[p]["short"], PROCESS_LAYOUT[p]["port"])
            for p in processes_on_node(key)
        )
        print("  {}  {:<16} {:<28} {}{}".format(key, node_ips[key], NODE_ROLES[key], procs, marker))
    print()

    if single_host:
        print("Single-host mode. All five processes will run on this machine over loopback.")
        print("Use this for development only — the demo must run across three VMs.")
    elif my_node is None:
        print("[WARN] None of the three IPs matched this machine's own addresses.")
        print("       Detected locally: {}".format(", ".join(local_ips()) or "none"))
        print("       Routing will still work, but double-check you passed the right IPs.")
    else:
        print("Next:  python3 verify_cluster.py agent      (on Node 2 and Node 3)")
        print("       python3 verify_cluster.py check      (on Node 1)")
    print()


def main():
    args = [a for a in sys.argv[1:]]

    if args and args[0] in ("-h", "--help"):
        print(USAGE)
        return

    if args and args[0] == "--local":
        node_ips = {"node1": "127.0.0.1", "node2": "127.0.0.1", "node3": "127.0.0.1"}
        write_config(node_ips, "node1", True)
        summarise(node_ips, "node1", True)
        return

    if len(args) == 3:
        raw = args
    elif not args:
        raw = prompt_for_ips()
    else:
        print(USAGE)
        sys.exit("[ERROR] Expected exactly 3 IP addresses, got {}.".format(len(args)))

    node_ips = {
        "node1": validate_ip(raw[0], "Node 1"),
        "node2": validate_ip(raw[1], "Node 2"),
        "node3": validate_ip(raw[2], "Node 3"),
    }

    if len(set(node_ips.values())) != 3:
        print("[WARN] Two or more nodes share the same IP. That is only correct if you")
        print("       are deliberately co-locating processes on fewer machines.")

    my_node = detect_my_node(node_ips)
    write_config(node_ips, my_node, False)
    summarise(node_ips, my_node, False)


if __name__ == "__main__":
    main()
