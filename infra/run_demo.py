"""
run_demo.py — Launch this machine's processes, capture everything, shut down cleanly.
Owner: Sohail (Infrastructure)

WHY THIS EXISTS
---------------
A live demo has three ways to go wrong that have nothing to do with the
algorithm: processes started in the wrong order, output scrolling past
faster than anyone can read it, and stale processes left holding ports
afterwards. This handles all three.

Every line each process prints is timestamped, stripped of colour codes and
written to logs/<pN>.log, while still being echoed to the screen with a
process tag. Those log files are the raw evidence for the report, and they
are what analyse_run.py reads afterwards.

USAGE
-----
Single machine, whole system (dry run):

    python3 run_demo.py --all --auto

Three VMs — run on each, in this order (node3, then node2, then node1):

    python3 run_demo.py                 # auto-detects which node this is
    python3 run_demo.py --auto          # on node1, also drives the scenario

Useful flags:
    --procs P1,P3        run an explicit subset
    --duration 45        seconds to run before shutting down (default 40)
    --quiet              write logs but do not echo to the screen
    --keep-logs          append to existing logs instead of starting fresh

Start order is always P3 and P4 first, then P1 and P2, then P0. Listeners
must exist before senders: the team's processes do not retry a refused
connection, they simply print a send error and move on.
"""

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time

import team_repo as tr

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

# Listeners before senders. P0 last because it drives everything.
START_ORDER = ["P3", "P4", "P1", "P2", "P0"]

STAGGER = 0.6      # seconds between processes within a stage
STAGE_PAUSE = 1.2  # seconds between stages

TAG_COLOUR = {
    "P0": "\033[35m", "P1": "\033[32m", "P2": "\033[33m",
    "P3": "\033[36m", "P4": "\033[34m",
}
RESET = "\033[0m"


class Launched:
    def __init__(self, pname, proc, log_path):
        self.pname = pname
        self.proc = proc
        self.log_path = log_path
        self.lines = 0


def _pump(entry, log_fh, echo, lock):
    """Read one process's output, timestamp it, write it, optionally echo it."""
    colour = TAG_COLOUR.get(entry.pname, "")
    stream = entry.proc.stdout
    for raw in iter(stream.readline, b""):
        try:
            text = raw.decode("utf-8", errors="replace").rstrip("\n")
        except Exception:
            continue
        clean = ANSI.sub("", text).rstrip()
        if not clean.strip():
            continue
        stamp = time.strftime("%Y-%m-%dT%H:%M:%S") + ".{:03d}".format(
            int((time.time() % 1) * 1000))
        with lock:
            log_fh.write("{} | {} | {}\n".format(stamp, entry.pname, clean))
            log_fh.flush()
            entry.lines += 1
            if echo:
                sys.stdout.write("{}{:<3}{} {}\n".format(colour, entry.pname, RESET, clean))
                sys.stdout.flush()
    try:
        stream.close()
    except Exception:
        pass


def which_processes(args, node_ips):
    if args.procs:
        wanted = []
        for token in args.procs.replace(",", " ").split():
            name = token.strip().upper()
            if not name:
                continue
            if name.isdigit():
                name = "P" + name
            if name not in tr.PROCESS_NAMES:
                sys.exit("[ERROR] Unknown process {!r}. Valid: {}"
                         .format(token, ", ".join(tr.PROCESS_NAMES)))
            wanted.append(name)
        return wanted

    if args.all:
        return list(tr.PROCESS_NAMES)

    node = args.node
    if node:
        key = node.upper()
        if not key.endswith("_IP"):
            key = key.replace("NODE", "NODE") + "_IP"
        if key not in tr.NODE_KEYS:
            sys.exit("[ERROR] Unknown node {!r}. Valid: node1, node2, node3".format(node))
        return tr.processes_for_node(key)

    detected = tr.detect_my_node(node_ips)
    if not detected:
        sys.exit("[ERROR] Could not tell which node this machine is.\n"
                 "        Say so explicitly:  python3 run_demo.py --node node2\n"
                 "        Or run everything here:  python3 run_demo.py --all")
    return tr.processes_for_node(detected)


