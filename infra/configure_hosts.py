"""
configure_hosts.py — Point the team's processes at the three real VMs.
Owner: Sohail (Infrastructure)

WHY THIS EXISTS
---------------
The five process files resolve every peer through config/hosts.cfg. As
committed, the [nodes] section is blank:

    [nodes]
    NODE1_IP=
    NODE2_IP=
    NODE3_IP=

Each process then falls back to "localhost" (src/p1.py:85 and its siblings),
so the whole system silently collapses onto one machine. That is the single
change standing between the current code and a real three-VM run.

This tool fills those three lines in and nothing else. Ports, [process_hosts]
and every comment survive byte-for-byte, because it rewrites only the three
lines it recognises rather than round-tripping the file through a parser.

USAGE
-----
    python3 configure_hosts.py 10.0.0.15 10.0.0.16 10.0.0.17
    python3 configure_hosts.py --local        # 127.0.0.1 everywhere
    python3 configure_hosts.py --show         # print current state, change nothing
    python3 configure_hosts.py --restore      # put back the last backup

Run it on EVERY VM with the SAME three addresses in the SAME order:

    NODE1 = Master     hosts P0
    NODE2 = Slave 1    hosts P1, P2
    NODE3 = Slave 2    hosts P3, P4

A different order on one machine routes its messages to the wrong process,
and the failure looks like an application bug rather than a config mistake.
"""

import argparse
import ipaddress
import os
import re
import shutil
import sys
import time

import team_repo as tr

# The backup lives in THIS repo, never in the team's checkout — leaving stray
# files in someone else's working tree is how accidental commits happen.
BACKUP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           ".hosts.cfg.backup")


def validate_ip(raw, label):
    value = (raw or "").strip()
    try:
        ipaddress.IPv4Address(value)
    except (ipaddress.AddressValueError, ValueError):
        sys.exit("[ERROR] {} is not a valid IPv4 address: {!r}".format(label, raw))
    return value


def show(repo):
    ports, node_ips, hosts = tr.read_config(repo)
    print()
    print("Team repository : {}".format(repo))
    print("Config file     : {}".format(tr.hosts_cfg_path(repo)))
    print()
    print("  {:<12} {:<18} {}".format("NODE", "IP", "ROLE"))
    print("  " + "-" * 66)
    for key in tr.NODE_KEYS:
        ip = node_ips.get(key) or "(not set)"
        print("  {:<12} {:<18} {}".format(key, ip, tr.NODE_LABEL[key]))
    print()
    print("  {:<6} {:<18} {:<7} {}".format("PROC", "RESOLVES TO", "PORT", "ROLE"))
    print("  " + "-" * 74)
    for pname in tr.PROCESS_NAMES:
        print("  {:<6} {:<18} {:<7} {}".format(
            pname, hosts[pname], ports[pname], tr.ROLE[pname]))
    print()

    if not tr.is_configured(node_ips):
        print("  STATUS: NOT CONFIGURED — every process resolves to localhost.")
        print("          A three-VM run is not possible until this is set.")
        print()
        print("          python3 configure_hosts.py <NODE1_IP> <NODE2_IP> <NODE3_IP>")
    elif tr.is_single_host(node_ips):
        print("  STATUS: single-host mode. Fine for development, not for the demo.")
    else:
        my_node = tr.detect_my_node(node_ips)
        if my_node:
            owned = ", ".join(tr.processes_for_node(my_node))
            print("  STATUS: configured. This machine is {} and runs {}."
                  .format(my_node, owned))
        else:
            print("  STATUS: configured, but none of the three IPs match this machine.")
            print("          Detected locally: {}".format(
                ", ".join(tr.local_ips()) or "none"))
    print()
    return 0


def apply_ips(repo, node_ips_new, quiet=False):
    """Rewrite only the three NODEn_IP lines inside [nodes]."""
    path = tr.hosts_cfg_path(repo)
    with open(path, "r") as fh:
        original = fh.read()

    lines = original.splitlines(True)
    section = None
    written = {k: False for k in tr.NODE_KEYS}
    out = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1].lower()
            out.append(line)
            continue

        if section == "nodes":
            match = re.match(r"^(\s*)(NODE[123]_IP)(\s*)=(.*)$", line, re.IGNORECASE)
            if match:
                indent, key, pad, _old = match.groups()
                key_upper = key.upper()
                if key_upper in node_ips_new:
                    newline = "\n" if line.endswith("\n") else ""
                    out.append("{}{}{}={}{}".format(
                        indent, key_upper, pad, node_ips_new[key_upper], newline))
                    written[key_upper] = True
                    continue
        out.append(line)

    missing = [k for k, done in written.items() if not done]
    if missing:
        sys.exit("[ERROR] Could not find {} in the [nodes] section of {}.\n"
                 "        The config file layout has changed; fix it by hand."
                 .format(", ".join(missing), path))

    updated = "".join(out)
    if updated == original:
        if not quiet:
            print("[ok]   config/hosts.cfg already had these values — nothing to change.")
        return

    if not os.path.exists(BACKUP_PATH):
        shutil.copy2(path, BACKUP_PATH)
        if not quiet:
            print("[ok]   original backed up to {}".format(
                os.path.basename(BACKUP_PATH)))

    with open(path, "w") as fh:
        fh.write(updated)

    if not quiet:
        print("[ok]   config/hosts.cfg updated at {}".format(
            time.strftime("%H:%M:%S")))


def restore(repo):
    path = tr.hosts_cfg_path(repo)
    if not os.path.exists(BACKUP_PATH):
        sys.exit("[ERROR] No backup found at {}".format(BACKUP_PATH))
    shutil.copy2(BACKUP_PATH, path)
    print("[ok]   config/hosts.cfg restored from backup.")
    return show(repo)


def main():
    parser = argparse.ArgumentParser(
        description="Fill in the team's config/hosts.cfg with real node IPs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Run on every VM with the same three IPs in the same order.")
    parser.add_argument("ips", nargs="*", metavar="IP",
                        help="NODE1_IP NODE2_IP NODE3_IP")
    parser.add_argument("--repo", help="path to the team's checkout")
    parser.add_argument("--local", action="store_true",
                        help="set all three nodes to 127.0.0.1")
    parser.add_argument("--show", action="store_true",
                        help="print the current configuration and exit")
    parser.add_argument("--restore", action="store_true",
                        help="restore config/hosts.cfg from the backup")
    args = parser.parse_args()

    try:
        repo = tr.find_repo(args.repo)
    except tr.TeamRepoError as exc:
        sys.exit("[ERROR] {}".format(exc))

    if args.restore:
        return restore(repo)
    if args.show or (not args.ips and not args.local):
        return show(repo)

    if args.local:
        new = {k: "127.0.0.1" for k in tr.NODE_KEYS}
    else:
        if len(args.ips) != 3:
            sys.exit("[ERROR] Expected exactly 3 IP addresses, got {}.\n"
                     "        python3 configure_hosts.py <NODE1_IP> <NODE2_IP> <NODE3_IP>"
                     .format(len(args.ips)))
        new = {
            "NODE1_IP": validate_ip(args.ips[0], "NODE1_IP"),
            "NODE2_IP": validate_ip(args.ips[1], "NODE2_IP"),
            "NODE3_IP": validate_ip(args.ips[2], "NODE3_IP"),
        }
        if len(set(new.values())) != 3:
            print("[warn] Two or more nodes share an IP. That is only correct if you")
            print("       are deliberately co-locating processes on fewer machines.")

    apply_ips(repo, new)
    return show(repo)


if __name__ == "__main__":
    sys.exit(main() or 0)
