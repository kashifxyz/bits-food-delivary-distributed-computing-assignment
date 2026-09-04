# Distributed System Monitor — Bug Audit & Resolution Report

**Initial Audit Date & Time:** 2026-09-03 23:41:34 IST  
**Latest Update Date & Time:** 2026-09-04 14:15:42 IST  
**Project:** Distributed Food Delivery System (Tracking Events and Capturing Global State)  
**Scope:** Full multi-process codebase review & fixes (`src/vector_clock.py`, `src/snapshot.py`, `src/p0.py`, `src/p1.py`, `src/p2.py`, `src/p3.py`, `src/p4.py`, `config/hosts.cfg`, `tests/`)

---

## 1. Executive Summary

A comprehensive code audit was conducted across the distributed processes and algorithm implementations across two engineering iterations. A total of **10 bugs / integration flaws** have been identified and resolved:
* **Iteration 1 (2026-09-03):** Fixed 6 foundational bugs in Vector Clocks, Chandy-Lamport channel state recording, socket streaming (`sendall`), macOS port 5000 AirPlay collision, and `hosts.cfg` configuration loading.
* **Iteration 2 (2026-09-04):** Resolved 4 integration and protocol compatibility bugs arising from the addition of Delivery Partner processes `src/p3.py` and `src/p4.py`, including delivery handoff formatting, nested `STATE` payload resolution, dynamic host resolution, and graceful `Ctrl+C` shutdown handling across all 5 nodes.

---

## 2. Iteration 1 Bug Audit & Resolutions (2026-09-03 23:41:34 IST)

### BUG-01: Hardcoded `"localhost"` in Inter-Process Socket Communication
* **Severity:** Critical (Blocks Cloud/Multi-Node Deployment)
* **Affected Files:** `src/snapshot.py` (line 75), `src/p1.py` (line 71), `src/p2.py` (line 71)
* **Description:** 
  The networking functions in `snapshot.py`, `p1.py`, and `p2.py` hardcoded `sock.connect(("localhost", port))`. When deploying across Prayogshala cloud nodes (Node 1, Node 2, Node 3), inter-process message exchange failed with `ConnectionRefusedError`.
* **Fix Applied:** 
  Created a shared `load_network_config(path)` function in `snapshot.py`, `p1.py`, `p2.py`, and `p0.py` that dynamically resolves destination IP addresses from `config/hosts.cfg` while defaulting to `localhost` for single-node development.
* **Status:** ✅ RESOLVED

---

### BUG-02: `config/hosts.cfg` Node IP Reference Dereferencing Failure
* **Severity:** Critical (Blocks Cloud/Multi-Node Deployment)
* **Affected Files:** `config/hosts.cfg`, `src/p1.py`, `src/p2.py`, `src/snapshot.py`
* **Description:** 
  In `config/hosts.cfg`, process mappings use indirect keys:
  ```ini
  [nodes]
  NODE1_IP=10.0.0.1
  [process_hosts]
  P0_HOST=NODE1_IP
  ```
  Naively reading `c["process_hosts"]["P0_HOST"]` yielded the literal string `"NODE1_IP"` instead of the actual resolved IP address (`10.0.0.1`), causing DNS / connection errors.
* **Fix Applied:** 
  Implemented two-level configuration resolution: parses `[nodes]` dictionary and dereferences `process_hosts` entries (`P0_HOST` -> `NODE1_IP` -> `10.0.0.1`).
* **Status:** ✅ RESOLVED

---

### BUG-03: Incomplete Socket Transmission via `sock.send()` instead of `sock.sendall()`
* **Severity:** High (Data Truncation / Protocol Corruption)
* **Affected Files:** `src/snapshot.py` (line 77), `src/p1.py` (line 72), `src/p2.py` (line 72)
* **Description:** 
  Python's `socket.send()` is not guaranteed to send all bytes in a single call. Large JSON state messages or marker payloads could be truncated, leading to `json.JSONDecodeError` on the receiving end.
* **Fix Applied:** 
  Replaced all instances of `sock.send(...)` with `sock.sendall(...)` across `snapshot.py`, `p1.py`, `p2.py`, and `p0.py`.
* **Status:** ✅ RESOLVED

---

### BUG-04: Missing Channel State Recording in Chandy-Lamport Algorithm
* **Severity:** High (Assignment Requirement Violation)
* **Affected Files:** `src/snapshot.py` (lines 45, 125-175), `src/p1.py`, `src/p2.py`
* **Description:** 
  The Chandy-Lamport algorithm requires recording:
  1. Process local state upon the first marker.
  2. In-transit channel messages arriving on incoming channels between local state recording and marker arrival on that channel.
  In `snapshot.py`, `self.channel_state` was defined but never populated when in-flight messages arrived.
* **Fix Applied:** 
  Added `record_channel_message(sender, msg)` in `ChandyLamportSnapshot`. In `p1.py`, `p2.py`, and `p0.py`, regular incoming messages are routed to `snapshot.record_channel_message(sender, msg)` when a snapshot is active on that channel, and included in `STATE` messages sent to the coordinator.
* **Status:** ✅ RESOLVED

---

### BUG-05: Port 5000 AirPlay Conflict on macOS Development Environments
* **Severity:** Medium (Developer Experience / Local Testing)
* **Affected Files:** `config/hosts.cfg`, `src/p0.py`
* **Description:** 
  Port `5000` is used by macOS AirPlay Receiver (`ControlCenter`). When developers test locally on macOS, `P0` crashed on `bind()` with `OSError: [Errno 48] Address already in use`.
* **Fix Applied:** 
  Updated `config/hosts.cfg` default `P0_PORT=5005`, added `--port` CLI override in `src/p0.py`, and implemented automatic port fallback to 5005 if port 5000 is occupied.
