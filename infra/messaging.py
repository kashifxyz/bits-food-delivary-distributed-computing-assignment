"""
messaging.py — Framed, FIFO socket transport for the five processes.
Owner: Sohail (Infrastructure)

WHY THIS EXISTS
---------------
Two things break a naive socket implementation of this assignment:

1. TCP is a byte stream, not a message stream. A bare conn.recv(1024) will
   sometimes return two JSON messages glued together, and sometimes half of
   one. json.loads() then raises. This layer length-prefixes every message
   (4-byte big-endian length + UTF-8 JSON) so a message is always delivered
   whole and alone.

2. Chandy-Lamport assumes FIFO channels. If every send opens a fresh TCP
   connection, two messages on the same logical channel race on separate
   sockets and can arrive out of order — a MARKER can overtake the ORDER it
   was meant to follow, and the recorded cut is then not consistent. This
   layer keeps ONE persistent connection per directed channel (i -> j), which
   makes per-channel ordering guaranteed.

USAGE
-----
    from messaging import Node

    node = Node(1)                      # P1, Restaurant A
    node.start()                        # binds 0.0.0.0:5001, starts accepting

    node.send(3, {"type": "DELIVERY", "data": "...", "clock": vc.get_clock(),
                  "from": "P1"})

    sender_pid, msg = node.receive()             # blocks
    sender_pid, msg = node.receive(timeout=5)    # or (None, None) on timeout

    node.close()

The sender_pid returned by receive() is the CHANNEL the message arrived on.
Abhirup's snapshot code needs exactly that to attribute in-transit messages to
the right channel.

Nothing in this file knows about vector clocks or the snapshot algorithm. It
only moves dictionaries between processes, in order, intact.
"""

import json
import queue
import socket
import struct
import sys
import threading
import time

from cluster_config import (
    get_my_bind_address,
    get_process_name,
    get_target_address,
    peers_of,
)

# 4-byte big-endian unsigned length prefix.
_HEADER = struct.Struct("!I")
MAX_MESSAGE_BYTES = 4 * 1024 * 1024

# Sent as the first frame on every new outgoing connection so the receiver
# knows which process owns the channel.
HELLO_KEY = "__hello_from__"

CONNECT_RETRY_SECONDS = 0.5
DEFAULT_CONNECT_TIMEOUT = 60.0


class TransportError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Wire format
# ---------------------------------------------------------------------------

def _send_frame(sock, payload_dict):
    body = json.dumps(payload_dict).encode("utf-8")
    if len(body) > MAX_MESSAGE_BYTES:
        raise TransportError("Message too large: {} bytes".format(len(body)))
    sock.sendall(_HEADER.pack(len(body)) + body)


def _recv_exactly(sock, n):
    """Read exactly n bytes, or return None if the peer closed cleanly."""
    chunks = []
    remaining = n
    while remaining:
        chunk = sock.recv(remaining)
        if not chunk:
            return None
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _recv_frame(sock):
    """Read one complete message, or None if the connection closed."""
    header = _recv_exactly(sock, _HEADER.size)
    if header is None:
        return None
    (length,) = _HEADER.unpack(header)
    if length > MAX_MESSAGE_BYTES:
        raise TransportError("Declared frame length {} exceeds limit".format(length))
    body = _recv_exactly(sock, length)
    if body is None:
        return None
    return json.loads(body.decode("utf-8"))


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