def main():
    parser = argparse.ArgumentParser(
        description="Launch, capture and cleanly stop this machine's processes.")
    parser.add_argument("--repo", help="path to the team's checkout")
    parser.add_argument("--all", action="store_true",
                        help="run all five processes on this machine")
    parser.add_argument("--node", help="force node1 / node2 / node3")
    parser.add_argument("--procs", help="explicit list, e.g. P1,P3")
    parser.add_argument("--auto", action="store_true",
                        help="pass --auto to P0 so it drives the full scenario")
    parser.add_argument("--duration", type=float, default=40.0,
                        help="seconds to run before shutting down (default 40)")
    # Default beside this file, not beside the shell's cwd, so running the
    # tools from inside the team's checkout never scatters output into it.
    parser.add_argument("--logdir",
                        default=os.path.join(
                            os.path.dirname(os.path.abspath(__file__)), "logs"),
                        help="where to write logs (default: logs/ beside this script)")
    parser.add_argument("--quiet", action="store_true", help="do not echo to screen")
    parser.add_argument("--keep-logs", action="store_true",
                        help="append rather than truncate")
    args = parser.parse_args()

    try:
        repo = tr.find_repo(args.repo)
    except tr.TeamRepoError as exc:
        sys.exit("[ERROR] {}".format(exc))

    ports, node_ips, hosts = tr.read_config(repo)
    wanted = which_processes(args, node_ips)

    if not tr.is_configured(node_ips) and len(wanted) < len(tr.PROCESS_NAMES):
        print("[warn] Node IPs are not configured, so peers resolve to localhost.")
        print("       A partial run on this machine will not reach the other VMs.")
        print("       Fix with: python3 configure_hosts.py <IP1> <IP2> <IP3>")
        print()

    logdir = os.path.abspath(args.logdir)
    os.makedirs(logdir, exist_ok=True)

    started_at = time.time()
    run_id = time.strftime("%Y%m%d-%H%M%S")

    print()
    print("=" * 72)
    print(" RUN {}  —  starting {} on this machine".format(run_id, ", ".join(wanted)))
    print(" repo   {}".format(repo))
    print(" logs   {}".format(logdir))
    print("=" * 72)
    print()

    launched = []
    lock = threading.Lock()
    pumps = []
    log_handles = []

    order = [p for p in START_ORDER if p in wanted]
    stages = [[p for p in ("P3", "P4") if p in order],
              [p for p in ("P1", "P2") if p in order],
              [p for p in ("P0",) if p in order]]

    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"

    try:
        for stage in stages:
            if not stage:
                continue
            for pname in stage:
                script = tr.process_file(repo, pname)
                if not os.path.isfile(script):
                    print("[warn] {} not found at {} — skipping".format(pname, script))
                    continue

                cmd = [sys.executable, script]
                if pname == "P0" and args.auto:
                    cmd.append("--auto")

                log_path = os.path.join(logdir, "{}.log".format(pname.lower()))
                fh = open(log_path, "a" if args.keep_logs else "w", buffering=1)
                log_handles.append(fh)
                fh.write("# run {} | {} | {}\n".format(
                    run_id, pname, tr.ROLE[pname]))

                proc = subprocess.Popen(
                    cmd, cwd=repo, env=env,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL)

                entry = Launched(pname, proc, log_path)
                launched.append(entry)

                thread = threading.Thread(target=_pump,
                                          args=(entry, fh, not args.quiet, lock),
                                          daemon=True)
                thread.start()
                pumps.append(thread)

                print("[ok]   started {:<3} pid {:<7} port {}"
                      .format(pname, proc.pid, ports[pname]))
                time.sleep(STAGGER)
            time.sleep(STAGE_PAUSE)

        if not launched:
            sys.exit("[ERROR] Nothing was started.")

        print()
        print("-" * 72)
        print(" running for {:.0f}s — Ctrl-C to stop early".format(args.duration))
        print("-" * 72)
        print()

        deadline = time.time() + args.duration
        while time.time() < deadline:
            if all(e.proc.poll() is not None for e in launched):
                print("\n[note] every process exited on its own.")
                break
            time.sleep(0.25)

    except KeyboardInterrupt:
        print("\n[note] interrupted — shutting down.")

    finally:
        print()
        print("-" * 72)
        for entry in launched:
            if entry.proc.poll() is None:
                try:
                    entry.proc.send_signal(signal.SIGTERM)
                except Exception:
                    pass
        deadline = time.time() + 5.0
        while time.time() < deadline:
            if all(e.proc.poll() is not None for e in launched):
                break
            time.sleep(0.1)
        for entry in launched:
            if entry.proc.poll() is None:
                try:
                    entry.proc.kill()
                except Exception:
                    pass

        for thread in pumps:
            thread.join(timeout=2.0)
        for fh in log_handles:
            try:
                fh.close()
            except Exception:
                pass

        elapsed = time.time() - started_at
        meta = {
            "run_id": run_id,
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%S",
                                        time.localtime(started_at)),
            "duration_seconds": round(elapsed, 1),
            "repo": repo,
            "processes": [e.pname for e in launched],
            "node_ips": node_ips,
            "ports": ports,
            "hosts": hosts,
            "log_lines": {e.pname: e.lines for e in launched},
        }
        with open(os.path.join(logdir, "run-meta.json"), "w") as fh:
            json.dump(meta, fh, indent=2)
            fh.write("\n")

        print(" stopped after {:.1f}s".format(elapsed))
        for entry in launched:
            print("   {:<3} {:>5} lines  ->  {}".format(
                entry.pname, entry.lines, os.path.relpath(entry.log_path)))
        print("-" * 72)
        print()
        print(" Next:  python3 analyse_run.py --logdir {}".format(
            os.path.relpath(logdir)))
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
