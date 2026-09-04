"""
analyse_run.py — Turn captured logs into the evidence the report needs.
Owner: Sohail (Infrastructure)

WHY THIS EXISTS
---------------
The assignment is graded on evidence, not on the system merely having run:
causal ordering, a demonstrated pair of concurrent events, the recorded
global state including channels, and an argument about consistency. Scraping
that out of five scrolling terminals by hand is slow and easy to get wrong.

This reads the logs written by run_demo.py and produces:

  * a merged, causally-ordered event timeline across all five processes
  * every pair of concurrent events found, by vector-clock comparison
  * a reconstruction of each snapshot: who recorded, at what clock, and
    what channel state (if any) was captured
  * an independent consistency verdict, checked in BOTH directions
  * a requirement-by-requirement checklist derived from what actually happened

Output is a self-contained HTML file. Open it in a browser and print to PDF
for the submission, or paste the tables straight into GROUP-2.pdf.

    python3 analyse_run.py                       # reads ./logs
    python3 analyse_run.py --logdir logs --out report
    python3 analyse_run.py --csv                 # also write the timeline as CSV

Pure standard library.
"""

import argparse
import csv
import html
import json
import os
import re
import sys
import time

PROCESS_NAMES = ["P0", "P1", "P2", "P3", "P4"]
N = 5

ROLE = {
    "P0": "Central Order Processor",
    "P1": "Restaurant A — Pizza Palace",
    "P2": "Restaurant B — Burger Hub",
    "P3": "Delivery Partner 1 — Fleet Runner A",
    "P4": "Delivery Partner 2 — Fleet Runner B",
}

CLOCK = r"\[\s*(\d+(?:\s*,\s*\d+)*)\s*\]"

# Threads inside a single process can interleave their print() calls, so two
# log lines occasionally arrive merged: "... | SNAPSHOT_1[MARKER] P2 -> P4".
# A bare \S+ swallows the second line's opening bracket and invents a snapshot
# called "SNAPSHOT_1[MARKER". Restrict ids to characters they can actually use.
SNAPID = r"[A-Za-z0-9_.\-]+"

LINE = re.compile(r"^(?P<ts>\S+)\s\|\s(?P<proc>P\d)\s\|\s(?P<body>.*)$")

PATTERNS = [
    # --- vector_clock.py, common to every process -------------------------
    ("internal", re.compile(r"^\[INTERNAL\]\s+(?P<who>P\d)\s*\|\s*(?P<desc>.*?)\s*\|\s*Clock:\s*" + CLOCK)),
    ("send",     re.compile(r"^\[SEND\]\s+(?P<who>P\d)\s*\|\s*Clock:\s*" + CLOCK + r"\s*$")),
    ("receive",  re.compile(r"^\[RECV\]\s+(?P<who>P\d)\s*\|\s*Clock:\s*" + CLOCK + r"\s*$")),
    # --- p3.py / p4.py own loggers ---------------------------------------
    ("send",     re.compile(r"^\[SEND\]\s+(?P<who>P\d)\s*(?:->|→)\s*(?P<peer>P\d)\s*\|\s*(?P<desc>.*?)\s*\|\s*Clock:\s*" + CLOCK)),
    ("receive",  re.compile(r"^\[RECV\]\s+(?P<who>P\d)\s*(?:<-|←)\s*(?P<peer>P\d)\s*\|\s*(?P<desc>.*?)\s*\|\s*Clock:\s*" + CLOCK)),
    ("snapshot", re.compile(r"^\[SNAPSHOT\]\s+(?P<who>P\d)\s*\|\s*(?P<desc>.*?)\s*\|\s*Clock:\s*" + CLOCK)),
    # --- application-level lines -----------------------------------------
    ("receive",  re.compile(r"^\[(?P<who>P\d)\s[^\]]*\]\s+RECEIVE\s+ORDER\s+(?P<desc>\S+).*?Clock:\s*" + CLOCK)),
    ("send",     re.compile(r"^\[(?P<who>P\d)\s[^\]]*\]\s+DISPATCH\s+(?P<desc>ORDER\s+\S+).*?Clock:\s*" + CLOCK)),
]

