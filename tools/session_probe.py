#!/usr/bin/env python3
"""Test the two documented session edges on OUR XAUUSD M5 data.

The impulse study (tools/edge_probe.py) showed that a bar-relative impulse has
too small an edge to pay a 0.25 $/oz round trip, and that the basket family
loses to the tail. The literature points somewhere else: session-ANCHORED,
low-frequency, bounded-risk trades.

  1. Market intraday momentum (Gao, Han, Li & Zhou, JFE 2018): the first
     half-hour/hour return of the session predicts the last half-hour return.
  2. Opening Range Breakout (Zarattini & Aziz 2023/2024): break the first
     N-minute range, stop at the opposite end of the range, hold to the close.

Both are testable straight from the 3.8-year M5 dump that ImpulseProbeEA wrote,
so nothing here costs a tester run. Everything is reported in $/oz next to the
0.25 $/oz round-trip cost, and per-trade R for the ORB version.

Usage: python3 tools/session_probe.py /tmp/impulse_probe.csv [start_hour] [range_hours]
"""
import sys
from collections import defaultdict

import numpy as np

COST = 0.25   # round-trip spread, $/oz (measured from real ticks, see research/impulse-basket.md)


def load(path):
    day = []
    dates, hours, mins, o, h, l, c = [], [], [], [], [], [], []
    for line in open(path):
        if line.startswith("#") or line.startswith("idx"):
            continue
        p = line.strip().split(",")
        if len(p) < 8:
            continue
        t = p[1]                      # "2023.01.03 07:30"
        dates.append(t[:10])
        hours.append(int(t[11:13]))
        mins.append(int(t[14:16]))
        o.append(float(p[4])); h.append(float(p[5])); l.append(float(p[6])); c.append(float(p[7]))
    return (np.array(dates), np.array(hours), np.array(mins),
            np.array(o), np.array(h), np.array(l), np.array(c))


def tstat(x):
    x = np.asarray(x, dtype=float)
    n = len(x)
    if n < 2:
        return 0.0, 0.0, n
    m = x.mean()
    sd = x.std(ddof=1)
    return m, (m / (sd / np.sqrt(n)) if sd > 0 else 0.0), n


