"""
snapshot.py

Chandy-Lamport Distributed Snapshot Algorithm
for Food Delivery Distributed System

Topology:

P0 --> P1 --> P3
 |
 +--> P2 --> P4

P0 = Coordinator
"""

import json
import socket
import threading
from copy import deepcopy

# Import Vector Clock class
from vector_clock import VectorClock


class ChandyLamportSnapshot:

    def __init__(
        self,
        process_name,
        process_id,
        vector_clock,
        outgoing_neighbors,
        coordinator="P0"
    ):

        self.process_name = process_name
        self.process_id = process_id
        self.vc = vector_clock
        self.outgoing_neighbors = outgoing_neighbors
        self.coordinator = coordinator

        self.lock = threading.Lock()

        # snapshot_id -> local state
        self.local_states = {}

        # snapshot_id -> {channel : messages}
        self.channel_states = {}

        # snapshot_id -> channels still recording
        self.recording_channels = {}

        # snapshot_id -> completed?
        self.completed = {}

        #
        # Incoming-channel mapping
        #
        self.incoming_channels = {
            "P0": ["P3", "P4"],
            "P1": ["P0"],
            "P2": ["P0"],
            "P3": ["P1"],
            "P4": ["P2"]
        }

    # -----------------------------------------------------
    # Network send utility
    # -----------------------------------------------------

    def _send_json(self, host, port, msg):

        try:

            with socket.socket(
                socket.AF_INET,
                socket.SOCK_STREAM
            ) as s:

                s.settimeout(5)

                s.connect((host, port))

                payload = json.dumps(msg)

                try:
                    s.sendall((payload + "\n").encode())
                except:
                    s.sendall(payload.encode())

        except Exception as e:

            print(
                f"[SNAPSHOT ERROR]"
                f" {self.process_name} "
                f"send failed: {e}"
            )

    # -----------------------------------------------------
    # Snapshot initiation by coordinator
    # -----------------------------------------------------

    def initiate_snapshot(
        self,
        snapshot_id,
        ports,
        hosts
    ):

        with self.lock:

            # vector_clock filled in after marker sends below (see handle_marker
            # for why: it keeps our recorded clock >= anything we send out).
            self.local_states[snapshot_id] = {
                "process": self.process_name,
                "vector_clock": None,
                "local_state": {
                    "initiator": True
                }
            }

            self.channel_states[snapshot_id] = {}

            self.recording_channels[snapshot_id] = set(
                self.incoming_channels.get(
                    self.process_name,
                    []
                )
            )

            self.completed[snapshot_id] = False

        print(
            f"[SNAPSHOT] "
            f"{self.process_name} | "
            f"{snapshot_id} triggered | "
            f"Clock: {self.vc.get_clock()}"
        )

        marker_msg = {
            "type": "MARKER",
            "snapshot_id": snapshot_id,
            "from": self.process_name,
            "clock": self.vc.send_event(),
            "data": {
                "snapshot_id": snapshot_id
            }
        }

        for neighbor in self.outgoing_neighbors:

            self._send_json(
                hosts.get(neighbor, "localhost"),
                ports[neighbor],
                marker_msg
            )

            print(
                f"[MARKER]"
                f" {self.process_name}"
                f" -> {neighbor}"
                f" | {snapshot_id}"
            )

        self.local_states[snapshot_id]["vector_clock"] = self.vc.get_clock()

        # P0 usually has no incoming markers,
        # therefore send state immediately.
        if len(
            self.recording_channels[snapshot_id]
        ) == 0:

            self.completed[snapshot_id] = True

            self.send_state_to_coordinator(
                snapshot_id,
                ports,
                hosts
            )

    # -----------------------------------------------------
    # Record in-transit messages
    # -----------------------------------------------------

    def record_channel_message(
        self,
        sender,
        message
    ):

        with self.lock:

            for snap_id in self.local_states:

                if self.completed.get(snap_id):

                    continue

                if sender in \
                   self.recording_channels.get(
                        snap_id,
                        set()
                   ):

                    self.channel_states\
                        .setdefault(
                            snap_id,
                            {}
                        )\
                        .setdefault(
                            sender,
                            []
                        )\
                        .append(
                            deepcopy(message)
                        )

    # -----------------------------------------------------
    # Handle marker
    # -----------------------------------------------------

    def handle_marker(
        self,
        msg,
        ports,
        hosts
    ):

        snapshot_id = (
            msg.get("snapshot_id")
            or
            msg.get("data", {}).get(
                "snapshot_id"
            )
            or
            "SNAPSHOT_1"
        )

        sender = msg.get(
            "from",
            "UNKNOWN"
        )

        self.vc.receive_event(
            msg.get(
                "clock",
                self.vc.get_clock()
            )
        )

        first_marker = False

        with self.lock:

            #
            # First marker
            #
            if snapshot_id not in \
                    self.local_states:

                first_marker = True

                # vector_clock is filled in AFTER marker forwarding below --
                # forwarding is itself a send event that advances our clock,
                # so recording it here (before forwarding) would let this
                # clock value undercount what we're about to send downstream,
                # making a downstream process "know" more about us than our
                # own recorded state admits: a real causal inconsistency.
                self.local_states[snapshot_id] = {

                    "process":
                        self.process_name,

                    "vector_clock":
                        None,

                    "local_state":
                        f"Recorded by "
                        f"{self.process_name}"
                }

                self.channel_states[
                    snapshot_id
                ] = {}

                incoming = set(
                    self.incoming_channels.get(
                        self.process_name,
                        []
                    )
                )

                self.recording_channels[
                    snapshot_id
                ] = incoming

                self.completed[
                    snapshot_id
                ] = False

            #
            # Marker closes channel
            #
            self.recording_channels[
                snapshot_id
            ].discard(sender)

        print(
            f"[MARKER RECV] "
            f"{self.process_name}"
            f" <- {sender}"
            f" | {snapshot_id}"
            f" | Clock:"
            f" {self.vc.get_clock()}"
        )

        #
        # First marker => forward markers
        #
        if first_marker:

            marker = {

                "type": "MARKER",

                "snapshot_id":
                    snapshot_id,

                "from":
                    self.process_name,

                "clock":
                    self.vc.send_event(),

                "data": {
                    "snapshot_id":
                        snapshot_id
                }
            }

            for neighbor in \
                    self.outgoing_neighbors:

                self._send_json(
                    hosts.get(
                        neighbor,
                        "localhost"
                    ),
                    ports[neighbor],
                    marker
                )

                print(
                    f"[MARKER]"
                    f" {self.process_name}"
                    f" -> {neighbor}"
                )

            # Now freeze the clock -- it's >= anything we just sent out.
            self.local_states[snapshot_id]["vector_clock"] = self.vc.get_clock()

        #
        # Snapshot complete?
        #
        if len(
            self.recording_channels[
                snapshot_id
            ]
        ) == 0:

            with self.lock:

                if not self.completed[
                    snapshot_id
                ]:

                    self.completed[
                        snapshot_id
                    ] = True

                    self.send_state_to_coordinator(
                        snapshot_id,
                        ports,
                        hosts
                    )

    # -----------------------------------------------------
    # Send state to coordinator
    # -----------------------------------------------------

    def send_state_to_coordinator(
        self,
        snapshot_id,
        ports,
        hosts
    ):

        state_payload = {

            "snapshot_id":
                snapshot_id,

            "process":
                self.process_name,

            "vector_clock":
                self.vc.get_clock(),

            "local_state":
                self.local_states[
                    snapshot_id
                ],

            "channel_state":
                self.channel_states.get(
                    snapshot_id,
                    {}
                )
        }

        state_msg = {

            "type":
                "STATE",

            "snapshot_id":
                snapshot_id,

            "from":
                self.process_name,

            "clock":
                self.vc.send_event(),

            "data":
                state_payload
        }

        self._send_json(
            hosts.get(
                self.coordinator,
                "localhost"
            ),
            ports[self.coordinator],
            state_msg
        )

        print(
            f"[STATE] "
            f"{self.process_name}"
            f" -> {self.coordinator}"
            f" | {snapshot_id}"
        )

    # -----------------------------------------------------
    # Coordinator collects states
    # -----------------------------------------------------

    def handle_state(
        self,
        msg,
        state_store
    ):

        # Must match handle_marker()'s extraction: some senders (e.g. P3/P4)
        # nest snapshot_id inside "data" instead of at the top level. Using a
        # cruder fallback here than handle_marker() does causes state to be
        # silently filed under the wrong snapshot bucket -- e.g. SNAPSHOT_2
        # data landing in "SNAPSHOT_1", stalling SNAPSHOT_2 short of 5/5.
        snapshot_id = (
            msg.get("snapshot_id")
            or (
                msg.get("data", {}).get("snapshot_id")
                if isinstance(msg.get("data"), dict) else None
            )
            or "SNAPSHOT_1"
        )

        sender = msg.get(
            "from",
            "UNKNOWN"
        )

        state_store\
            .setdefault(
                snapshot_id,
                {}
            )

        state_store[
            snapshot_id
        ][sender] = msg.get(
            "data",
            {}
        )

        print(
            f"[STATE RECEIVED] "
            f"{sender} -> "
            f"{self.process_name}"
            f" | {snapshot_id}"
        )