* **Status:** ✅ RESOLVED

---

### BUG-06: `VectorClock.is_concurrent` Type Inflexibility
* **Severity:** Low (API Fragility)
* **Affected Files:** `src/vector_clock.py` (line 42)
* **Description:** 
  Passing a `VectorClock` instance directly to `vc1.is_concurrent(vc2)` caused `TypeError: 'VectorClock' object is not subscriptable` because it only accepted a raw `list`.
* **Fix Applied:** 
  Updated `is_concurrent(self, other_clock)` and `receive_event(self, received_clock)` to check `if hasattr(other_clock, "get_clock"): other_clock = other_clock.get_clock()`. Also added bounds and type safety checks.
* **Status:** ✅ RESOLVED

---

## 3. Iteration 2 Bug Audit & Resolutions (2026-09-04 14:15:42 IST)
*Scope: Integration of `src/p3.py` (Fleet Runner A) and `src/p4.py` (Fleet Runner B) with `p0.py` and `snapshot.py`.*

### BUG-07: Hardcoded Port 5000 & Host Resolution Failure in `p3.py` & `p4.py`
* **Severity:** Critical (Blocks Multi-Node & Local 5-Process Execution)
* **Affected Files:** `src/p3.py` (lines 39-45), `src/p4.py` (lines 47-53)
* **Description:** 
  `p3.py` and `p4.py` used a hardcoded `NODES` dictionary specifying `P0: {"host": "127.0.0.1", "port": 5000}`. Because `P0` binds to port `5005` (and connects via resolved Prayogshala node IPs in cloud deployments), `P3` and `P4` failed to deliver `STATE` snapshot reports and `DELIVERY` confirmations to `P0`, crashing with `ConnectionRefusedError`.
* **Fix Applied:** 
  Replaced hardcoded `NODES` with `load_network_config()` from `config/hosts.cfg` across `src/p3.py` and `src/p4.py`.
* **Status:** ✅ RESOLVED

---

### BUG-08: Payload & Snapshot ID Key Mismatch in `STATE` Messages from `P3`/`P4`
* **Severity:** High (State Collection Failure / Snapshot Dropping)
* **Affected Files:** `src/p0.py`, `src/snapshot.py`, `src/p3.py`, `src/p4.py`
* **Description:** 
  `p3.py` and `p4.py` wrapped their state inside `msg["data"]["snapshot_id"]` instead of top-level `msg["snapshot_id"]`. When received by `P0` / `snapshot.py`, `msg.get("snapshot_id")` evaluated to `None` or raised a `KeyError`, preventing `P0` from associating the state report with the active snapshot.
* **Fix Applied:** 
  Updated `snapshot.handle_state()` and `p0.py` `dispatch()` to safely extract `snapshot_id` from either top-level `msg["snapshot_id"]` or nested `msg["data"]["snapshot_id"]`. Updated process counters to track `Progress: 5/5 processes recorded`.
* **Status:** ✅ RESOLVED

---

### BUG-09: Unhandled `DELIVERY` Message Type at `P0` Coordinator
* **Severity:** Medium (Protocol Compatibility / Delivery Tracking)
* **Affected Files:** `src/p0.py` (lines 280-295)
* **Description:** 
  `p3.py` and `p4.py` transmit delivery completion notifications using `{"type": "DELIVERY", "data": "Order #... delivered...", "from": "P3"}`. `p0.py` previously only matched `DELIVERY_COMPLETE` / `ORDER_DELIVERED`, causing incoming notifications to fall into the unhandled message log without merging vector clocks or updating delivery status.
* **Fix Applied:** 
  Extended `p0.py` dispatching logic to match `type: "DELIVERY"`, advance `P0`'s vector clock upon receipt (`vc.receive_event()`), and log order fulfillment.
* **Status:** ✅ RESOLVED

---

### BUG-10: Lack of Graceful Signal Handling (`SIGINT`/`Ctrl+C`)
* **Severity:** Low (Terminal Developer Experience & Socket Cleanup)
* **Affected Files:** `src/p0.py`, `src/p1.py`, `src/p2.py`, `src/p3.py`, `src/p4.py`
* **Description:** 
  Pressing `Ctrl+C` produced raw `KeyboardInterrupt` stack traces across all process terminals and left TCP listening sockets in `TIME_WAIT` / open states on local machines.
* **Fix Applied:** 
  Added `signal.signal(signal.SIGINT, shutdown_handler)` and `signal.signal(signal.SIGTERM, shutdown_handler)` across all 5 processes to close listening sockets and exit cleanly.
* **Status:** ✅ RESOLVED

---

## 4. Complete Verification & Regression Log

| Test Suite / Script | Target Scope | Command Executed | Result | Notes |
|---|---|---|---|---|
| **Vector Clock Unit Tests** | Vector Clocks ($N=5$) | `python tests/test_vector_clock.py` | ✅ **9/9 PASSED** | Verified initial state, increments, merge $\max(L, R)$, concurrency detection ($P1 \parallel P2$), and thread safety. |
| **P0 & Snapshot Unit Test** | P0 Coordinator Socket & Cut | `python tests/test_p0_integration.py` | ✅ **PASSED** | Validated P0 socket dispatching, marker emission, state reception, and causal consistency calculation. |
| **Full System 5-Node Test** | All 5 Processes (`P0`-`P4`) | `python tests/test_full_system.py` | ✅ **PASSED** | End-to-end multi-process execution: order creation $\to$ kitchen prep $\to$ transit $\to$ delivery $\to$ 2 global snapshots capturing all 5/5 processes consistent. |
