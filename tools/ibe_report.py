#!/usr/bin/env python3
"""Turn one ImpulseBasketEA equity path into the brief's decision metrics.

Why this exists: the brief's metric is EV per run with a $1,000 deposit and a
run that blows up counted as -$1,000, but 12 monthly runs are 12 samples --
not enough to measure a blow-up rate. Because the EA trades a FIXED lot, the
dollar P/L path does not depend on the account balance, so ONE continuous run
at a large deposit gives the honest price path for every possible starting
day. Every start day of a 21-trading-day window then becomes its own run:

    EV per run = (sum of window P/L with blow-ups floored at -D) / n_windows

with a blow-up counted whenever the equity falls D below the window's own
starting equity. That is the same accounting as "deposit D, run until the
account dies or the window ends", just measured on ~240 windows instead of 12.

Usage
  python3 tools/ibe_report.py <equity.csv> [deposit] [window_days]
"""
import sys
from collections import OrderedDict


def load(path):
    bal, eq, tstamp = [], [], []
    for line in open(path):
        p = line.strip().split(",")
        if len(p) != 7 or p[0] == "time":
            continue
        bal.append(float(p[1]))
        eq.append(float(p[2]))
        tstamp.append(p[0])
    return bal, eq, tstamp


def month_key(s):
    return s[:7]


def day_key(s):
    return s[:10]


def window_stats(eq, starts, dep):
    """starts: list of (begin_index, end_index); returns EV table rows."""
    rows = []
    for i0, i1 in starts:
        e0 = eq[i0]
        lowest = min(eq[i0:i1 + 1])
        dd = e0 - lowest
        pl = eq[i1] - e0
        if dd >= dep:
            pl = -dep
        rows.append((pl, dd, pl))
    return rows


def main():
    path = sys.argv[1]
    dep = float(sys.argv[2]) if len(sys.argv) > 2 else 1000.0
    wdays = int(sys.argv[3]) if len(sys.argv) > 3 else 21
    bal, eq, ts = load(path)
    n = len(eq)
    if n < 100:
        raise SystemExit("too few rows: %d" % n)
    print("samples=%d  %s -> %s" % (n, ts[0], ts[-1]))
    print("balance %.2f -> %.2f   equity %.2f -> %.2f   maxDD %.2f" %
          (bal[0], bal[-1], eq[0], eq[-1], max(eq[i] - min(eq[i:]) for i in range(0, n, 97))))

    # ---- trading days present in the path ---------------------------
    days = OrderedDict()
    for i, s in enumerate(ts):
        days.setdefault(day_key(s), i)
    day_list = list(days.items())

    # ---- calendar-month runs (EV per month, the brief's headline）----
    months = OrderedDict()
    for i, s in enumerate(ts):
        months.setdefault(month_key(s), [i, i])
        months[month_key(s)][1] = i
    print("\n=== calendar-month runs (deposit %.0f) ===" % dep)
    print("%-9s %10s %10s %8s  %s" % ("month", "P/L", "maxDD", "days", "counted"))
    tot = 0.0
    ruins = 0
    for k, (i0, i1) in months.items():
        e0 = eq[i0]
        dd = e0 - min(eq[i0:i1 + 1])
        pl = eq[i1] - e0
        died = dd >= dep
        counted = -dep if died else pl
        tot += counted
        ruins += 1 if died else 0
        print("%-9s %10.2f %10.2f %8d  %s" % (k, pl, dd,
              len(set(day_key(s) for s in ts[i0:i1 + 1])), "RUIN" if died else ""))
    nm = len(months)
    print("months=%d  ruined=%d (%.0f%%)  sum(P/L)=%.2f  EV/run=%.2f" %
          (nm, ruins, 100.0 * ruins / nm, tot, tot / nm))

    # ---- rolling-window runs ---------------------------------------
    starts = []
    for a in range(len(day_list)):
        b = a + wdays - 1
        if b >= len(day_list):
            break
        starts.append((day_list[a][1], day_list[b][1]))
    print("\n=== rolling %d-trading-day windows (deposit %.0f), n=%d ===" %
          (wdays, dep, len(starts)))
    for d in (dep,):
        rows = window_stats(eq, starts, d)
        pls = sorted(r[0] for r in rows)
        ruin = sum(1 for r in rows if r[1] >= d)
        mean = sum(p for p in pls) / len(pls)
        print("deposit %7.0f: EV/run %+8.2f   ruin %5.1f%% (%d/%d)   median %+8.2f   p05 %+8.2f   worst %+8.2f   best %+8.2f" %
              (d, mean, 100.0 * ruin / len(rows), ruin, len(rows),
               pls[len(pls) // 2], pls[int(0.05 * len(pls))], pls[0], pls[-1]))
    for d in (250, 500, 2000, 5000):
        rows = window_stats(eq, starts, d)
        ruin = sum(1 for r in rows if r[1] >= d)
        mean = sum(r[0] for r in rows) / len(rows)
        print("deposit %7.0f: EV/run %+8.2f   ruin %5.1f%%" % (d, mean, 100.0 * ruin / len(rows)))

    # ---- day-level distribution ------------------------------------
    daypl = []
    for i in range(1, len(day_list)):
        i0 = day_list[i - 1][1]
        i1 = day_list[i][1]
        daypl.append((day_list[i][0], eq[i1] - eq[i0], eq[i0] - min(eq[i0:i1 + 1])))
    pls = sorted(x[1] for x in daypl)
    wins = sum(1 for x in pls if x > 0)
    dds = sorted(x[2] for x in daypl)
    print("\n=== trading days: n=%d ===" % len(daypl))
    print("mean %+7.2f  median %+7.2f  win%% %4.1f  best %+8.2f  worst %+8.2f  "
          "meanDD %6.2f  worstDD %8.2f" %
          (sum(pls) / len(pls), pls[len(pls) // 2], 100.0 * wins / len(pls),
           pls[-1], pls[0], sum(dds) / len(dds), dds[-1]))
    print("day P/L deciles: " + " ".join("%+.1f" % pls[int(q * (len(pls) - 1))] for q in
                                         (0.0, .1, .2, .3, .4, .5, .6, .7, .8, .9, 1.0)))


if __name__ == "__main__":
    main()