def main():
    path = sys.argv[1]
    H0 = int(sys.argv[2]) if len(sys.argv) > 2 else 8     # session/range start (server hour)
    RW = int(sys.argv[3]) if len(sys.argv) > 3 else 1     # range window, hours

    dates, hours, mins, o, h, l, c = load(path)
    print("bars=%d  %s -> %s   cost=%.2f $/oz round trip" %
          (len(dates), dates[0], dates[-1], COST))

    # ---- hourly volatility profile (also tells us the server-time offset) ----
    ret = np.abs(np.diff(c))
    prof = np.zeros(24); cnt = np.zeros(24)
    for i in range(1, len(c)):
        prof[hours[i]] += ret[i - 1]
        cnt[hours[i]] += 1
    print("\nhourly mean |M5 return| in $/oz (server hour):")
    print("  " + " ".join("%d:%.2f" % (hh, prof[hh] / max(cnt[hh], 1)) for hh in range(24)))

    # ---- build per-day index ranges -----------------------------------------
    days = defaultdict(list)
    for i, d in enumerate(dates):
        days[d].append(i)
    day_list = [(d, v[0], v[-1]) for d, v in sorted(days.items()) if len(v) > 200]
    print("days=%d" % len(day_list))

    # ================= 1. market intraday momentum ==========================
    first, last, eod, nxt = [], [], [], []
    for d, i0, i1 in day_list:
        hh = hours[i0:i1 + 1]
        oo = o[i0:i1 + 1]; cc = c[i0:i1 + 1]; ll = l[i0:i1 + 1]; hh_ = h[i0:i1 + 1]
        m = (hh >= H0) & (hh < H0 + RW)                 # first RW hours of the session
        if m.sum() < RW * 6:
            continue
        a = np.where(m)[0][0]; b = np.where(m)[0][-1]
        # The signal window and the traded window MUST be disjoint, otherwise
        # the "prediction" is just the signal measuring itself. This is the trap
        # that makes first-hour -> whole-day "momentum" look enormous.
        first.append(cc[b] - oo[a])                     # signal: window open -> window close
        eod.append(cc[-1] - cc[b])                      # disjoint: end of window -> day close

    first = np.array(first)
    eod = np.array(eod)
    print("\n=== 1. MIM (disjoint): first %dh return (from %02d:00) vs the rest of the day ==="
          % (RW, H0))
    up = first > 0
    base_m, base_t, base_n = tstat(eod)
    print("days=%d   P(up first window)=%.1f%%   UNCONDITIONAL rest-of-day drift %+7.3f $/oz (t %+5.2f)"
          % (len(first), 100.0 * up.mean(), base_m, base_t))
    for lab, sel in (("first-window UP ", up), ("first-window DOWN", ~up)):
        e = eod[sel]
        mm, tt, nn = tstat(e)
        print("  %s n=%4d  mean rest-of-day %+7.3f $/oz (t %+5.2f)  win%% %4.1f  "
              "vs unconditional %+7.3f" %
              (lab, nn, mm, tt, 100.0 * (e > 0).mean(), mm - base_m))
    # tradeable version: enter at the end of the window in the window's direction, exit at the close
    tr = np.sign(first) * eod                      # $/oz, gross
    mm, tt, nn = tstat(tr)
    print("  TRADE (session-open direction, hold to close): mean %+7.3f $/oz (t %+5.2f), "
          "win%% %4.1f, after cost %+7.3f  -> per 0.02 lot $%+.2f" %
          (mm, tt, 100.0 * (tr > 0).mean(), mm - COST, (mm - COST) * 2))
    # drift-free control: same trade with the sign of the move of the previous window
    print("  drift-free control (random-signed trade): mean %+7.3f $/oz" % (np.sign(np.random.RandomState(0).randn(len(eod))) * eod).mean())

    # ================= 2. opening range breakout ============================
    print("\n=== 2. ORB: break the %02d:00-%02d:00 range, stop at the other end, exit at close ==="
          % (H0, H0 + RW))
    res = []      # (R multiple, $/oz, whether the stop was hit, dir)
    for d, i0, i1 in day_list:
        hh = hours[i0:i1 + 1]
        oo = o[i0:i1 + 1]; cc = c[i0:i1 + 1]; ll = l[i0:i1 + 1]; hh_ = h[i0:i1 + 1]
        m = (hh >= H0) & (hh < H0 + RW)
        if m.sum() < RW * 6:
            continue
        a = np.where(m)[0][0]; b = np.where(m)[0][-1]
        rng_hi = hh_[a:b + 1].max(); rng_lo = ll[a:b + 1].min()
        after = slice(b + 1, len(cc))
        if len(cc[after]) < 20:
            continue
        up_break = np.where(cc[after] > rng_hi)[0]
        dn_break = np.where(cc[after] < rng_lo)[0]
        iu = up_break[0] if len(up_break) else 10 ** 9
        idn = dn_break[0] if len(dn_break) else 10 ** 9
        if iu == idn == 10 ** 9:
            continue
        if iu <= idn:
            k = iu + b + 1; dirn = 1.0; stop = rng_lo
        else:
            k = idn + b + 1; dirn = -1.0; stop = rng_hi
        entry = cc[k]
        risk = abs(entry - stop)
        if risk <= 0:
            continue
        path = slice(k + 1, len(cc))
        if len(cc[path]) == 0:
            continue
        if dirn > 0:
            mfe = hh_[path].max() - entry
            mae = ll[path].min() - entry
        else:
            mfe = entry - ll[path].min()
            mae = entry - hh_[path].max()
        exitp = cc[-1]
        pl = (exitp - entry) * dirn
        res.append((pl / risk, pl, (mae <= -risk), dirn, rng_hi - rng_lo, mfe / risk))

    R = np.array([x[0] for x in res]); P = np.array([x[1] for x in res])
    stopped = np.array([x[2] for x in res]); dirs = np.array([x[3] for x in res])
    ranges = np.array([x[4] for x in res]); mfeR = np.array([x[5] for x in res])
    mr, tr, n = tstat(R)
    mp, tp, _ = tstat(P)
    print("trades=%d (break rate %.1f%%)  long %.0f%% / short %.0f%%  mean opening range $%.2f/oz" %
          (n, 100.0 * n / len(day_list), 100.0 * (dirs > 0).mean(), 100.0 * (dirs < 0).mean(),
           ranges.mean()))
    print("  mean R to the close: %+6.3f (t %+5.2f)   mean $/oz %+7.3f (t %+5.2f)  "
          "after cost %+7.3f  -> per 0.02 lot $%+.2f" %
          (mr, tr, mp, tp, mp - COST, (mp - COST) * 2))
    print("  hit rate %4.1f%%   %% where the opposite side of the range was touched before the close: %.1f%%"
          % (100.0 * (P > 0).mean(), 100.0 * stopped.mean()))
    print("  mean MFE in R before the close: %+5.2f R" % mfeR.mean())
    for k in (1, 2, 3, 5):
        print("    target %dR: %.1f%% of days reach it (in R terms)" % (k, 100.0 * (mfeR >= k).mean()))


if __name__ == "__main__":
    main()
