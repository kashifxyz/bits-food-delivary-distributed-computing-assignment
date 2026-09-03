# Distributed System Monitor: Tracking Events and Capturing Global State
**Course:** Distributed Computing | **Assignment:** Distributed Computing Lab Project  
**Group:** GROUP-XX *(Placeholder)* | **Video Demonstration:** [Link to Presentation / Demo Video] *(Placeholder)*

---

## 1. Executive Summary

This project implements a complete, production-quality **Distributed System Monitor** modeling a decentralized online food-delivery platform across **5 independent logical processes ($N=5$)**.

The system addresses the core challenges of distributed computing:
1. **Logical Time & Causality**: Implemented using **Vector Clocks ($N=5$)** from first principles to determine causal order ($e_a \to e_b$) and identify concurrency ($e_a \parallel e_b$) without relying on synchronized physical clocks.
2. **Global State Capture**: Implemented using the **Chandy-Lamport Distributed Snapshot Algorithm** for reliable FIFO channels to capture process local states and in-transit channel messages without pausing the distributed system.
3. **Causal Consistency Verification**: Evaluates captured global cuts to mathematically ensure the absence of orphan or post-snapshot messages.
4. **Cloud-Ready Architecture**: Designed with decoupled TCP socket communications dynamically configured via `config/hosts.cfg` for deployment across the **Prayogshala Cloud Lab**.

---

## 2. Distributed Process Model & Topology

The system models an online food delivery platform with 5 logical processes mapped across 3 Prayogshala cloud VM nodes:

```
                                +-----------------------------+
                                |      P0: Coordinator        |
                                |  (Central Order Processor)  |
                                +--------------+--------------+
                                               |
                     +-------------------------+-------------------------+
                     | ORDER / MARKER                                    | ORDER / MARKER
                     v                                                   v
        +-------------------------+                         +-------------------------+
        |  P1: Pizza Palace       |                         |  P2: Burger Hub         |
        |  (Restaurant A)         |                         |  (Restaurant B)         |
        +------------+------------+                         +------------+------------+
                     |                                                   |
                     | DELIVERY / MARKER                                 | DELIVERY / MARKER
                     v                                                   v
        +-------------------------+                         +-------------------------+
        |  P3: Fleet Runner A     |                         |  P4: Fleet Runner B     |
        |  (Delivery Partner 1)   |                         |  (Delivery Partner 2)   |
        +------------+------------+                         +------------+------------+
                     |                                                   |
                     +-------------------------+-------------------------+
                                               | STATE (Snapshot Reports)
                                               v
                                +-----------------------------+
                                |      P0: Coordinator        |
                                | (State Collection & Verify) |
                                +-----------------------------+
```

### Process Roles & Prayogshala Node Allocation

| Process ID | Name | Role & Responsibilities | Prayogshala Node | Port |
|---|---|---|---|---|
| **P0** (0) | `P0` | **Coordinator & Order Processor**: Creates orders, dispatches to P1/P2, initiates snapshots, collects `STATE` messages, and verifies consistency. | **Node 1** (`NODE1_IP`) | `5000` |
| **P1** (1) | `Pizza Palace` | **Restaurant A**: Receives orders from P0, logs internal prep events, and dispatches food-ready delivery jobs to P3. | **Node 2** (`NODE2_IP`) | `5001` |
| **P2** (2) | `Burger Hub` | **Restaurant B**: Receives orders from P0, logs internal prep events, and dispatches food-ready delivery jobs to P4. | **Node 2** (`NODE2_IP`) | `5002` |
| **P3** (3) | `Fleet Runner A` | **Delivery Partner 1**: Accepts delivery jobs from P1, logs pickup/transit events, delivers food, and reports state. | **Node 3** (`NODE3_IP`) | `5003` |
| **P4** (4) | `Fleet Runner B` | **Delivery Partner 2**: Accepts delivery jobs from P2, logs pickup/transit events, delivers food, and reports state. | **Node 3** (`NODE3_IP`) | `5004` |

---

## 3. Distributed Algorithms

### 3.1. Vector Clock Rules ($N=5$)

Each process $P_i$ maintains an integer array $V_i = [v_0, v_1, v_2, v_3, v_4]$, initialized to $[0, 0, 0, 0, 0]$.

1. **Internal Event**:
   $$V_i[i] \leftarrow V_i[i] + 1$$
2. **Send Event**:
   $$V_i[i] \leftarrow V_i[i] + 1$$
   Attach the snapshot of $V_i$ to the outgoing message.
3. **Receive Event**:
   Upon receiving message with timestamp $V_{\text{msg}}$:
   $$\forall k \in [0, 4]: V_i[k] \leftarrow \max(V_i[k], V_{\text{msg}}[k])$$
   $$V_i[i] \leftarrow V_i[i] + 1$$