class Node:
    """Transport endpoint for one process.

    One listener socket, plus one persistent outgoing connection per peer that
    this process actually sends to. Incoming messages land on a single queue
    tagged with the sending process id.
    """

    def __init__(self, process_id, verbose=True):
        self.pid = int(process_id)
        self.name = get_process_name(self.pid, short=True)
        self.verbose = verbose

        self.inbox = queue.Queue()

        self._server = None
        self._out_links = {}            # target_pid -> socket
        self._out_locks = {}            # target_pid -> Lock guarding that socket
        self._links_lock = threading.Lock()
        self._reader_threads = []
        self._running = threading.Event()

    # -- lifecycle ---------------------------------------------------------

    def _log(self, text):
        if self.verbose:
            print("[NET] {} | {}".format(self.name, text), flush=True)

    def start(self):
        """Bind the listener and begin accepting connections."""
        bind_addr = get_my_bind_address(self.pid)
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self._server.bind(bind_addr)
        except OSError as exc:
            raise TransportError(
                "Could not bind {}:{} — {}. Is another copy of this process "
                "still running?".format(bind_addr[0], bind_addr[1], exc)
            )
        self._server.listen(8)
        self._server.settimeout(0.5)
        self._running.set()

        accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        accept_thread.start()
        self._log("listening on {}:{}".format(*bind_addr))
        return self

    def _accept_loop(self):
        while self._running.is_set():
            try:
                conn, addr = self._server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            thread = threading.Thread(target=self._reader_loop, args=(conn, addr), daemon=True)
            thread.start()
            self._reader_threads.append(thread)

    def _reader_loop(self, conn, addr):
        """Serve one inbound channel. The first frame identifies the sender."""
        sender_pid = None
        try:
            conn.settimeout(None)
            hello = _recv_frame(conn)
            if hello is None or HELLO_KEY not in hello:
                self._log("rejected unidentified connection from {}".format(addr[0]))
                return
            sender_pid = int(hello[HELLO_KEY])
            self._log("channel open  P{} -> {}".format(sender_pid, self.name))

            while self._running.is_set():
                msg = _recv_frame(conn)
                if msg is None:
                    break
                self.inbox.put((sender_pid, msg))
        except (OSError, ValueError, TransportError) as exc:
            if self._running.is_set():
                self._log("channel error from {}: {}".format(addr[0], exc))
        finally:
            try:
                conn.close()
            except OSError:
                pass
            if sender_pid is not None:
                self._log("channel closed  P{} -> {}".format(sender_pid, self.name))

    def close(self):
        """Shut down cleanly. Safe to call twice."""
        self._running.clear()
        with self._links_lock:
            for sock in self._out_links.values():
                try:
                    sock.close()
                except OSError:
                    pass
            self._out_links.clear()
        if self._server is not None:
            try:
                self._server.close()
            except OSError:
                pass
            self._server = None
        self._log("shut down")

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.close()
        return False

    # -- outgoing ----------------------------------------------------------

    def _get_link(self, target_pid, timeout=DEFAULT_CONNECT_TIMEOUT):
        """Return the persistent socket to target_pid, connecting if needed."""
        with self._links_lock:
            existing = self._out_links.get(target_pid)
            if existing is not None:
                return existing

        ip, port = get_target_address(target_pid)
        deadline = time.time() + timeout
        attempt = 0
        last_error = None

        while time.time() < deadline:
            attempt += 1
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            try:
                sock.connect((ip, port))
                sock.settimeout(None)
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                _send_frame(sock, {HELLO_KEY: self.pid})
            except OSError as exc:
                last_error = exc
                sock.close()
                if attempt == 1:
                    self._log("waiting for P{} at {}:{} ...".format(target_pid, ip, port))
                time.sleep(CONNECT_RETRY_SECONDS)
                continue

            with self._links_lock:
                # Another thread may have raced us to the same peer.
                if target_pid in self._out_links:
                    sock.close()
                    return self._out_links[target_pid]
                self._out_links[target_pid] = sock
                self._out_locks[target_pid] = threading.Lock()
            self._log("channel open  {} -> P{} ({}:{})".format(self.name, target_pid, ip, port))
            return sock

        raise TransportError(
            "Could not reach P{} at {}:{} after {:.0f}s — {}. "
            "Check that the process is running and ports 5000-5004 are open."
            .format(target_pid, ip, port, timeout, last_error)
        )

    def connect_to(self, target_pids, timeout=DEFAULT_CONNECT_TIMEOUT):
        """Open channels up front so the demo does not stall mid-run."""
        for pid in target_pids:
            self._get_link(pid, timeout=timeout)

    def send(self, target_pid, message, timeout=DEFAULT_CONNECT_TIMEOUT):
        """Send one dict to target_pid. Blocks until the bytes are handed to TCP.

        Ordering is preserved per destination: two sends to the same peer are
        delivered in the order they were issued.
        """
        if not isinstance(message, dict):
            raise TypeError("message must be a dict, got {}".format(type(message).__name__))

        target_pid = int(target_pid)
        sock = self._get_link(target_pid, timeout=timeout)
        lock = self._out_locks[target_pid]
        with lock:
            try:
                _send_frame(sock, message)
            except OSError as exc:
                with self._links_lock:
                    self._out_links.pop(target_pid, None)
                    self._out_locks.pop(target_pid, None)
                try:
                    sock.close()
                except OSError:
                    pass
                raise TransportError("Send to P{} failed: {}".format(target_pid, exc))

    def broadcast(self, message, targets=None):
        """Send the same dict to several peers. Used for snapshot MARKERs."""
        for pid in (peers_of(self.pid) if targets is None else targets):
            self.send(pid, dict(message))

    # -- incoming ----------------------------------------------------------

    def receive(self, timeout=None):
        """Next (sender_pid, message). Returns (None, None) if timeout expires."""
        try:
            return self.inbox.get(timeout=timeout)
        except queue.Empty:
            return (None, None)

    def pending(self):
        """Approximate count of undelivered messages sitting in the inbox."""
        return self.inbox.qsize()

    def drain(self):
        """Pop everything currently queued without blocking."""
        out = []
        while True:
            try:
                out.append(self.inbox.get_nowait())
            except queue.Empty:
                return out