MARKER_SENT = re.compile(r"^\[MARKER\]\s+(?P<src>P\d)\s*(?:->|→)\s*(?P<dst>P\d)(?:\s*\|\s*(?P<snap>" + SNAPID + r"))?")
MARKER_RECV = re.compile(r"^\[MARKER RECV\]\s+(?P<dst>P\d)\s*(?:<-|←)\s*(?P<src>P\d)\s*\|\s*(?P<snap>" + SNAPID + r")")
STATE_SENT = re.compile(r"^\[STATE\]\s+(?P<src>P\d)\s*(?:->|→)\s*(?P<dst>P\d)\s*\|\s*(?P<snap>" + SNAPID + r")")
STATE_RECV = re.compile(r"^\[STATE RECEIVED\]\s+(?P<src>P\d)\s*(?:->|→)\s*(?P<dst>P\d)\s*(?:\||for)\s*(?P<snap>" + SNAPID + r")")
SNAP_TRIG = re.compile(r"^\[SNAPSHOT\]\s+(?P<who>P\d)\s*\|\s*(?P<snap>" + SNAPID + r")\s+triggered")
PROGRESS = re.compile(r"Progress:\s*(?P<got>\d+)\s*/\s*(?P<total>\d+)")
REPORT_HDR = re.compile(r"^-*\s*Global Snapshot Report:\s*(?P<snap>" + SNAPID + r")")
# The clock group is named: 'who' occupies group 1, so positional access here
# would read the process name instead of the digits.
REPORT_ROW = re.compile(
    r"^(?P<who>P\d)\s+\[\s*(?P<clock>\d+(?:\s*,\s*\d+)*)\s*\]\s*(?P<rest>.*)$")
# P3 and P4 log an incoming marker through their own logger rather than
# snapshot.py's, so the marker flow is only complete if both forms are read.
MARKER_RECV_ALT = re.compile(
    r"^\[RECV\]\s+(?P<dst>P\d)\s*(?:<-|←)\s*(?P<src>P\d)\s*\|\s*MARKER\s+for\s+(?P<snap>"
    + SNAPID + r")")
# Channel-state detection has to be strict. "Order #101 in transit" is a
# delivery status, not a recorded channel. Only these shapes count as a
# process actually reporting the contents of an incoming channel.
CHANNEL_STATE = re.compile(
    r"channel[_\s]state"
    r"|in-transit\s+message"
    r"|channel\s+P\d\s*(?:->|→|<-|←)\s*P\d"
    r"|recorded\s+\d+\s+message",
    re.IGNORECASE)