---

### 3.2. Causal Ordering & Concurrency Proof

* **Happens-Before ($V_A \to V_B$)**:
  $$\forall k \in [0, 4]: V_A[k] \le V_B[k] \quad \land \quad \exists k: V_A[k] < V_B[k]$$
* **Concurrent ($V_A \parallel V_B$)**:
  $$\neg (V_A \to V_B) \quad \land \quad \neg (V_B \to V_A) \quad \land \quad V_A \ne V_B$$

#### Explicit Concurrency Demonstration
Consider two independent internal events occurring in parallel at Restaurant A (P1) and Restaurant B (P2) after receiving initial orders from P0:
* **Event $e_{\text{P1}}$ (Pizza Palace prepares dough)**: Clock $V_{\text{P1}} = [1, 2, 0, 0, 0]$
* **Event $e_{\text{P2}}$ (Burger Hub grills patty)**: Clock $V_{\text{P2}} = [1, 0, 2, 0, 0]$

**Evaluation:**
1. Check $V_{\text{P1}} \to V_{\text{P2}}$: At index 1, $V_{\text{P1}}[1] = 2 > V_{\text{P2}}[1] = 0 \implies \text{False}$.
2. Check $V_{\text{P2}} \to V_{\text{P1}}$: At index 2, $V_{\text{P2}}[2] = 2 > V_{\text{P1}}[2] = 0 \implies \text{False}$.
3. **Conclusion**: $V_{\text{P1}} \parallel V_{\text{P2}}$ (**Strictly Concurrent**).

---

### 3.3. Chandy-Lamport Global Snapshot Algorithm

The system implements the **Chandy-Lamport algorithm** over reliable FIFO TCP channels:

1. **Initiator ($P_0$) Rule**:
   * $P_0$ records its local process state and vector clock.
   * $P_0$ sends a `MARKER` message along all its outgoing channels ($P_0 \to P_1, P_0 \to P_2$).
   * $P_0$ begins recording in-transit messages on all incoming channels.
2. **Non-Initiator ($P_j$) Marker Receipt from $P_i$**:
   * **First Marker Receipt**:
     * $P_j$ records its own local process state and vector clock.
     * $P_j$ records the state of incoming channel $C_{i \to j}$ as **empty** (`[]`).
     * $P_j$ sends a `MARKER` message along all its outgoing channels.
     * $P_j$ starts recording incoming non-marker messages on all other incoming channels $C_{k \to j}$ ($k \ne i$).
     * $P_j$ transmits its `STATE` report back to coordinator $P_0$.
   * **Subsequent Marker Receipt along channel $C_{k \to j}$**:
     * $P_j$ stops recording on channel $C_{k \to j}$.
     * The captured state of channel $C_{k \to j}$ contains all messages received on that channel since $P_j$ recorded its state.
3. **Global Consistency Verification**:
   * When $P_0$ receives `STATE` messages from all 5 processes, it checks that:
     $$\forall i, j: V_i[j] \le V_j[j]$$
   * This mathematically verifies that no recorded process state depends on events that occurred after the target process took its snapshot cut.

---

## 4. Message Wire Protocol

All inter-process communication uses structured JSON over dedicated TCP socket streams:

### 1. Customer Order Message (`ORDER`)
```json
{
  "type": "ORDER",
  "from": "P0",
  "to": "P1",
  "payload": {
    "order_id": 101,
    "item": "Margherita Pizza"
  },
  "clock": [2, 0, 0, 0, 0]
}
```

### 2. Delivery Dispatch Message (`DELIVERY`)
```json
{
  "type": "DELIVERY",
  "from": "P1",
  "to": "P3",
  "payload": {
    "order_id": 101,
    "item": "Margherita Pizza",
    "restaurant": "Pizza Palace"
  },
  "clock": [2, 5, 0, 0, 0]
}
```

### 3. Snapshot Marker Message (`MARKER`)
```json
{
  "type": "MARKER",
  "snapshot_id": "SNAPSHOT_1",
  "from": "P0",
  "clock": [4, 0, 0, 0, 0]
}
```

### 4. Process State Report Message (`STATE`)
```json
{
  "type": "STATE",
  "snapshot_id": "SNAPSHOT_1",
  "from": "P1",
  "data": {
    "process": "P1",
    "vector_clock": [2, 3, 0, 0, 0],
    "local_state": "Preparing food"
  },
  "channel_state": {
    "P0": []
  },
  "clock": [2, 6, 0, 0, 0]
}
```

---

## 5. Project Directory Structure

