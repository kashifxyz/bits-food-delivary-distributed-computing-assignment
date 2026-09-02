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

MARKER = "MARKER"
STATE = "STATE"


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

        self.channel_state = {}

    # ====================================================
    # RECORD LOCAL STATE
    # ====================================================

    def record_local_state(self, snapshot_id):

        state = {
            "process": self.process_name,
            "vector_clock": self.vc.get_clock(),
            "local_state": f"Current state of {self.process_name}"
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

    def send_message(self, target_port, message):

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(("localhost", target_port))

            sock.send(json.dumps(message).encode())

            sock.close()

        except Exception as e:
            print(f"Send Error: {e}")

    # ====================================================
    # INITIATE SNAPSHOT
    # ====================================================

    def initiate_snapshot(self,
                          snapshot_id,
                          ports):

        print(
            f"[SNAPSHOT] {self.process_name} | "
            f"{snapshot_id} triggered | "
            f"Clock: {self.vc.increment()}"
        )

        self.snapshot_active[snapshot_id] = True

        self.record_local_state(snapshot_id)

        self.marker_received[snapshot_id] = set()

        for neighbor in self.outgoing_neighbors:

            marker = {
                "type": MARKER,
                "snapshot_id": snapshot_id,
                "clock": self.vc.send_event(),
                "from": self.process_name
            }

            self.send_message(ports[neighbor], marker)

            print(
                f"[SEND] {self.process_name} → {neighbor} | "
                f"MARKER {snapshot_id} | "
                f"Clock: {marker['clock']}"
            )

    # ====================================================
    # HANDLE MARKER
    # ====================================================

    def handle_marker(self,
                      msg,
                      ports):

        snapshot_id = msg["snapshot_id"]

        sender = msg["from"]

        self.vc.receive_event(msg["clock"])

        first_marker = (
            snapshot_id not in self.snapshot_active
        )

        if first_marker:

            self.snapshot_active[snapshot_id] = True

            self.marker_received[snapshot_id] = {sender}

            self.record_local_state(snapshot_id)

            for neighbor in self.outgoing_neighbors:

                marker = {
                    "type": MARKER,
                    "snapshot_id": snapshot_id,
                    "clock": self.vc.send_event(),
                    "from": self.process_name
                }

                self.send_message(
                    ports[neighbor],
                    marker
                )

                print(
                    f"[SEND] {self.process_name} → {neighbor}"
                    f" | MARKER {snapshot_id}"
                    f" | Clock: {marker['clock']}"
                )

            self.send_state_to_coordinator(
                snapshot_id,
                ports
            )

        else:

            self.marker_received[snapshot_id].add(sender)

    # ====================================================
    # SEND STATE TO P0
    # ====================================================

    def send_state_to_coordinator(self,
                                  snapshot_id,
                                  ports):

        state_message = {

            "type": STATE,

            "snapshot_id": snapshot_id,

            "data": self.recorded_state[snapshot_id],

            "clock": self.vc.send_event(),

            "from": self.process_name
        }

        self.send_message(
            ports[self.coordinator],
            state_message
        )

        print(
            f"[SEND] {self.process_name} → {self.coordinator}"
            f" | STATE {snapshot_id}"
            f" | Clock: {state_message['clock']}"
        )

    # ====================================================
    # HANDLE STATE MESSAGE
    # ====================================================

    def handle_state(self,
                     msg,
                     state_store):

        snapshot_id = msg["snapshot_id"]

        sender = msg["from"]

        state_store.setdefault(snapshot_id, {})

        state_store[snapshot_id][sender] = msg["data"]

        print(
            f"[STATE] Received state from {sender}"
            f" for {snapshot_id}"
        )
