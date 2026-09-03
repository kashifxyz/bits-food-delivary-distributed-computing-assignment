"""
snapshot.py

Chandy-Lamport Snapshot Implementation
For Distributed Food Delivery System

Processes:
P0 -> Coordinator
P1 -> Restaurant A
P2 -> Restaurant B
P3 -> Delivery Partner A
P4 -> Delivery Partner B
"""

import json
import socket
import threading
import configparser
import os

MARKER = "MARKER"
STATE = "STATE"

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "hosts.cfg")


def load_network_config(path=CONFIG_PATH):
    """Loads ports and resolves host IPs from hosts.cfg."""
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


class ChandyLamportSnapshot:

    def __init__(self,
                 process_name,
                 process_id,
                 vector_clock,
                 outgoing_neighbors,
                 coordinator="P0"):

        self.process_name = process_name
        self.process_id = process_id
        self.vc = vector_clock

        self.outgoing_neighbors = outgoing_neighbors
        self.coordinator = coordinator

        self.snapshot_active = {}
        self.recorded_state = {}
        self.marker_received = {}
        self.channel_state = {}  # {snapshot_id: {sender_id: [messages]}}
        self.channel_recording = {}  # {snapshot_id: {sender_id: bool}}

        self.ports, self.hosts = load_network_config()

    # ====================================================
    # RECORD LOCAL STATE
    # ====================================================

    def record_local_state(self, snapshot_id, extra_state=None):

        state = {
            "process": self.process_name,
            "vector_clock": self.vc.get_clock(),
            "local_state": extra_state if extra_state is not None else f"Current state of {self.process_name}"
        }

        self.recorded_state[snapshot_id] = state

        print(
            f"[SNAPSHOT] {self.process_name} | "
            f"Local state recorded for {snapshot_id} | "
            f"Clock: {self.vc.get_clock()}"
        )

    # ====================================================
    # SEND MESSAGE
    # ====================================================

    def send_message(self, target_process, message, ports=None, hosts=None):
        if ports is None:
            ports = self.ports
        if hosts is None:
            hosts = self.hosts

        target_port = ports.get(target_process)
        target_host = hosts.get(target_process, "localhost")

        if not target_port:
            print(f"Send Error: Unknown process {target_process}")
            return

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3.0)
            sock.connect((target_host, target_port))
            sock.sendall(json.dumps(message).encode())
            sock.close()
        except Exception as e:
            print(f"Send Error from {self.process_name} to {target_process} ({target_host}:{target_port}): {e}")

    # ====================================================
    # INITIATE SNAPSHOT
    # ====================================================

    def initiate_snapshot(self, snapshot_id, ports=None, hosts=None):
        if ports is None:
            ports = self.ports
        if hosts is None:
            hosts = self.hosts

        print(
            f"[SNAPSHOT] {self.process_name} | "
            f"{snapshot_id} triggered | "
            f"Clock: {self.vc.increment()}"
        )

        self.snapshot_active[snapshot_id] = True
        self.record_local_state(snapshot_id)
        self.marker_received[snapshot_id] = set()
        self.channel_state[snapshot_id] = {}
        self.channel_recording[snapshot_id] = {}

        # Initiator records on all other incoming channels until markers arrive
        for neighbor in self.outgoing_neighbors:
            marker = {
                "type": MARKER,
                "snapshot_id": snapshot_id,
                "clock": self.vc.send_event(),
                "from": self.process_name
            }
            self.send_message(neighbor, marker, ports, hosts)
            print(
                f"[SEND] {self.process_name} → {neighbor} | "
                f"MARKER {snapshot_id} | "
                f"Clock: {marker['clock']}"
            )

    # ====================================================
    # HANDLE INCOMING REGULAR MESSAGE (CHANNEL RECORDING)
    # ====================================================

    def record_channel_message(self, sender, msg):
        """Records messages that arrive on a channel while snapshot is active (in-transit)."""
        for snapshot_id, active in self.snapshot_active.items():
            if active and self.channel_recording.get(snapshot_id, {}).get(sender, False):
                self.channel_state[snapshot_id].setdefault(sender, []).append(msg)
                print(f"[CHANNEL RECORDING] {self.process_name} recorded in-transit message from {sender} for {snapshot_id}")

    # ====================================================
    # HANDLE MARKER
    # ====================================================

    def handle_marker(self, msg, ports=None, hosts=None):
        if ports is None:
            ports = self.ports
        if hosts is None:
            hosts = self.hosts

        snapshot_id = msg["snapshot_id"]
        sender = msg["from"]

        self.vc.receive_event(msg["clock"])

        first_marker = (snapshot_id not in self.snapshot_active)

        if first_marker:
            self.snapshot_active[snapshot_id] = True
            self.marker_received[snapshot_id] = {sender}
            self.channel_state[snapshot_id] = {sender: []}
            self.channel_recording[snapshot_id] = {}

            # Channel along which marker arrived is recorded as empty
            self.record_local_state(snapshot_id)

            # Start recording on all other incoming channels
            for inc in ["P0", "P1", "P2", "P3", "P4"]:
                if inc != sender and inc != self.process_name:
                    self.channel_recording[snapshot_id][inc] = True

            # Forward marker along all outgoing channels
            for neighbor in self.outgoing_neighbors:
                marker = {
                    "type": MARKER,
                    "snapshot_id": snapshot_id,
                    "clock": self.vc.send_event(),
                    "from": self.process_name
                }
                self.send_message(neighbor, marker, ports, hosts)
                print(
                    f"[SEND] {self.process_name} → {neighbor} | "
                    f"MARKER {snapshot_id} | "
                    f"Clock: {marker['clock']}"
                )

            # Transmit recorded process state to coordinator
            self.send_state_to_coordinator(snapshot_id, ports, hosts)
        else:
            # Subsequent marker on this channel: stop recording on this channel
            self.marker_received[snapshot_id].add(sender)
            self.channel_recording.get(snapshot_id, {})[sender] = False
            print(f"[SNAPSHOT] {self.process_name} stopped recording channel from {sender} for {snapshot_id}")

    # ====================================================
    # SEND STATE TO COORDINATOR
    # ====================================================

    def send_state_to_coordinator(self, snapshot_id, ports=None, hosts=None):
        if ports is None:
            ports = self.ports
        if hosts is None:
            hosts = self.hosts

        state_message = {
            "type": STATE,
            "snapshot_id": snapshot_id,
            "data": self.recorded_state[snapshot_id],
            "channel_state": self.channel_state.get(snapshot_id, {}),
            "clock": self.vc.send_event(),
            "from": self.process_name
        }

        self.send_message(self.coordinator, state_message, ports, hosts)
        print(
            f"[SEND] {self.process_name} → {self.coordinator} | "
            f"STATE {snapshot_id} | "
            f"Clock: {state_message['clock']}"
        )

    # ====================================================
    # HANDLE STATE MESSAGE (AT COORDINATOR)
    # ====================================================

    def handle_state(self, msg, state_store):
        snapshot_id = msg["snapshot_id"]
        sender = msg["from"]
        state_store.setdefault(snapshot_id, {})
        state_store[snapshot_id][sender] = msg["data"]
        if "channel_state" in msg and msg["channel_state"]:
            state_store[snapshot_id].setdefault("_channels", {})[sender] = msg["channel_state"]
        print(f"[STATE] Received state from {sender} for {snapshot_id}")
