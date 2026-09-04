# Chandy-Lamport Distributed Snapshot & Consistency

**Algorithm Specification, Marker Propagation, Channel Recording, and Consistency Verification**

---

## 1. Problem Definition

In a distributed food delivery system, orders move across multiple processes and in-transit network channels simultaneously. Capturing a **Globally Consistent Snapshot** requires recording:
1. The **local state** of every process at a specific logical cut.
2. The **channel state** (messages in transit) along all directed communication channels.
3. Guaranteeing that the captured global cut contains no **orphan messages** (a message recorded as received whose send event was not recorded) or **future dependencies**.

---

## 2. Chandy-Lamport Algorithm Rules

### 2.1. Snapshot Initiation (by Coordinator $P_0$)
1. $P_0$ records its local process state (active orders, order status) and local Vector Clock $V_0$.
2. $P_0$ emits a `MARKER(snapshot_id)` message along all outgoing channels ($P_0 \to P_1, P_0 \to P_2$).
3. $P_0$ initiates channel recording on all incoming channels.

---

### 2.2. Marker Reception Rules at Process $P_j$ from Sender $P_i$

#### Case 1: First Marker Received
If process $P_j$ has **not yet recorded** its local state for `snapshot_id`:
1. $P_j$ records its own local process state and Vector Clock $V_j$.
2. $P_j$ marks the incoming channel $C_{i \to j}$ as **empty** (`[]`).
3. $P_j$ sends a `MARKER(snapshot_id)` along all its outgoing channels ($P_j \to P_k$).
4. $P_j$ begins recording all non-marker messages arriving on any other incoming channel $C_{u \to j}$ ($u \ne i$).
5. $P_j$ transmits its captured state report (`STATE`) back to Coordinator $P_0$.

#### Case 2: Subsequent Marker Received
If process $P_j$ has **already recorded** its state for `snapshot_id`:
1. $P_j$ stops recording on channel $C_{i \to j}$.
2. The final recorded state of channel $C_{i \to j}$ consists of all messages received on that channel between $P_j$'s state recording and this marker's arrival.

---

## 3. Global Cut Consistency Verification

Once Coordinator $P_0$ receives `STATE` reports from all $N = 5$ processes ($P_0, P_1, P_2, P_3, P_4$), it evaluates causal consistency across all pairs of recorded process vector clocks $(V_A, V_B)$:

$$\forall A, B \in \{P_0, P_1, P_2, P_3, P_4\}: \quad V_A[B] \le V_B[B]$$

### Inconsistency Condition:
If $V_A[B] > V_B[B]$, then process $A$'s snapshot state contains knowledge of an event generated at process $B$ that occurred *after* process $B$ took its snapshot cut. This would constitute an inconsistent cut (orphan message / causality violation).

When $V_A[B] \le V_B[B]$ holds for all pairs, the captured global state is mathematically guaranteed to be **Causally Consistent**.

---

## 4. Execution Cuts in the Food Delivery Scenario

### Snapshot 1: Mid-Execution Cut (`SNAPSHOT_1`)
* **Timing**: Triggered by $P_0$ while restaurants $P_1$ and $P_2$ are actively preparing meals.
* **Captured Cut**:
  * $P_0$: Active orders dispatched.
  * $P_1$: State = `PREPARING` / `FOOD_READY`, Clock = `[6, 6, 0, 0, 0]`
  * $P_2$: State = `PREPARING`, Clock = `[7, 0, 4, 0, 0]`
  * $P_3$: State = `PICKED_UP`, Clock = `[6, 7, 0, 4, 0]`
  * $P_4$: State = `WAITING_FOR_ORDER`, Clock = `[7, 0, 5, 0, 2]`
* **Evaluation**: **CAUSALLY CONSISTENT** ($V_i[j] \le V_j[j]$ for all $i, j$).

### Snapshot 2: Post-Fulfillment Cut (`SNAPSHOT_2`)
* **Timing**: Triggered by $P_0$ following order completion.
* **Captured Cut**:
  * $P_0$: All orders marked `DELIVERED`.
  * $P_1, P_2$: Kitchens idle (`Current state of P1/P2`).
  * $P_3, P_4$: Delivery fleets marked `Status: DELIVERED`.
* **Evaluation**: **CAUSALLY CONSISTENT** (Complete terminal cut).
