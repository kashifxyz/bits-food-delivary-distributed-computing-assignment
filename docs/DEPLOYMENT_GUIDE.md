# Multi-Node Cloud Deployment Guide

**Prayogshala Cloud Lab & Localhost Multi-Terminal Deployment**

---

## 1. Prayogshala Cloud Lab Node Topology

The system is deployed across 3 distributed Linux virtual machine nodes:

```
+---------------------------+       +---------------------------+       +---------------------------+
|          Node 1           |       |          Node 2           |       |          Node 3           |
|         (master)          |       |          (slave1)         |       |          (slave2)         |
|  IP: NODE1_IP             |       |  IP: NODE2_IP             |       |  IP: NODE3_IP             |
|                           |       |                           |       |                           |
|  - P0 (Port 5005)         |       |  - P1 (Port 5001)         |       |  - P3 (Port 5003)         |
|    Coordinator & Orders   |       |    Restaurant A           |       |    Delivery Partner 1     |
|                           |       |  - P2 (Port 5002)         |       |  - P4 (Port 5004)         |
|                           |       |    Restaurant B           |       |    Delivery Partner 2     |
+---------------------------+       +---------------------------+       +---------------------------+
```

---

## 2. Configuration Setup (`config/hosts.cfg`)

Before launching on Prayogshala, update [config/hosts.cfg](file:///Users/kashif/codemill/bits/bits-food-delivary-distributed-computing-assignment/config/hosts.cfg) with the assigned node IPs:

```ini
[nodes]
NODE1_IP=10.0.1.10
NODE2_IP=10.0.1.11
NODE3_IP=10.0.1.12

[ports]
P0_PORT=5005
P1_PORT=5001
P2_PORT=5002
P3_PORT=5003
P4_PORT=5004

[process_hosts]
P0_HOST=NODE1_IP
P1_HOST=NODE2_IP
P2_HOST=NODE2_IP
P3_HOST=NODE3_IP
P4_HOST=NODE3_IP
```

---

## 3. Step-by-Step Deployment Instructions

### Step 1: Clone Repository on All 3 Nodes
```bash
git clone https://github.com/kashifxyz/bits-food-delivary-distributed-computing-assignment.git
cd bits-food-delivary-distributed-computing-assignment
pip install -r requirements.txt
```

### Step 2: Start Delivery Partners (Node 3 — slave2)
```bash
python src/p3.py &
python src/p4.py &
```

### Step 3: Start Restaurants (Node 2 — slave1)
```bash
python src/p1.py &
python src/p2.py &
```

### Step 4: Start Coordinator & Automated Demo (Node 1 — master)
```bash
python src/p0.py --auto
```

---

## 4. Localhost Single-Machine Testing (5 Terminals)

To run the full multi-process system locally:

```bash
# Terminal 1 — Delivery Partner 1
python src/p3.py

# Terminal 2 — Delivery Partner 2
python src/p4.py

# Terminal 3 — Restaurant A (Pizza Palace)
python src/p1.py

# Terminal 4 — Restaurant B (Burger Hub)
python src/p2.py

# Terminal 5 — Coordinator (Central Order Processor)
python src/p0.py --auto
```

Or run the automated single-script verification:
```bash
python tests/test_full_system.py
```

---

## 5. Troubleshooting & FAQ

| Symptom | Cause | Solution |
|---|---|---|
| `[Errno 48] Address already in use` (Port 5000) | macOS AirPlay Receiver occupies port 5000. | `P0` automatically binds to `5005` as configured in `hosts.cfg`. Alternatively, disable AirPlay in macOS Settings. |
| `[Errno 61] Connection refused` | Downstream listener process is not yet running. | Always launch processes in bottom-up order: Delivery Partners (`P3`, `P4`) $\to$ Restaurants (`P1`, `P2`) $\to$ Coordinator (`P0`). |
| `Permission denied` / Firewall block on Prayogshala | UFW or iptables blocking ports 5001–5005. | Allow ports on Linux: `sudo ufw allow 5000:5005/tcp`. |
