# Vector Clocks & Causal Ordering

**Theory, Mathematical Specification, and Concurrency Analysis**

---

## 1. Mathematical Foundations

In a distributed system without shared memory or a global physical clock, **Vector Clocks** (Mattern / Fidge, 1988) establish a strict partial ordering ($\to$, *happens-before*) across distributed events.

### Vector Clock Representation
For a system of $N = 5$ processes ($P_0, P_1, P_2, P_3, P_4$), each process $P_i$ maintains an integer vector:
$$V_i = [V_i[0], V_i[1], V_i[2], V_i[3], V_i[4]]$$
where $V_i[j]$ represents $P_i$'s knowledge of the logical time (event counter) at process $P_j$.

---

## 2. Transition & Update Rules

1. **Initialization**:
   $$\forall i, j \in [0, 4]: V_i[j] = 0$$
2. **Rule 1 (Internal Event on $P_i$)**:
   Before generating an internal event:
   $$V_i[i] \leftarrow V_i[i] + 1$$
3. **Rule 2 (Send Event on $P_i$ to $P_j$)**:
   Before sending a message $m$:
   $$V_i[i] \leftarrow V_i[i] + 1$$
   $$m.\text{clock} \leftarrow V_i$$
4. **Rule 3 (Receive Event on $P_j$ from $P_i$)**:
   Upon receiving message $m$ with timestamp $m.\text{clock}$:
   $$\forall k \in [0, 4]: V_j[k] \leftarrow \max(V_j[k], m.\text{clock}[k])$$
   $$V_j[j] \leftarrow V_j[j] + 1$$

---

## 3. Causal Relationship Definitions

Let $e_A$ and $e_B$ be two events with vector timestamps $V(e_A)$ and $V(e_B)$:

* **Strong Causal Precedence ($e_A \to e_B$)**:
  $$e_A \to e_B \iff \Big( \forall k: V(e_A)[k] \le V(e_B)[k] \Big) \land \Big( \exists k: V(e_A)[k] < V(e_B)[k] \Big)$$

* **Concurrency ($e_A \parallel e_B$)**:
  $$e_A \parallel e_B \iff \neg(e_A \to e_B) \land \neg(e_B \to e_A) \land V(e_A) \ne V(e_B)$$
  Equivalently:
  $$e_A \parallel e_B \iff \Big( \exists u: V(e_A)[u] > V(e_B)[u] \Big) \land \Big( \exists w: V(e_A)[w] < V(e_B)[w] \Big)$$

---

## 4. Concrete System Execution Traces

### 4.1. Direct Causal Chain ($P_0 \to P_1 \to P_3$)
```
P0 (Send Order)      -> [2, 0, 0, 0, 0]
P1 (Recv Order)      -> [2, 1, 0, 0, 0]
P1 (Prep Food)       -> [2, 3, 0, 0, 0]
P1 (Send Delivery)   -> [2, 5, 0, 0, 0]
P3 (Recv Delivery)   -> [2, 5, 0, 1, 0]
P3 (Delivered)       -> [2, 5, 0, 4, 0]
```
* **Evaluation**: $V(P0) \le V(P1) \le V(P3)$. This satisfies $e_{P0} \to e_{P1} \to e_{P3}$ (**Causally Ordered**).

### 4.2. Independent Concurrent Execution ($P_1 \parallel P_2$)
During parallel kitchen preparations:
* Event $e_{P1}$ (Pizza Palace baking): $V(e_{P1}) = [2, 3, 0, 0, 0]$
* Event $e_{P2}$ (Burger Hub grilling): $V(e_{P2}) = [4, 0, 3, 0, 0]$

**Proof of Concurrency**:
1. At index 1: $V(e_{P1})[1] = 3 > V(e_{P2})[1] = 0 \implies \neg(e_{P1} \to e_{P2})$
2. At index 0: $V(e_{P1})[0] = 2 < V(e_{P2})[0] = 4 \implies \neg(e_{P2} \to e_{P1})$
3. Therefore: $e_{P1} \parallel e_{P2}$ (**Concurrent**).

---

## 5. Thread-Safe Implementation

In `src/vector_clock.py`, vector clocks are guarded by reentrant synchronization locks (`threading.Lock`) to prevent race conditions during concurrent message processing and timer-driven snapshot events.