# ---------------------------------------------------------------------------
# Self-test: python3 messaging.py selftest
# ---------------------------------------------------------------------------

def _selftest_responder(pid, expected):
    """Child-process entry point for the self-test.

    Must live at module level: macOS and Windows start subprocesses with
    'spawn', which pickles the target function, and nested functions cannot
    be pickled.
    """
    node = Node(pid, verbose=False).start()
    received = []
    while len(received) < expected:
        _sender, msg = node.receive(timeout=30)
        if msg is None:
            break
        received.append(msg["seq"])
    node.close()
    ok = received == list(range(expected))
    print("  P{} received {} of {} messages, order {}".format(
        pid, len(received), expected,
        "PRESERVED" if ok else "BROKEN"), flush=True)
    sys.exit(0 if ok else 1)


def _selftest():
    """Prove framing and FIFO ordering hold under back-to-back sends."""
    import multiprocessing

    # 'spawn' on every platform so the test behaves identically on macOS,
    # Linux and the Prayogshala VMs.
    ctx = multiprocessing.get_context("spawn")

    burst = 200
    workers = []
    for pid in (1, 2):
        proc = ctx.Process(target=_selftest_responder, args=(pid, burst))
        proc.start()
        workers.append(proc)

    # spawn re-imports the module in each child, so allow time to boot.
    # Node.send() also retries on its own if a listener is not up yet.
    time.sleep(3.0)

    sender = Node(0, verbose=False).start()
    padding = "x" * 3000  # large enough to span multiple TCP segments
    for target in (1, 2):
        for seq in range(burst):
            sender.send(target, {"type": "TEST", "seq": seq, "pad": padding, "from": "P0"})

    for proc in workers:
        proc.join(timeout=60)
    sender.close()

    failed = [p for p in workers if p.exitcode != 0]
    print("  result: {}".format("PASS" if not failed else "FAIL"), flush=True)
    return 0 if not failed else 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        print("messaging.py self-test (framing + FIFO under burst load)")
        sys.exit(_selftest())
    print(__doc__)