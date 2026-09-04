# System Architecture & Event Flow Specification

**Project:** Distributed System Monitor — Food Delivery Platform  
**Target:** 5 Distributed Processes ($N=5$) over Multi-Node Cloud Lab / Localhost

---

## 1. Process Roles & State Machines

The distributed system consists of 5 logical processes communicating strictly via TCP socket exchanges with causal Vector Clocks.

```
+---------------------------------------------------------------------------------------------------+
|                                      P0: Central Coordinator                                      |
|  - Creates Orders #101 & #102                                                                     |
|  - Dispatches to Restaurants P1 & P2                                                              |
|  - Triggers Chandy-Lamport Snapshots (SNAPSHOT_1, SNAPSHOT_2)                                      |
|  - Collects STATE messages from P0, P1, P2, P3, P4 and verifies Causal Consistency                |
+-------------------------------------------------+-------------------------------------------------+
                                                  |
                         +------------------------+------------------------+
                         | ORDER #101                                      | ORDER #102
                         v                                                 v
+--------------------------------------------------+ +--------------------------------------------------+
|            P1: Pizza Palace (Restaurant A)       | |             P2: Burger Hub (Restaurant B)        |
|  - State: WAITING -> CONFIRMED -> PREPARING ->   | |  - State: WAITING -> CONFIRMED -> PREPARING ->   |
|           FOOD_READY                             | |           FOOD_READY                             |
|  - Dispatches DELIVERY to P3                     | |  - Dispatches DELIVERY to P4                     |
|  - Forwards MARKER to P3; reports STATE to P0    | |  - Forwards MARKER to P4; reports STATE to P0    |
+------------------------+-------------------------+ +------------------------+-------------------------+
                         |                                                 |
                         | DELIVERY #101                                   | DELIVERY #102
                         v                                                 v
+--------------------------------------------------+ +--------------------------------------------------+
|           P3: Fleet Runner A (Delivery 1)        | |           P4: Fleet Runner B (Delivery 2)        |
|  - State: WAITING -> PICKED_UP -> IN_TRANSIT ->  | |  - State: WAITING -> PICKED_UP -> IN_TRANSIT ->  |
|           DELIVERED                              | |           DELIVERED                              |
|  - Reports DELIVERY completion to P0             | |  - Reports DELIVERY completion to P0             |
|  - Leaf Node: Reports STATE to P0                | |  - Leaf Node: Reports STATE to P0                |
+------------------------+-------------------------+ +------------------------+-------------------------+
                         |                                                 |
                         +------------------------+------------------------+
                                                  | STATE & DELIVERY Messages
                                                  v
                                      +-----------------------+
                                      |     P0: Coordinator   |
                                      +-----------------------+
```

---

## 2. Event Progression & Event Types

Every state change in the system generates a formal distributed event classified into three standard categories:

| Process | Event Description | Event Type | Vector Clock Update Rule |
|---|---|---|---|
| **P0** | Create Customer Order #101 | **Internal Event** | $V_0[0] \leftarrow V_0[0] + 1$ |
| **P0** | Dispatch Order #101 to P1 | **Send Event** | $V_0[0] \leftarrow V_0[0] + 1$; attach $V_0$ to message |
| **P1** | Receive Order #101 from P0 | **Receive Event** | $\forall k: V_1[k] \leftarrow \max(V_1[k], V_{\text{msg}}[k])$; $V_1[1] \leftarrow V_1[1] + 1$ |
| **P1** | "Order confirmed" | **Internal Event** | $V_1[1] \leftarrow V_1[1] + 1$ |
| **P1** | "Preparing food" | **Internal Event** | $V_1[1] \leftarrow V_1[1] + 1$ |
| **P1** | "Food ready for pickup" | **Internal Event** | $V_1[1] \leftarrow V_1[1] + 1$ |
| **P1** | Dispatch DELIVERY to P3 | **Send Event** | $V_1[1] \leftarrow V_1[1] + 1$; attach $V_1$ to message |
| **P3** | Receive Delivery handoff | **Receive Event** | $\forall k: V_3[k] \leftarrow \max(V_3[k], V_{\text{msg}}[k])$; $V_3[3] \leftarrow V_3[3] + 1$ |
| **P3** | "Order picked up from P1" | **Internal Event** | $V_3[3] \leftarrow V_3[3] + 1$ |
| **P3** | "Order in transit" | **Internal Event** | $V_3[3] \leftarrow V_3[3] + 1$ |
| **P3** | "Order delivered to customer" | **Internal Event** | $V_3[3] \leftarrow V_3[3] + 1$ |
| **P3** | Send DELIVERY confirmation to P0 | **Send Event** | $V_3[3] \leftarrow V_3[3] + 1$; attach $V_3$ to message |
| **P0** | Receive delivery confirmation | **Receive Event** | $\forall k: V_0[k] \leftarrow \max(V_0[k], V_{\text{msg}}[k])$; $V_0[0] \leftarrow V_0[0] + 1$ |

*(An identical symmetric flow occurs for Order #102: $P0 \to P2 \to P4 \to P0$).*

---

## 3. Communication Channel Invariants

1. **FIFO Order**: TCP streams guarantee that messages along any directed channel $C_{i \to j}$ arrive in the exact order they were transmitted.
2. **One-Shot TCP Connections**: To prevent socket leaks across distributed VMs, messages are transmitted as newline-terminated JSON payloads over short-lived TCP connections.
3. **Dynamic Topology Configuration**: Process endpoints are resolved at runtime via `config/hosts.cfg`:
   * `P0` binds to port `5005` (Node 1)
   * `P1` binds to port `5001` (Node 2)
   * `P2` binds to port `5002` (Node 2)
   * `P3` binds to port `5003` (Node 3)
   * `P4` binds to port `5004` (Node 3)
