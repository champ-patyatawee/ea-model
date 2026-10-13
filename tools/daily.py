#!/usr/bin/env python3
"""Day-by-day P/L extracted from the MT5 tester log.

Because the EA trades a FIXED lot (InpFixedLot=0.02) the per-trade P/L does not
depend on the account equity, so a single continuous monthly run already gives
the honest "what if I started every day with $100" numbers - as long as the
month did not blow the account up. This avoids running one tester job per day
(each job costs ~60s of terminal startup).

Usage:
  python3 tools/daily.py <from> <to> [field=value ...] [--log PATH]

Example:
  python3 tools/daily.py 2026.09.01 2026.10.01 InpDirByDepth=1 InpTPByDir=0
"""

import re
import sys
from collections import OrderedDict

import bt

PL_RE = re.compile(r"Core 01\t(\d{4}\.\d{2}\.\d{2}) \S+\s+.*MFELOG.*P/L=(-?[\d.]+)")
OPEN_RE = re.compile(r"Core 01\t(\d{4}\.\d{2}\.\d{2}) \S+\s+.*(ORDER OPENED|ORDER REJECTED|not enough money)")


def select(runs, frm, to, **want):
    out = []
    expert = want.pop("expert", None)
    for r in runs:
        if r["from"] != frm or r["to"] != to:
            continue
        if r["final"] is None:
            continue
        if expert and r["expert"] != expert:
            continue
        if all(r["params"].get(k) == v for k, v in want.items()):
            out.append(r)
    return out


def day_table(lines, start, end):
    days = OrderedDict()
    for line in lines:
        m = PL_RE.search(line)
        if not m:
            continue
        d, pl = m.group(1), float(m.group(2))
        days.setdefault(d, []).append(pl)
    rows = []
    for d in sorted(days):
        if not (start <= d <= end):
            continue
        pls = days[d]
        rows.append((d, sum(pls), len(pls), sum(1 for p in pls if p > 0),
                     sum(1 for p in pls if p <= 0)))
    return rows


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    frm, to = sys.argv[1], sys.argv[2]
    want = {}
    log = None
    for a in sys.argv[3:]:
        if a.startswith("--log="):
            log = a.split("=", 1)[1]
        elif "=" in a:
            k, v = a.split("=", 1)
            want[k] = v
    if log is None:
        log = bt.newest_log()
    lines = open(log, encoding="utf-8", errors="replace").read().split("\n")
    runs = bt.parse_log(log)
    cand = select(runs, frm, to, **want)
    if not cand:
        raise SystemExit("no run matches %s -> %s %s" % (frm, to, want))
    if len(cand) > 1:
        print("WARNING: %d runs match, using the last" % len(cand))
    r = cand[-1]

    rows = day_table(lines[r["line"]:r["endline"]], frm, to)
    total = sum(x[1] for x in rows)
    print("run: %s %s -> %s   final balance %.2f   (deposit 100)" %
          (r["expert"], frm, to, r["final"]))
    print()
    print("%-12s %10s %6s %6s %6s" % ("day", "P/L", "trades", "win", "loss"))
    for d, pl, n, w, l in rows:
        print("%-12s %10.2f %6d %6d %6d" % (d, pl, n, w, l))
    print()
    if rows:
        w = sum(1 for x in rows if x[1] > 0)
        l = sum(1 for x in rows if x[1] < 0)
        best = max(rows, key=lambda x: x[1])
        worst = min(rows, key=lambda x: x[1])
        print("days=%d  winning=%d  losing=%d  flat=%d" % (len(rows), w, l, len(rows) - w - l))
        print("total P/L %.2f   best %s %+.2f   worst %s %+.2f" %
              (total, best[0], best[1], worst[0], worst[1]))


if __name__ == "__main__":
    main()