```
bits-food-delivery/
├── config/
│   └── hosts.cfg               # Node IP mappings and process port configurations
├── src/
│   ├── p0.py                   # Coordinator & Central Order Processor
│   ├── p1.py                   # Restaurant A (Pizza Palace)
│   ├── p2.py                   # Restaurant B (Burger Hub)
│   ├── p3.py                   # Delivery Partner 1 (Fleet Runner A)
│   ├── p4.py                   # Delivery Partner 2 (Fleet Runner B)
│   ├── snapshot.py             # Chandy-Lamport Snapshot Engine & Channel Recording
│   └── vector_clock.py         # Thread-safe Vector Clock Implementation
├── tests/
│   ├── test_vector_clock.py    # 9 Unit tests for Vector Clock operations
│   └── test_p0_integration.py  # End-to-end P0 socket dispatch & snapshot test
├── BUG-REPORTS.md              # Complete bug audit & resolution documentation
├── requirements.txt            # Python dependencies (colorama, flask)
└── README.md                   # System documentation & evaluation guide
```

---

## 6. Installation & Setup

### Prerequisites
* Python 3.10+
* Git

```bash
# Clone the repository
git clone https://github.com/kashifxyz/bits-food-delivary-distributed-computing-assignment.git
cd bits-food-delivary-distributed-computing-assignment

# Create virtual environment and install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 7. How to Run & Demonstration Guide

### 7.1. Single-Machine Local Demonstration (5 Separate Terminals)

Open 5 terminal windows and start the processes in reverse order (listeners first):

```bash
# Terminal 1 — Delivery Partners
python src/p3.py &
python src/p4.py &

# Terminal 2 — Restaurant A & B
python src/p1.py &
python src/p2.py &

# Terminal 3 — Central Processor / Coordinator
python src/p0.py
```

#### Running the Automated Demo Flow:
In Terminal 3, run:
```bash
python src/p0.py --auto
```
**Demonstration Sequence:**
1. **Order 101 Dispatched**: P0 dispatches "Margherita Pizza" to P1 (Clock: `[2, 0, 0, 0, 0]`).
2. **Order 102 Dispatched**: P0 dispatches "Double Cheeseburger" to P2 (Clock: `[4, 0, 0, 0, 0]`).
3. **Mid-Flight Snapshot (`SNAPSHOT_1`)**: P0 initiates snapshot while kitchens are preparing food in parallel.
4. **State Collection & Consistency Verification**: P0 collects state reports from P0, P1, P2, P3, P4 and proves causal consistency.
5. **Post-Completion Snapshot (`SNAPSHOT_2`)**: Captures final system state after deliveries complete.

---

### 7.2. Multi-Node Prayogshala Cloud Lab Deployment

1. Edit [config/hosts.cfg](file:///Users/kashif/codemill/bits/bits-food-delivary-distributed-computing-assignment/config/hosts.cfg) with your node IPs:
   ```ini
   [nodes]
   NODE1_IP=10.0.1.10
   NODE2_IP=10.0.1.11
   NODE3_IP=10.0.1.12
   ```

2. **On Node 3 (Delivery Partners)**:
   ```bash
   python src/p3.py &
   python src/p4.py
   ```

3. **On Node 2 (Restaurants)**:
   ```bash
   python src/p1.py &
   python src/p2.py
   ```

4. **On Node 1 (Central Processor & Coordinator)**:
   ```bash
   python src/p0.py --auto
   ```

---

## 8. Test Cases & Verification Matrix

The test suite validates all requirements specified in the assignment:

| Test ID | Test Name | Purpose | Actions & Inputs | Expected Result | Status |
|---|---|---|---|---|---|
| **TC01** | Initial Clock State | Verify vector clock zero initialization | Initialize `VectorClock(0, 5)` | Clock is `[0, 0, 0, 0, 0]` | ✅ **PASS** |
| **TC02** | Local Increment | Verify process component tick | Call `vc.increment()` twice | Clock slot increments: `1`, `2` | ✅ **PASS** |
| **TC03** | Send Event | Verify send event advances clock and returns copy | Call `vc.send_event()` | Local clock increments, attached to message | ✅ **PASS** |
| **TC04** | Receive Event | Verify causal merge rule $\max(L, R) + 1$ | `vc1.receive_event(clock0)` | Merges P0 timestamp and increments P1 slot | ✅ **PASS** |
| **TC05** | Internal Event | Verify internal state transition logging | Call `vc.internal_event(...)` | Local clock increments independently | ✅ **PASS** |
| **TC06** | Concurrent Event Detection | Verify detection of independent events | Compare $V_{\text{P1}} = [1, 2, 0, 0, 0]$ vs $V_{\text{P2}} = [1, 0, 2, 0, 0]$ | `is_concurrent(...) == True` | ✅ **PASS** |
| **TC07** | Non-Concurrent Causality | Verify happens-before causal chains | Compare $V_{\text{P0}} = [1, 0, 0, 0, 0]$ vs $V_{\text{P1}} = [1, 1, 0, 0, 0]$ | `is_concurrent(...) == False` ($P0 \to P1$) | ✅ **PASS** |
| **TC08** | Full Order Causal Flow | Verify end-to-end vector clock propagation ($P0 \to P1 \to P3$) | Full lifecycle execution | P3 knows P0 sent 1 msg, P1 had $\ge 4$ events | ✅ **PASS** |
| **TC09** | Thread Safety | Verify synchronization under concurrency | 5 concurrent threads executing 100 increments each | Final clock component equals exactly `500` | ✅ **PASS** |
| **TC10** | Chandy-Lamport Snapshot & Consistency | Verify global cut capture & consistency check | Trigger snapshot during active order flow | All process states collected; snapshot verified consistent | ✅ **PASS** |

### Running the Test Suite
```bash
# Run Vector Clock Unit Tests
python tests/test_vector_clock.py

