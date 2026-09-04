"""
preflight.py — Everything that can fail before the demo, checked in one command.
Owner: Sohail (Infrastructure)

Run this on every VM immediately before the dry run and again before the real
run. It is deliberately paranoid: a failure here costs thirty seconds, the
same failure during the presentation costs marks.

    python3 preflight.py               # local checks only
    python3 preflight.py --net         # also probe the other VMs
    python3 preflight.py --strict      # warnings are treated as failures

Checks performed
  ENV   Python version, colorama availability, write access for logs
  CODE  all seven source files present, non-empty and syntactically valid
  CONF  hosts.cfg parses; node IPs set; this machine identified
  PORT  the ports this machine owns are free (nothing stale still bound)
  NET   with --net, every peer endpoint accepts a TCP connection

Exit code 0 means go. Anything else means stop and read the output.
Pure standard library apart from the colorama probe, which is a check, not
a dependency of this file.
"""

import argparse
import os
import socket
import sys

import team_repo as tr

PASS = "[ ok ]"
WARN = "[warn]"
FAIL = "[FAIL]"

MIN_PYTHON = (3, 8)


class Report:
    def __init__(self, strict=False):
        self.rows = []
        self.failures = 0
        self.warnings = 0
        self.strict = strict

    def ok(self, group, detail):
        self.rows.append((PASS, group, detail))

    def warn(self, group, detail, hint=None):
        self.warnings += 1
        self.rows.append((WARN, group, detail))
        if hint:
            self.rows.append(("", "", "      -> " + hint))

    def fail(self, group, detail, hint=None):
        self.failures += 1
        self.rows.append((FAIL, group, detail))
        if hint:
            self.rows.append(("", "", "      -> " + hint))

    def render(self):
        print()
        for status, group, detail in self.rows:
            if status:
                print("  {} {:<6} {}".format(status, group, detail))
            else:
                print("  {:<6} {:<6} {}".format("", "", detail))
        print()
        print("  " + "-" * 68)
        if self.failures:
            print("  RESULT: {} failure(s), {} warning(s). Do not start the demo yet."
                  .format(self.failures, self.warnings))
            return 1
        if self.warnings and self.strict:
            print("  RESULT: {} warning(s), and --strict was requested."
                  .format(self.warnings))
            return 1
        if self.warnings:
            print("  RESULT: ready, with {} warning(s) above.".format(self.warnings))
            return 0
        print("  RESULT: all checks passed. Ready to run.")
        return 0


# ---------------------------------------------------------------------------

def check_env(rep):
    version = "{}.{}.{}".format(*sys.version_info[:3])
    if sys.version_info >= MIN_PYTHON:
        rep.ok("ENV", "python {}".format(version))
    else:
        rep.fail("ENV", "python {} is too old (need {}.{}+)"
                 .format(version, *MIN_PYTHON),
                 "sudo apt install -y python3")

    try:
        import colorama  # noqa: F401
        rep.ok("ENV", "colorama importable (required by the team's processes)")
    except ImportError:
        rep.fail("ENV", "colorama is not installed",
                 "pip3 install colorama   (or: sudo apt install -y python3-colorama)")

    # We need exactly one thing from the filesystem: the ability to create
    # logs/ and write into it. Test that, not a generic temp file — some
    # mounted filesystems allow creation but not unlink, which is fine here.
    probe_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    probe = os.path.join(probe_dir, ".preflight-probe")
    try:
        os.makedirs(probe_dir, exist_ok=True)
        with open(probe, "w") as fh:
            fh.write("ok\n")
        rep.ok("ENV", "logs/ is writable (run output can be captured)")
    except OSError as exc:
        rep.fail("ENV", "cannot write to {}: {}".format(probe_dir, exc),
                 "run from a directory you own, or pass --logdir elsewhere")
    finally:
        try:
            os.remove(probe)
        except OSError:
            pass  # unlink may be denied on some mounts; the write is what matters


def check_code(rep, repo):
    rep.ok("CODE", "team repository at {}".format(repo))

    expected = ["p0.py", "p1.py", "p2.py", "p3.py", "p4.py",
                "vector_clock.py", "snapshot.py"]
    missing, empty, broken = [], [], []

    for name in expected:
        path = tr.src_path(repo, name)
        if not os.path.isfile(path):
            missing.append(name)
            continue
        if os.path.getsize(path) == 0:
            empty.append(name)
            continue
        try:
            with open(path, "r", errors="replace") as fh:
                compile(fh.read(), path, "exec")
        except SyntaxError as exc:
            broken.append("{} (line {}: {})".format(name, exc.lineno, exc.msg))
        except OSError as exc:
            broken.append("{} (unreadable: {})".format(name, exc))

    if missing:
        rep.fail("CODE", "missing source files: {}".format(", ".join(missing)),
                 "git pull in the team repository")
    if empty:
        rep.fail("CODE", "empty source files: {}".format(", ".join(empty)),
                 "these are placeholders — the owner has not committed yet")
    if broken:
        for item in broken:
            rep.fail("CODE", "syntax error in {}".format(item))

    good = len(expected) - len(missing) - len(empty) - len(broken)
    if good:
        rep.ok("CODE", "{}/{} source files present and compile cleanly"
               .format(good, len(expected)))


