# Distributed System Monitor — Bug Audit & Resolution Report

**Audit Date & Time:** 2026-09-03 23:41:34 IST  
**Resolution Date & Time:** 2026-09-03 23:44:15 IST  
**Project:** Distributed Food Delivery System (Tracking Events and Capturing Global State)  
**Scope:** Existing codebase review & fixes (`src/vector_clock.py`, `src/snapshot.py`, `src/p1.py`, `src/p2.py`, `src/p0.py`, `config/hosts.cfg`, `tests/`)

---

## 1. Executive Summary

A comprehensive code audit was conducted across the distributed processes and algorithm implementations. A total of **6 bugs / architectural flaws** were identified and successfully resolved:
* **2 Critical Deployment/Networking Bugs** (Hardcoded localhost & Unresolved configuration node IPs)
* **2 Protocol & Socket Reliability Bugs** (Partial TCP `send` vs `sendall` & macOS port 5000 collision)
* **2 Distributed Algorithm Compliance Bugs** (Missing channel message recording in Chandy-Lamport & `VectorClock` type mismatch handling)

All 9 vector clock tests and integration tests pass with 100% success rate.

---

## 2. Bug Details & Fix Resolutions

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
  Added `--port` CLI override argument in `src/p0.py` and wrapped `start_listener()` in friendly error handling that diagnoses macOS AirPlay conflicts and guides the user.
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

## 3. Verification Log

| Test Suite | Commands Run | Result | Notes |
|---|---|---|---|
| **Vector Clock Unit Tests** | `python tests/test_vector_clock.py` | ✅ **9/9 PASSED** | All vector clock progression, merging, concurrency, and thread-safety tests passed. |
| **P0 & Snapshot Integration Test** | `python tests/test_p0_integration.py` | ✅ **PASSED** | End-to-end socket communication, order dispatching, snapshot initiation, and causal consistency verification succeeded. |