# Run Socket Integration & Snapshot Tests
python tests/test_p0_integration.py
```

---

## 9. 5–10 Minute Presentation Demonstration Flow

When demonstrating this project to the evaluator:

1. **Step 1: Introduction & Architecture (1 min)**:
   * Explain the 5 processes ($P0 \dots P4$), their roles, and multi-node mapping.
2. **Step 2: Vector Clock Verification (2 mins)**:
   * Run `python tests/test_vector_clock.py` to show all 9 causal ordering and thread-safety tests passing.
3. **Step 3: Live Order Dispatch & Event Progression (2 mins)**:
   * Launch `src/p0.py` and dispatch Order 101 to P1.
   * Observe Terminal outputs displaying internal events: `Order confirmed` $\to$ `Preparing food` $\to$ `Food ready` $\to$ `DELIVERY -> P3`.
4. **Step 4: Concurrent Event Proof (1.5 mins)**:
   * Show P1 and P2 preparing orders simultaneously, and demonstrate that their vector clocks ($[1, 2, 0, 0, 0]$ and $[1, 0, 2, 0, 0]$) are evaluated as **CONCURRENT**.
5. **Step 5: Chandy-Lamport Global Snapshot & Consistency (2 mins)**:
   * Trigger `SNAPSHOT_1` from P0.
   * Highlight marker propagation across channels, local process state capture, and channel state recording.
   * Show the printed **Global Snapshot Report** and the **Causal Consistency Verification** output.

---

## 10. Team Member Contribution Table

| Member Name | Student ID *(Placeholder)* | Role / Assigned Component | Key Contributions |
|---|---|---|---|
| **Shaik Baleeghuddin Kashif** | `202X-XX-XXXX` | `src/p0.py` (Central Order Processor & Coordinator) | Order creation & dispatching, Chandy-Lamport snapshot initiation, state collection from all 5 processes, consistency evaluation, concurrency analysis, and integration testing. |
| **Vinjanampati Sri Harsha** | `202X-XX-XXXX` | `src/p1.py`, `src/p2.py` (Restaurants) | Order confirmation, food preparation internal events, delivery dispatching to P3/P4, and marker forwarding. |
| **Nerella Chandra Hasitha** | `202X-XX-XXXX` | `src/p3.py`, `src/p4.py` (Delivery Partners) | Delivery job acceptance, transit internal events, delivery completion, and state reporting to P0. |
| **Abhirup Bhattacharjee** | `202X-XX-XXXX` | `src/snapshot.py` (Snapshot Algorithm) | Chandy-Lamport snapshot algorithm implementation, marker creation, local state recording, and channel state recording. |
| **Sohail Quazi** | `202X-XX-XXXX` | Infrastructure & Cloud Setup | Provisioning Prayogshala cloud VM nodes, network routing, and host configuration (`config/hosts.cfg`). |

---

## 11. References & Bug Audit Log

* For complete details on the code audit, edge-case fixes, and socket reliability improvements, see [BUG-REPORTS.md](file:///Users/kashif/codemill/bits/bits-food-delivary-distributed-computing-assignment/BUG-REPORTS.md).
* **Distributed Computing Principles**:
  * K. Mani Chandy and Leslie Lamport, *"Distributed Snapshots: Determining Global States of Distributed Systems"*, ACM Transactions on Computer Systems (TOCS), 1985.
  * Colin Fidge, *"Timestamps in Message-Ordering Systems"*, Proceedings of the 11th Australian Computer Science Conference, 1988.
