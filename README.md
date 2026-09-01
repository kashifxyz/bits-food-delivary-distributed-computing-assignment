# Distributed Food Delivery System — Distributed System Monitor
**Tracking Events, Vector Clocks, and Capturing Global State (Chandy-Lamport)**

---

## 1. Project Overview

This project is a comprehensive Distributed System Monitor modeling an online food-delivery platform with four independent distributed processes:
* **P1 — Order Processor**: Coordinates order lifecycles, dispatches requests, and tracks final delivery statuses.
* **P2 — Restaurant A**: Receives food orders, transitions through kitchen preparation, and dispatches food-ready notifications.
* **P3 — Delivery Partner**: Accepts delivery tasks, executes physical pickup, and confirms completion.
* **P4 — Restaurant B (Independent)**: Operates independently to generate concurrent and decoupled distributed events.

The system features:
1. **Mathematical Vector Clocks ($N=4$)** implemented from first principles to establish causal precedence ($e_a \to e_b$) and identify concurrency ($e_a \parallel e_b$).
2. **Chandy-Lamport Global Snapshot Algorithm** for reliable FIFO channels, recording local process states and in-transit flying messages.
3. **Causal Consistency Verification Engine** that mathematically validates global cuts against orphan and post-snapshot causal anomalies.
4. **Interactive React + TypeScript Dashboard** featuring live WebSocket streaming, network topology graph, interactive vector clock comparator, and scenario simulation controls.

---

## 2. Architecture & Topology

```
                                +-----------------------------------+
                                |  React + TypeScript UI (Vite)     |
                                |  Port: 5173                       |
                                +-----------------+-----------------+
                                                  |
                                  REST APIs (HTTP)| WebSocket (/ws/events)
                                                  v
+-------------------------------------------------------------------------------------------------+
|                                 FastAPI Backend Server (Port: 8000)                             |
|                                                                                                 |
|   +-----------------------------------------------------------------------------------------+   |
|   | APIs: /api/processes, /api/orders, /api/events, /api/snapshots, /api/scenarios          |   |
|   +--------------------------------------------+--------------------------------------------+   |
|                                                |                                                |
|   +--------------------------------------------v--------------------------------------------+   |
|   | Services: ProcessService, OrderService, EventService, SnapshotService                   |   |
|   +--------------------------------------------+--------------------------------------------+   |
|                                                |                                                |
|   +--------------------------------------------v--------------------------------------------+   |
|   | Distributed Core Engine:                                                                |   |
|   | - ProcessManager (coordinates lifecycle, async listeners, and routing)                  |   |
|   | - SnapshotManager (Chandy-Lamport distributed snapshot coordinator)                     |   |
|   | - ConsistencyChecker (validates causal consistency & channel invariants)               |   |
|   | - EventManager (global causal event log and observer dispatcher)                        |   |
|   | - MessageBus: Directed FIFO Channels (C_ij) between all logical nodes (1-4)             |   |
|   |                                                                                         |   |
|   | Logical Independent Distributed Processes:                                              |   |
|   |   + P1 (Order Processor)         Vector Clock: [c1, c2, c3, c4]                         |   |
|   |   + P2 (Restaurant A)            Vector Clock: [c1, c2, c3, c4]                         |   |
|   |   + P3 (Delivery Partner)        Vector Clock: [c1, c2, c3, c4]                         |   |
|   |   + P4 (Restaurant B)            Vector Clock: [c1, c2, c3, c4]                         |   |
|   +-----------------------------------------------------------------------------------------+   |
+-------------------------------------------------------------------------------------------------+
```

---

## 3. Technology Stack

* **Backend**: Python 3.11+, FastAPI, Uvicorn, Pydantic v2, WebSockets, Pytest, AsyncIO.
* **Frontend**: React 19, TypeScript (TSX), Vite, Lucide Icons, Custom CSS Theme.
* **Communication Layer**: Directed FIFO Channels with In-Transit Buffering (Local Asynchronous Bus / Extensible to TCP Network Bus).

---

## 4. Installation & Setup

### Prerequisites
* Python 3.11+
* Node.js 18+ and `pnpm` (or `npm`)

### Backend Setup
```bash
python3 -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements.txt
```

### Frontend Setup
```bash
cd frontend
pnpm install
```

---

## 5. Running the Application

### Option A: Run All with One Script
```bash
./scripts/start_all.sh
```
* **Frontend**: [http://localhost:5173](http://localhost:5173)
* **Backend API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

### Option B: Run Individually
* **Backend**:
  ```bash
  ./scripts/start_backend.sh
  ```
* **Frontend**:
  ```bash
  ./scripts/start_frontend.sh
  ```

### Option C: Run with Docker Compose
```bash
docker compose up --build
```

---

## 6. Running Tests

Execute the automated test suite covering vector clocks, channel FIFO queues, snapshot recording, consistency checking, and multi-process scenarios:
```bash
# Run all tests
make test

# Or run unit tests specifically
PYTHONPATH=. backend/.venv/bin/pytest backend/tests/unit/ -v

# Or run integration tests specifically
PYTHONPATH=. backend/.venv/bin/pytest backend/tests/integration/ -v
```

---

## 7. Deterministic Test Scenarios

The system includes 5 built-in scenarios:
1. **TC01 — Basic Order Flow**: Executes full order progression $P1 \to P2 \to P3 \to P1$ with vector clock updates across send/receive/internal events.
2. **TC02 — Vector Clock Progression**: Verifies exact mathematical updates ($L[k] = \max(L[k], R[k])$ and $L[i] += 1$).
3. **TC03 — Deterministic Concurrent Events**: Generates independent events at $P2$ and $P4$ and proves causal concurrency ($e_A \parallel e_B$).
4. **TC04 — In-Transit Message Snapshot**: Dispatches an in-flight message and records it in the channel state during a Chandy-Lamport snapshot.
5. **TC05 — Complete Global Snapshot**: Captures a full 4-process, 12-channel consistent global state cut.

---

## 8. REST & WebSocket API Documentation

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/processes` | List all 4 processes, vector clocks, and local states |
| `GET` | `/api/processes/{id}` | Get state of specific process |
| `POST` | `/api/processes/reset` | Reset distributed processes and clear history |
| `GET` | `/api/events` | Query event history (supports `process_id` & `order_id` filters) |
| `GET` | `/api/events/compare` | Evaluate causal relation between `event_a` and `event_b` |
| `GET` | `/api/orders` | List customer orders |
| `POST` | `/api/orders` | Create a new food delivery order |
| `POST` | `/api/snapshots` | Initiate Chandy-Lamport snapshot |
| `GET` | `/api/snapshots` | List recorded global snapshots |
| `GET` | `/api/snapshots/{id}/consistency` | Verify causal consistency of snapshot |
| `GET` | `/api/scenarios` | List available deterministic scenarios |
| `POST` | `/api/scenarios/{id}/run` | Execute deterministic scenario |
| `WS` | `/ws/events` | Real-time WebSocket event broadcaster |

---

## 9. Cloud Deployment Readiness

The processes communicate using the `MessageBus` abstraction and load addresses dynamically from `config/processes.json` and `config/network.json`. To deploy across distinct cloud nodes:
1. Update `config/processes.json` with target node IPs and open ports.
2. The `MessageBus` layer seamlessly swaps `LocalMessageBus` with a TCP/socket based network bus without altering core process logic.