def check_conf(rep, repo):
    try:
        ports, node_ips, hosts = tr.read_config(repo)
    except tr.TeamRepoError as exc:
        rep.fail("CONF", str(exc))
        return None, None, None

    rep.ok("CONF", "hosts.cfg parses; ports {}".format(
        " ".join("{}={}".format(p, ports[p]) for p in tr.PROCESS_NAMES)))

    if not tr.is_configured(node_ips):
        unset = [k for k in tr.NODE_KEYS if not node_ips.get(k)]
        rep.fail("CONF", "node IPs not set: {}".format(", ".join(unset)),
                 "python3 configure_hosts.py <NODE1_IP> <NODE2_IP> <NODE3_IP>")
        return ports, node_ips, hosts

    if tr.is_single_host(node_ips):
        rep.warn("CONF", "single-host mode — all processes on {}"
                 .format(node_ips["NODE1_IP"]),
                 "fine for a dry run, but the demo must span three VMs")
    else:
        rep.ok("CONF", "three distinct nodes configured")

    my_node = tr.detect_my_node(node_ips)
    if my_node:
        owned = ", ".join(tr.processes_for_node(my_node))
        rep.ok("CONF", "this machine is {} and owns {}".format(my_node, owned))
    else:
        rep.warn("CONF", "this machine matches none of the configured IPs",
                 "detected locally: {}".format(", ".join(tr.local_ips()) or "none"))

    return ports, node_ips, hosts


def check_ports(rep, ports, node_ips):
    """The ports this machine is meant to bind must be free right now."""
    my_node = tr.detect_my_node(node_ips) if node_ips else None
    if my_node:
        owned = tr.processes_for_node(my_node)
    else:
        owned = list(tr.PROCESS_NAMES)
        rep.warn("PORT", "node unknown — checking all five ports on this machine")

    busy = []
    for pname in owned:
        port = ports[pname]
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("0.0.0.0", port))
        except OSError:
            busy.append((pname, port))
        finally:
            sock.close()

    if busy:
        for pname, port in busy:
            rep.fail("PORT", "{} port {} is already in use".format(pname, port),
                     "pkill -f 'p{}.py'   or:  ss -ltnp | grep {}"
                     .format(pname[1:], port))
    else:
        rep.ok("PORT", "ports free on this machine: {}".format(
            " ".join(str(ports[p]) for p in owned)))


def check_net(rep, ports, hosts, node_ips):
    """Probe every peer endpoint. Only meaningful once peers are running."""
    my_node = tr.detect_my_node(node_ips) if node_ips else None
    mine = set(tr.processes_for_node(my_node)) if my_node else set()

    reachable, refused, timedout = [], [], []
    for pname in tr.PROCESS_NAMES:
        if pname in mine:
            continue
        host, port = hosts[pname], ports[pname]
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3.0)
        try:
            sock.connect((host, port))
            reachable.append("{}@{}:{}".format(pname, host, port))
        except socket.timeout:
            timedout.append("{}@{}:{}".format(pname, host, port))
        except OSError:
            refused.append("{}@{}:{}".format(pname, host, port))
        finally:
            sock.close()

    for item in reachable:
        rep.ok("NET", "{} reachable".format(item))
    for item in refused:
        rep.warn("NET", "{} refused the connection".format(item),
                 "the network is fine; that process is simply not running yet")
    for item in timedout:
        rep.fail("NET", "{} timed out".format(item),
                 "firewall or wrong IP — sudo ufw allow 5001:5005/tcp, "
                 "then check the lab network policy")


def main():
    parser = argparse.ArgumentParser(
        description="Pre-demo readiness check for the distributed food delivery system.")
    parser.add_argument("--repo", help="path to the team's checkout")
    parser.add_argument("--net", action="store_true",
                        help="also probe peer endpoints over the network")
    parser.add_argument("--strict", action="store_true",
                        help="treat warnings as failures")
    args = parser.parse_args()

    print()
    print("=" * 72)
    print(" PREFLIGHT — Group 2 distributed food delivery system")
    print("=" * 72)

    rep = Report(strict=args.strict)
    check_env(rep)

    try:
        repo = tr.find_repo(args.repo)
    except tr.TeamRepoError as exc:
        rep.fail("CODE", "team repository not found")
        for line in str(exc).splitlines():
            rep.rows.append(("", "", "      " + line.strip()))
        return rep.render()

    check_code(rep, repo)
    ports, node_ips, hosts = check_conf(rep, repo)

    if ports:
        check_ports(rep, ports, node_ips)
        if args.net:
            check_net(rep, ports, hosts, node_ips)
        else:
            rep.rows.append(("", "", "      (network probes skipped — add --net)"))

    return rep.render()


if __name__ == "__main__":
    sys.exit(main())