# A channel that was recorded but held nothing. Legitimate under
# Chandy-Lamport, but it does not by itself demonstrate the requirement.
CHANNEL_EMPTY = re.compile(r"\bempty\b|:\s*\[\s*\]|:\s*\{\s*\}", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Vector clock algebra
# ---------------------------------------------------------------------------

def parse_clock(text):
    try:
        vals = [int(x.strip()) for x in text.split(",")]
    except (ValueError, AttributeError):
        return None
    if len(vals) != N:
        return None
    return vals


def leq(a, b):
    return all(x <= y for x, y in zip(a, b))


def happens_before(a, b):
    return a != b and leq(a, b)


def concurrent(a, b):
    return a != b and not leq(a, b) and not leq(b, a)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

class Event:
    __slots__ = ("seq", "ts", "proc", "kind", "desc", "clock", "peer", "raw")

    def __init__(self, seq, ts, proc, kind, desc, clock, peer, raw):
        self.seq, self.ts, self.proc = seq, ts, proc
        self.kind, self.desc, self.clock = kind, desc, clock
        self.peer, self.raw = peer, raw


def parse_logs(logdir):
    events, markers, states, snapshots, reports = [], [], [], {}, {}
    channel_lines = []
    raw_count = 0
    seq = 0

    files = sorted(f for f in os.listdir(logdir) if f.endswith(".log"))
    if not files:
        raise SystemExit(
            "[ERROR] No .log files in {}.\n"
            "        Capture a run first:  python3 run_demo.py --all --auto"
            .format(logdir))

    current_report = None

    for fname in files:
        with open(os.path.join(logdir, fname), "r", errors="replace") as fh:
            for line in fh:
                line = line.rstrip("\n")
                if not line.strip() or line.startswith("#"):
                    continue
                match = LINE.match(line)
                if not match:
                    continue
                raw_count += 1
                ts, proc, body = match.group("ts"), match.group("proc"), match.group("body").strip()

                if CHANNEL_STATE.search(body):
                    channel_lines.append(
                        (proc, body, bool(CHANNEL_EMPTY.search(body))))

                hdr = REPORT_HDR.search(body)
                if hdr:
                    current_report = hdr.group("snap")
                    reports.setdefault(current_report, [])
                    continue
                if current_report:
                    row = REPORT_ROW.match(body)
                    if row:
                        clk = parse_clock(row.group("clock"))
                        if clk:
                            reports[current_report].append(
                                (row.group("who"), clk, row.group("rest").strip()))
                            continue
                    if body.startswith("=") or "CONSISTENT" in body or not body:
                        current_report = None

                trig = SNAP_TRIG.match(body)
                if trig:
                    snapshots.setdefault(trig.group("snap"), {
                        "initiator": trig.group("who"), "markers": [],
                        "states": [], "progress": (0, N)})

                m = MARKER_RECV.match(body) or MARKER_RECV_ALT.match(body)
                if m:
                    markers.append((m.group("src"), m.group("dst"), m.group("snap"), "recv"))
                    entry = snapshots.setdefault(m.group("snap"), {
                        "initiator": None, "markers": [], "states": [],
                        "progress": (0, N)})
                    hop = (m.group("src"), m.group("dst"))
                    if hop not in entry["markers"]:
                        entry["markers"].append(hop)
                else:
                    m = MARKER_SENT.match(body)
                    if m:
                        markers.append((m.group("src"), m.group("dst"),
                                        m.group("snap") or "?", "sent"))

                m = STATE_RECV.match(body)
                if m:
                    snap = m.group("snap")
                    entry = snapshots.setdefault(snap, {
                        "initiator": None, "markers": [], "states": [],
                        "progress": (0, N)})
                    if m.group("src") not in entry["states"]:
                        entry["states"].append(m.group("src"))
                    prog = PROGRESS.search(body)
                    if prog:
                        entry["progress"] = (int(prog.group("got")), int(prog.group("total")))
                    states.append((m.group("src"), snap))
                else:
                    m = STATE_SENT.match(body)
                    if m:
                        states.append((m.group("src"), m.group("snap")))

                for kind, pattern in PATTERNS:
                    hit = pattern.match(body)
                    if not hit:
                        continue
                    groups = hit.groupdict()
                    clock = parse_clock(hit.group(hit.lastindex)) if hit.lastindex else None
                    if clock is None:
                        for gi in range(hit.lastindex or 0, 0, -1):
                            clock = parse_clock(hit.group(gi))
                            if clock:
                                break
                    if clock is None:
                        continue
                    who = groups.get("who") or proc
                    seq += 1
                    events.append(Event(
                        seq, ts, who, kind,
                        (groups.get("desc") or "").strip(), clock,
                        groups.get("peer"), body))
                    break

    return {
        "events": events, "markers": markers, "states": states,
        "snapshots": snapshots, "reports": reports,
        "channel_lines": channel_lines, "raw_count": raw_count,
        "files": files,
    }


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def dedupe_events(events):
    """The same event is often logged twice (once by vector_clock.py, once by
    the process's own logger). Collapse on (process, clock, kind)."""
    seen, out = {}, []
    for ev in events:
        key = (ev.proc, tuple(ev.clock), ev.kind)
        if key in seen:
            prior = seen[key]
            if len(ev.desc) > len(prior.desc):
                prior.desc = ev.desc
                prior.peer = prior.peer or ev.peer
            continue
        seen[key] = ev
        out.append(ev)
    return out


def causal_sort(events):
    """Order events so that a cause never appears after its effect."""
    return sorted(events, key=lambda e: (sum(e.clock), e.clock, e.proc))


def find_concurrent(events, limit=40):
    """Every pair of events at different processes with incomparable clocks."""
    pairs = []
    for i in range(len(events)):
        a = events[i]
        for j in range(i + 1, len(events)):
            b = events[j]
            if a.proc == b.proc:
                continue
            if concurrent(a.clock, b.clock):
                pairs.append((a, b))
    # The most convincing example is between two processes that never exchange
    # a message at all, and where both clocks have advanced.
    def score(pair):
        a, b = pair
        return (min(a.clock[int(a.proc[1])], b.clock[int(b.proc[1])]),
                sum(a.clock) + sum(b.clock))
    pairs.sort(key=score, reverse=True)
    return pairs, pairs[:limit]


def verify_consistency(recorded):
    """recorded: {proc: clock}. Check BOTH directions for every pair.

    A cut is causally consistent when no process's recorded clock knows about
    an event at another process that the other process had not yet recorded.
    """
    issues = []
    names = sorted(recorded)
    for i, pa in enumerate(names):
        for pb in names[i + 1:]:
            ca, cb = recorded[pa], recorded[pb]
            ia, ib = int(pa[1]), int(pb[1])
            if ca[ib] > cb[ib]:
                issues.append(
                    "{a}'s recorded clock {ca} shows {b} at {seen}, but {b} recorded "
                    "itself at {own}. {a}'s cut observes an event {b} had not taken."
                    .format(a=pa, b=pb, ca=ca, seen=ca[ib], own=cb[ib]))
            if cb[ia] > ca[ia]:
                issues.append(
                    "{b}'s recorded clock {cb} shows {a} at {seen}, but {a} recorded "
                    "itself at {own}. {b}'s cut observes an event {a} had not taken."
                    .format(a=pa, b=pb, cb=cb, seen=cb[ia], own=ca[ia]))
    return issues


def build_snapshot_view(data):
    out = {}
    for snap, info in data["snapshots"].items():
        recorded = {}
        for who, clock, rest in data["reports"].get(snap, []):
            recorded[who] = clock
        got, total = info["progress"]
        complete = (got >= total) or (len(recorded) >= N)
        out[snap] = {
            "initiator": info.get("initiator"),
            "markers": info.get("markers", []),
            "states": info.get("states", []),
            "progress": (max(got, len(recorded)), total),
            "recorded": recorded,
            "detail": {w: r for w, c, r in data["reports"].get(snap, [])},
            "complete": complete,
            "issues": verify_consistency(recorded) if len(recorded) >= 2 else [],
        }
    return out


MET, PARTIAL, UNMET = "MET", "PARTIAL", "NOT MET"


def requirement_checklist(events, conc_all, snaps, channel_lines):
    kinds = {k: 0 for k in ("internal", "send", "receive")}
    for ev in events:
        if ev.kind in kinds:
            kinds[ev.kind] += 1
    procs = sorted({ev.proc for ev in events})

    all_snaps = sorted(snaps)
    complete = [s for s in all_snaps if snaps[s]["complete"]]
    incomplete = [s for s in all_snaps if not snaps[s]["complete"]]
    consistent = [s for s in complete if not snaps[s]["issues"]]

    nonempty_channels = [c for c in channel_lines if not c[2]]

    def yn(ok):
        return MET if ok else UNMET

    rows = []
    rows.append(("At least 4 distributed processes",
                 yn(len(procs) >= 4),
                 "{} processes produced events: {}".format(len(procs), ", ".join(procs))))

    rows.append(("Messages representing order / delivery events",
                 yn(kinds["send"] > 0 and kinds["receive"] > 0),
                 "{} send and {} receive events observed".format(
                     kinds["send"], kinds["receive"])))

    rows.append(("Internal, send and receive events",
                 yn(all(v > 0 for v in kinds.values())),
                 "internal {}, send {}, receive {}".format(
                     kinds["internal"], kinds["send"], kinds["receive"])))

    rows.append(("Vector clocks for event timestamping",
                 yn(len(events) > 0),
                 "{} events carry a {}-element vector clock".format(len(events), N)))

    rows.append(("At least one pair of concurrent events",
                 yn(len(conc_all) > 0),
                 "{} concurrent pairs detected by clock comparison".format(len(conc_all))))

    if not all_snaps:
        snap_status, snap_detail = UNMET, "no snapshot was triggered"
    elif incomplete:
        snap_status = PARTIAL
        snap_detail = "{} of {} snapshots completed; {} never collected all {} states".format(
            len(complete), len(all_snaps), ", ".join(incomplete), N)
    else:
        snap_status = MET
        snap_detail = "all {} snapshot(s) collected {} process states".format(len(all_snaps), N)
    rows.append(("Global snapshot recording algorithm", snap_status, snap_detail))

    if nonempty_channels:
        chan_status = MET
        chan_detail = "{} channel state record(s) with captured messages".format(
            len(nonempty_channels))
    elif channel_lines:
        chan_status = PARTIAL
        chan_detail = ("{} channel record(s) found, all empty — no in-transit "
                       "message was ever captured".format(len(channel_lines)))
    else:
        chan_status = UNMET
        chan_detail = "no channel state recorded, transmitted or reported anywhere"
    rows.append(("State of each process AND communication channel",
                 chan_status, chan_detail))

    if not complete:
        cons_status = UNMET
        cons_detail = "no snapshot completed, so no global cut could be verified"
    elif incomplete:
        cons_status = PARTIAL
        cons_detail = "{} of {} completed cut(s) verified consistent; {} incomplete".format(
            len(consistent), len(complete), len(incomplete))
    else:
        cons_status = MET if len(consistent) == len(complete) else PARTIAL
        cons_detail = "{} of {} cut(s) verified causally consistent".format(
            len(consistent), len(complete))
    rows.append(("Explain whether the captured global state is consistent",
                 cons_status, cons_detail))

    return rows, kinds, procs


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------

CSS = """
*{box-sizing:border-box}
body{margin:0;background:#fff;color:#16191d;
 font:14px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:36px 30px 80px}
h1{font-size:27px;margin:0 0 6px;letter-spacing:-.02em}
h2{font-size:19px;margin:38px 0 10px;padding-bottom:6px;border-bottom:2px solid #16191d}
h3{font-size:14px;margin:22px 0 8px;text-transform:uppercase;letter-spacing:.07em;color:#5a6472}
.sub{color:#5a6472;font-size:13px;margin:0 0 4px}
.meta{border-top:2px solid #16191d;margin-top:14px;padding-top:12px;
 display:flex;flex-wrap:wrap;gap:10px 30px;font-size:12.5px;color:#5a6472}
table{border-collapse:collapse;width:100%;margin:10px 0 18px;font-size:13px}
th,td{text-align:left;padding:7px 11px;border-bottom:1px solid #e4e7eb;vertical-align:top}
th{background:#f2f4f6;font-size:11px;text-transform:uppercase;letter-spacing:.06em;
 color:#4a5260;border-bottom:2px solid #ccd1d8}
td.mono,th.mono,.mono{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;
 font-size:12px;font-variant-numeric:tabular-nums}
.scroll{overflow-x:auto}
.pill{display:inline-block;padding:1px 8px;border-radius:2px;font-size:11px;
 font-weight:600;letter-spacing:.03em}
.yes{background:#e3f4e8;color:#14663a}
.no{background:#fbe4e2;color:#a2231c}
.part{background:#fdf2dc;color:#8a5a08}
.callout{border-left:3px solid #0f6e73;background:#f2fafa;padding:12px 16px;margin:14px 0}
.callout.bad{border-left-color:#b3261e;background:#fdf3f2}
.callout p{margin:0 0 6px}.callout p:last-child{margin:0}
.k{display:inline-block;min-width:118px;color:#5a6472;font-size:12px}
.small{font-size:12px;color:#5a6472}
ul{margin:6px 0 14px;padding-left:20px}li{margin-bottom:4px}
.foot{margin-top:48px;padding-top:14px;border-top:1px solid #ccd1d8;
 font-size:12px;color:#5a6472}
@media print{
 .wrap{max-width:none;padding:0}
 h2{page-break-after:avoid}table{page-break-inside:auto}
 tr{page-break-inside:avoid}body{font-size:11px}
}
"""


def esc(x):
    return html.escape(str(x))


def clk(c):
    return "[" + ",".join(str(v) for v in c) + "]"


def render_html(data, events, conc_all, conc_top, snaps, checklist, kinds, procs, meta):
    p = []
    a = p.append

    a("<!doctype html><html><head><meta charset='utf-8'>")
    a("<title>Run Evidence — Group 2 Distributed Food Delivery</title>")
    a("<style>{}</style></head><body><div class='wrap'>".format(CSS))

    a("<p class='sub'>GROUP 2 &nbsp;·&nbsp; CCZG 526 DISTRIBUTED COMPUTING &nbsp;·&nbsp; LAB ASSIGNMENT I</p>")
    a("<h1>Execution Evidence Report</h1>")
    a("<p class='sub'>Generated automatically from captured process logs by analyse_run.py</p>")

    a("<div class='meta'>")
    a("<div><span class='k'>Run</span> <span class='mono'>{}</span></div>".format(
        esc(meta.get("run_id", "n/a"))))
    a("<div><span class='k'>Started</span> {}</div>".format(esc(meta.get("started_at", "n/a"))))
    a("<div><span class='k'>Duration</span> {}s</div>".format(esc(meta.get("duration_seconds", "n/a"))))
    a("<div><span class='k'>Analysed</span> {}</div>".format(time.strftime("%Y-%m-%d %H:%M:%S")))
    a("</div>")

    node_ips = meta.get("node_ips") or {}
    if node_ips:
        distinct = len({v for v in node_ips.values() if v})
        mode = ("three distinct VMs" if distinct == 3
                else "single host" if distinct == 1 else "partially configured")
        a("<p class='small' style='margin-top:10px'>Deployment: <strong>{}</strong> — {}</p>"
          .format(esc(mode),
                  esc(", ".join("{}={}".format(k, v or "unset") for k, v in sorted(node_ips.items())))))

    # ---- 1. Requirement checklist -----------------------------------------
    a("<h2>1. Requirement coverage</h2>")
    a("<p class='small'>Derived from what the run actually produced, not from what the code intends to do.</p>")
    pill_class = {MET: "yes", PARTIAL: "part", UNMET: "no"}
    a("<div class='scroll'><table><tr><th style='width:42%'>Requirement</th>"
      "<th style='width:11%'>Result</th><th>Evidence from this run</th></tr>")
    for req, status, detail in checklist:
        a("<tr><td>{}</td><td><span class='pill {}'>{}</span></td><td class='small'>{}</td></tr>"
          .format(esc(req), pill_class[status], status, esc(detail)))
    a("</table></div>")

    gaps = [(r, s, d) for r, s, d in checklist if s != MET]
    if gaps:
        a("<div class='callout bad'><p><strong>{} requirement(s) not fully demonstrated "
          "by this run.</strong></p><ul>".format(len(gaps)))
        for req, status, detail in gaps:
            a("<li><strong>{}</strong> — {}<br><span class='small'>{}</span></li>"
              .format(esc(req), status, esc(detail)))
        a("</ul><p class='small'>These are the gaps to close before submission.</p></div>")
    else:
        a("<div class='callout'><p><strong>All eight requirements demonstrated by this run.</strong></p></div>")

    # ---- 2. Process activity ----------------------------------------------
    a("<h2>2. Process activity</h2>")
    per = {}
    for ev in events:
        d = per.setdefault(ev.proc, {"internal": 0, "send": 0, "receive": 0, "snapshot": 0})
        if ev.kind in d:
            d[ev.kind] += 1
    a("<table><tr><th>Process</th><th>Role</th><th class='mono'>Internal</th>"
      "<th class='mono'>Send</th><th class='mono'>Receive</th><th class='mono'>Final clock</th></tr>")
    for name in PROCESS_NAMES:
        d = per.get(name)
        if not d:
            a("<tr><td class='mono'>{}</td><td class='small'>{}</td>"
              "<td colspan='4' class='small'>no events captured</td></tr>"
              .format(name, esc(ROLE[name])))
            continue
        last = max((e for e in events if e.proc == name), key=lambda e: sum(e.clock))
        a("<tr><td class='mono'>{}</td><td class='small'>{}</td><td class='mono'>{}</td>"
          "<td class='mono'>{}</td><td class='mono'>{}</td><td class='mono'>{}</td></tr>"
          .format(name, esc(ROLE[name]), d["internal"], d["send"], d["receive"], clk(last.clock)))
    a("</table>")

    # ---- 3. Concurrency ----------------------------------------------------
    a("<h2>3. Concurrent events</h2>")
    if conc_all:
        a("<div class='callout'><p><strong>{} concurrent pairs found.</strong> "
          "Two events are concurrent when neither vector clock is less than or equal to "
          "the other, so neither event could have influenced the other.</p></div>"
          .format(len(conc_all)))
        a("<div class='scroll'><table><tr><th>Event A</th><th class='mono'>Clock A</th>"
          "<th>Event B</th><th class='mono'>Clock B</th><th>Why incomparable</th></tr>")
        for ea, eb in conc_top[:14]:
            ia, ib = int(ea.proc[1]), int(eb.proc[1])
            why = ("A[{ib}]={x} &lt; B[{ib}]={y} but A[{ia}]={u} &gt; B[{ia}]={v}"
                   .format(ia=ia, ib=ib, x=ea.clock[ib], y=eb.clock[ib],
                           u=ea.clock[ia], v=eb.clock[ia]))
            a("<tr><td class='small'><span class='mono'>{}</span> {}</td><td class='mono'>{}</td>"
              "<td class='small'><span class='mono'>{}</span> {}</td><td class='mono'>{}</td>"
              "<td class='small mono'>{}</td></tr>"
              .format(ea.proc, esc(ea.desc or ea.kind), clk(ea.clock),
                      eb.proc, esc(eb.desc or eb.kind), clk(eb.clock), why))
        a("</table></div>")
        if len(conc_all) > 14:
            a("<p class='small'>Showing the 14 clearest of {} pairs.</p>".format(len(conc_all)))
    else:
        a("<div class='callout bad'><p>No concurrent pairs were found. The assignment "
          "requires at least one. Either the run was too short for the two restaurant "
          "branches to overlap, or events were serialised by the message pattern.</p></div>")

    # ---- 4. Snapshots -------------------------------------------------------
    a("<h2>4. Global snapshots</h2>")
    if not snaps:
        a("<div class='callout bad'><p>No snapshot was triggered during this run.</p></div>")
    for snap in sorted(snaps):
        v = snaps[snap]
        got, total = v["progress"]
        a("<h3>{} &nbsp;—&nbsp; {}</h3>".format(
            esc(snap),
            "<span class='pill yes'>COMPLETE</span>" if v["complete"]
            else "<span class='pill no'>INCOMPLETE {}/{}</span>".format(got, total)))

        if v["initiator"]:
            a("<p class='small'>Initiated by <span class='mono'>{}</span>. "
              "Markers observed: {}. States delivered: {}.</p>"
              .format(esc(v["initiator"]),
                      esc(", ".join("{}→{}".format(s, d) for s, d in v["markers"]) or "none"),
                      esc(", ".join(v["states"]) or "none")))

        if v["recorded"]:
            a("<table><tr><th>Process</th><th class='mono'>Recorded vector clock</th>"
              "<th>Recorded local state</th></tr>")
            for name in PROCESS_NAMES:
                if name not in v["recorded"]:
                    continue
                a("<tr><td class='mono'>{}</td><td class='mono'>{}</td><td class='small'>{}</td></tr>"
                  .format(name, clk(v["recorded"][name]), esc(v["detail"].get(name, ""))))
            a("</table>")

            if v["issues"]:
                a("<div class='callout bad'><p><strong>Cut is NOT causally consistent.</strong></p><ul>")
                for issue in v["issues"]:
                    a("<li class='small'>{}</li>".format(esc(issue)))
                a("</ul></div>")
            else:
                a("<div class='callout'><p><strong>Cut is causally consistent.</strong> "
                  "Checked in both directions for every pair of processes: no recorded clock "
                  "observes an event at another process beyond that process's own recorded "
                  "clock, so the cut contains no orphan message.</p></div>")
        else:
            a("<p class='small'>No per-process state table was produced for this snapshot.</p>")

        if not v["complete"]:
            a("<div class='callout bad'><p>This snapshot never collected all {} states, so no "
              "global cut exists for it. Everything above is a partial record.</p></div>".format(N))

    # ---- 5. Channel state ---------------------------------------------------
    a("<h2>5. Communication channel state</h2>")
    if data["channel_lines"]:
        nonempty = [c for c in data["channel_lines"] if not c[2]]
        a("<table><tr><th>Process</th><th>Contents</th><th>Record</th></tr>")
        for who, body, is_empty in data["channel_lines"][:30]:
            a("<tr><td class='mono'>{}</td><td class='small mono'>{}</td>"
              "<td><span class='pill {}'>{}</span></td></tr>"
              .format(who, esc(body), "part" if is_empty else "yes",
                      "EMPTY" if is_empty else "HAS MESSAGES"))
        a("</table>")
        if not nonempty:
            a("<div class='callout bad'><p><strong>Every recorded channel was empty.</strong></p>"
              "<p class='small'>An empty channel is a legitimate Chandy-Lamport outcome, but on "
              "its own it does not demonstrate the requirement. The marker protocol exists to "
              "capture messages that were sent before the sender recorded its state and received "
              "after the receiver recorded its own — those belong to the channel, not to either "
              "process. To show one, trigger a snapshot while a message is genuinely in flight.</p></div>")
    else:
        a("<div class='callout bad'><p><strong>No channel state was recorded anywhere in this run.</strong></p>"
          "<p class='small'>The assignment requires the recorded snapshot to show the state of each "
          "process <em>and</em> each communication channel. In-transit messages are the whole "
          "point of the marker protocol: a message sent before the sender recorded its state but "
          "received after the receiver recorded its own belongs to the channel, not to either "
          "process. Nothing in this run captured one.</p></div>")

    # ---- 6. Timeline --------------------------------------------------------
    a("<h2>6. Causally ordered event timeline</h2>")
    a("<p class='small'>Ordered by vector clock, not by wall-clock time — no shared clock exists. "
      "A cause never appears below its effect.</p>")
    a("<div class='scroll'><table><tr><th class='mono'>#</th><th>Process</th><th>Type</th>"
      "<th>Description</th><th class='mono'>Vector clock</th><th class='small'>Wall clock</th></tr>")
    for i, ev in enumerate(events, 1):
        a("<tr><td class='mono'>{}</td><td class='mono'>{}</td><td class='small'>{}</td>"
          "<td class='small'>{}</td><td class='mono'>{}</td><td class='small mono'>{}</td></tr>"
          .format(i, ev.proc, ev.kind.upper(), esc(ev.desc or "—"),
                  clk(ev.clock), esc(ev.ts.split("T")[-1] if "T" in ev.ts else ev.ts)))
    a("</table></div>")

    a("<div class='foot'>Generated by <span class='mono'>analyse_run.py</span> from "
      "{} log lines across {} files. Infrastructure, deployment and verification tooling "
      "by Sohail.</div>".format(data["raw_count"], len(data["files"])))
    a("</div></body></html>")
    return "\n".join(p)


# ---------------------------------------------------------------------------

def console_summary(events, conc_all, snaps, checklist, data):
    print()
    print("=" * 72)
    print(" RUN ANALYSIS")
    print("=" * 72)
    print("  {} log lines -> {} distinct events across {} processes"
          .format(data["raw_count"], len(events), len({e.proc for e in events})))
    print("  {} concurrent pairs".format(len(conc_all)))
    print("  {} snapshot(s): {}".format(
        len(snaps),
        ", ".join("{} {}".format(s, "complete" if v["complete"]
                                 else "INCOMPLETE {}/{}".format(*v["progress"]))
                  for s, v in sorted(snaps.items())) or "none"))
    print()
    tag = {MET: "[ ok ]", PARTIAL: "[part]", UNMET: "[FAIL]"}
    print("  REQUIREMENT COVERAGE")
    for req, status, detail in checklist:
        print("    {} {:<52} {}".format(tag[status], req[:52], detail[:64]))
    print()
    gaps = [r for r, s, _ in checklist if s != MET]
    if gaps:
        print("  {} requirement(s) not fully demonstrated:".format(len(gaps)))
        for req in gaps:
            print("    - {}".format(req))
        print()
    bad = [s for s, v in snaps.items() if v["complete"] and v["issues"]]
    if bad:
        print("  CONSISTENCY PROBLEMS in: {}".format(", ".join(bad)))
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Turn captured run logs into evidence for the report.")
    # Defaults sit beside this file so the tools work identically whether they
    # live in their own repo or inside the team's checkout.
    here = os.path.dirname(os.path.abspath(__file__))
    parser.add_argument("--logdir", default=os.path.join(here, "logs"),
                        help="directory of .log files (default: logs/ beside this script)")
    parser.add_argument("--out", default=os.path.join(here, "report"),
                        help="output directory (default: report/ beside this script)")
    parser.add_argument("--csv", action="store_true", help="also write the timeline as CSV")
    args = parser.parse_args()

    logdir = os.path.abspath(args.logdir)
    if not os.path.isdir(logdir):
        sys.exit("[ERROR] No such directory: {}\n"
                 "        Capture a run first:  python3 run_demo.py --all --auto".format(logdir))

    data = parse_logs(logdir)
    events = causal_sort(dedupe_events(data["events"]))
    conc_all, conc_top = find_concurrent(events)
    snaps = build_snapshot_view(data)
    checklist, kinds, procs = requirement_checklist(
        events, conc_all, snaps, data["channel_lines"])

    meta = {}
    meta_path = os.path.join(logdir, "run-meta.json")
    if os.path.isfile(meta_path):
        try:
            with open(meta_path) as fh:
                meta = json.load(fh)
        except (OSError, ValueError):
            pass

    os.makedirs(args.out, exist_ok=True)
    stamp = meta.get("run_id") or time.strftime("%Y%m%d-%H%M%S")
    html_path = os.path.join(args.out, "run-{}.html".format(stamp))
    with open(html_path, "w") as fh:
        fh.write(render_html(data, events, conc_all, conc_top, snaps,
                             checklist, kinds, procs, meta))

    console_summary(events, conc_all, snaps, checklist, data)
    print("  Report written to {}".format(os.path.relpath(html_path)))

    if args.csv:
        csv_path = os.path.join(args.out, "timeline-{}.csv".format(stamp))
        with open(csv_path, "w", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["order", "process", "type", "description",
                             "vector_clock", "wall_clock"])
            for i, ev in enumerate(events, 1):
                writer.writerow([i, ev.proc, ev.kind, ev.desc, clk(ev.clock), ev.ts])
        print("  Timeline CSV    {}".format(os.path.relpath(csv_path)))

    print("  Open it in a browser and print to PDF for the submission.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
