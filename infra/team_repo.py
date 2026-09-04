"""
team_repo.py — Locate and read the team's application repository.
Owner: Sohail (Infrastructure)

The five process files (p0.py .. p4.py), the vector clock and the snapshot
module live in a SEPARATE repository owned by the rest of the team. Every
tool in this repo reads that checkout but never writes to its source files.

Resolution order for the team checkout:
    1. --repo <path> passed on the command line
    2. $DC_TEAM_REPO
    3. the current working directory, if it looks like the team repo
    4. siblings of this repo, and the usual spots under $HOME

Pure standard library. No third-party imports anywhere in this file.
"""

import configparser
import os

# Ports the team's config ships with. Used only when hosts.cfg is missing
# or unreadable; hosts.cfg always wins when it is present.
FALLBACK_PORTS = {"P0": 5005, "P1": 5001, "P2": 5002, "P3": 5003, "P4": 5004}

PROCESS_NAMES = ["P0", "P1", "P2", "P3", "P4"]

# Which node each process belongs to, per the team's config/hosts.cfg.
PROCESS_NODE = {
    "P0": "NODE1_IP",
    "P1": "NODE2_IP",
    "P2": "NODE2_IP",
    "P3": "NODE3_IP",
    "P4": "NODE3_IP",
}

NODE_KEYS = ["NODE1_IP", "NODE2_IP", "NODE3_IP"]

NODE_LABEL = {
    "NODE1_IP": "node1  Master — Central Coordinator",
    "NODE2_IP": "node2  Slave 1 — Restaurants",
    "NODE3_IP": "node3  Slave 2 — Delivery Partners",
}

ROLE = {
    "P0": "Central Order Processor",
    "P1": "Restaurant A — Pizza Palace",
    "P2": "Restaurant B — Burger Hub",
    "P3": "Delivery Partner 1 — Fleet Runner A",
    "P4": "Delivery Partner 2 — Fleet Runner B",
}

# Application message channels, as implemented by the team's code.
# Used by the analyser to reason about the snapshot cut.
CHANNELS = [("P0", "P1"), ("P0", "P2"), ("P1", "P3"), ("P2", "P4"),
            ("P3", "P0"), ("P4", "P0")]

HERE = os.path.dirname(os.path.abspath(__file__))


class TeamRepoError(RuntimeError):
    """Raised when the team's application repository cannot be located."""


def _looks_like_team_repo(path):
    """A directory is the team repo if it has src/p0.py and config/hosts.cfg."""
    if not path or not os.path.isdir(path):
        return False
    return (os.path.isfile(os.path.join(path, "src", "p0.py"))
            and os.path.isfile(os.path.join(path, "config", "hosts.cfg")))


def _candidates():
    """Every place worth looking, in priority order."""
    out = []
    env = os.environ.get("DC_TEAM_REPO")
    if env:
        out.append(os.path.abspath(os.path.expanduser(env)))

    out.append(os.getcwd())

    # These tools may live INSIDE the team repo (e.g. as team-repo/infra/),
    # so walk up from this file and test each ancestor directly.
    node = HERE
    for _ in range(4):
        parent = os.path.dirname(node)
        if not parent or parent == node:
            break
        out.append(parent)
        node = parent

    parents = [os.path.dirname(HERE), os.path.expanduser("~"),
               os.path.join(os.path.expanduser("~"), "Code"),
               os.path.join(os.path.expanduser("~"), "mnt")]

    for parent in parents:
        if not os.path.isdir(parent):
            continue
        try:
            entries = sorted(os.listdir(parent))
        except OSError:
            continue
        for name in entries:
            # Match the team's repo name, however it was cloned or renamed.
            low = name.lower()
            if "food" in low or "delivar" in low or "deliver" in low or "bits" in low:
                out.append(os.path.join(parent, name))
    return out


def find_repo(explicit=None, required=True):
    """Return the absolute path of the team's checkout, or raise/None."""
    if explicit:
        path = os.path.abspath(os.path.expanduser(explicit))
        if _looks_like_team_repo(path):
            return path
        if required:
            raise TeamRepoError(
                "--repo {} does not look like the team repository.\n"
                "        Expected to find src/p0.py and config/hosts.cfg inside it."
                .format(path))
        return None

    seen = set()
    for cand in _candidates():
        if cand in seen:
            continue
        seen.add(cand)
        if _looks_like_team_repo(cand):
            return cand

    if required:
        raise TeamRepoError(
            "Could not find the team's application repository.\n"
            "        It is the checkout containing src/p0.py and config/hosts.cfg.\n\n"
            "        Point at it explicitly:\n"
            "          python3 <tool>.py --repo /path/to/bits-food-delivary-...\n"
            "        or export it once per shell:\n"
            "          export DC_TEAM_REPO=/path/to/bits-food-delivary-...")
    return None


def hosts_cfg_path(repo):
    return os.path.join(repo, "config", "hosts.cfg")


def src_path(repo, name):
    return os.path.join(repo, "src", name)


def process_file(repo, pname):
    """Absolute path of pN.py for a process name like 'P3'."""
    return src_path(repo, "p{}.py".format(pname[1:]))


def read_config(repo):
    """Parse the team's hosts.cfg.

    Returns (ports, node_ips, hosts) where:
        ports    {'P0': 5005, ...}
        node_ips {'NODE1_IP': '10.0.0.15', ...}   ('' when unset)
        hosts    {'P0': '10.0.0.15', ...}         ('localhost' when unset,
                                                   matching the team's own
                                                   fallback in load_hosts())
    """
    ports = dict(FALLBACK_PORTS)
    node_ips = {k: "" for k in NODE_KEYS}

    path = hosts_cfg_path(repo)
    parser = configparser.ConfigParser()
    if os.path.exists(path):
        try:
            parser.read(path)
        except configparser.Error as exc:
            raise TeamRepoError("config/hosts.cfg is malformed: {}".format(exc))

        if "ports" in parser:
            for key, value in parser["ports"].items():
                try:
                    ports[key.split("_")[0].upper()] = int(value)
                except ValueError:
                    pass

        if "nodes" in parser:
            for key, value in parser["nodes"].items():
                node_ips[key.upper()] = value.strip()

    hosts = {}
    for pname in PROCESS_NAMES:
        ip = node_ips.get(PROCESS_NODE[pname], "")
        hosts[pname] = ip if ip else "localhost"

    return ports, node_ips, hosts


def is_configured(node_ips):
    """True when all three node IPs have been filled in."""
    return all(node_ips.get(k) for k in NODE_KEYS)


def is_single_host(node_ips):
    """True when every node points at the same address (loopback demo mode)."""
    values = [node_ips.get(k, "") for k in NODE_KEYS]
    return all(values) and len(set(values)) == 1


def processes_for_node(node_key):
    """['P1', 'P2'] for NODE2_IP, and so on."""
    return [p for p in PROCESS_NAMES if PROCESS_NODE[p] == node_key]


def detect_my_node(node_ips):
    """Which node key this machine is, matched against its own addresses."""
    mine = set(local_ips())
    for key in NODE_KEYS:
        ip = node_ips.get(key, "")
        if ip and ip in mine:
            return key
    if is_single_host(node_ips):
        return "NODE1_IP"
    return None


def local_ips():
    """Best-effort list of this machine's own IPv4 addresses."""
    import socket
    found = set()
    try:
        for res in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            found.add(res[4][0])
    except (socket.gaierror, OSError):
        pass
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        found.add(probe.getsockname()[0])
    except OSError:
        pass
    finally:
        probe.close()
    found.discard("127.0.0.1")
    return sorted(found)
