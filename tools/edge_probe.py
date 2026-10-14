#!/usr/bin/env python3
"""Question 1: does an impulse candle carry a real edge?

Reads the CSV written by ImpulseProbeEA.mq5 (one row per M5 bar, forward
returns measured from the open of the bar AFTER the signal) and reports the
conditional forward drift, its t-statistic, and -- the part that decides
everything -- the drift in dollars per ounce next to the real round-trip
spread cost.

  python3 tools/edge_probe.py /tmp/impulse_probe.csv
"""
import sys
import numpy as np

HOR = [1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48]
SPREAD = 0.24          # measured XAUUSDm round-trip spread, $/oz


def load(path):
    hdr = None
    rows = []
    for line in open(path):
        if line.startswith("###"):
            print("  " + line.strip())
            continue
        if hdr is None:
            hdr = line.strip().split(",")
            continue
        p = line.strip().split(",")
        if len(p) == len(hdr):
            rows.append(p)
    a = np.array(rows, dtype=object)
    d = {}
    for j, name in enumerate(hdr):
        if name in ("time",):
            d[name] = a[:, j].astype(str)
        else:
            d[name] = a[:, j].astype(float)
    return d


def tstat(x):
    n = len(x)
    if n < 2:
        return 0.0, 0.0
    m = float(np.mean(x))
    sd = float(np.std(x, ddof=1))
    return m, (m / (sd / np.sqrt(n)) if sd > 0 else 0.0)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/impulse_probe.csv"
    d = load(path)
    n = len(d["idx"])
    print("rows=%d  %s -> %s" % (n, d["time"][0], d["time"][-1]))
    print("cost model: round-trip spread %.2f $/oz on XAUUSDm (tick 0.001)" % SPREAD)
    yr = np.array([int(s[:4]) for s in d["time"]])
    dirn = d["dir"]

    def report(name, mask, horizons=HOR):
        m = np.asarray(mask, dtype=bool)
        k = int(m.sum())
        if k < 50:
            print("\n=== %s  n=%d (too few)" % (name, k))
            return
        print("\n=== %s   n=%d" % (name, k))
        print("   h  follow_R  t      follow_$/oz  t      hit%    fav_$   adv_$   edge/cost  fade_$/oz")
        for h in horizons:
            ret = d["ret%d" % h][m]
            mfe = d["mfe%d" % h][m]
            mae = d["mae%d" % h][m]
            atr = d["atr14"][m]
            dd = dirn[m]
            follow = dd * ret
            fade = -follow
            mr, tr = tstat(follow / atr)
            mp, tp = tstat(follow)
            # favourable excursion in the impulse's own direction:
            # an up impulse is favourable when price rises (mfe), a down
            # impulse when price falls (-mae).
            fav = np.where(dd > 0, mfe, -mae)
            adv = np.where(dd > 0, mae, -mfe)
            mfd, _ = tstat(fav)
            mad, _ = tstat(adv)
            hit = 100.0 * float(np.mean(follow > 0))
            print("  %-3d %+8.4f (%+5.2f) %+9.4f (%+5.2f) %6.1f%% %+7.3f %+7.3f  %+7.3f  %+8.4f" %
                  (h, mr, tr, mp, tp, hit, mfd, mad, mp / SPREAD,
                   float(np.mean(fade))))

    report("ALL BARS (baseline)", np.ones(n, bool), [1, 2, 4, 8, 16])
    for rat in (1.0, 1.2, 1.5, 2.0, 2.5, 3.0):
        report("range >= %.1f x ATR14" % rat, d["range_atr"] >= rat, [1, 2, 4, 8, 16, 32])
    for rat in (1.5, 2.0, 2.5):
        for br in (0.4, 0.5, 0.6, 0.7):
            report("range>=%.1f & body>=%.2f" % (rat, br),
                   (d["range_atr"] >= rat) & (d["body_ratio"] >= br), [2, 4, 8, 16])
    # thrust that closes at the extreme of the bar
    for rat in (1.2, 1.5):
        report("range>=%.1f & close_pos>=0.85 & body>=0.5" % rat,
               (d["range_atr"] >= rat) & (d["close_pos"] >= 0.85) & (d["body_ratio"] >= 0.5),
               [2, 4, 8, 16])
        report("range>=%.1f & close_pos<=0.15 & body>=0.5" % rat,
               (d["range_atr"] >= rat) & (d["close_pos"] <= 0.15) & (d["body_ratio"] >= 0.5),
               [2, 4, 8, 16])
    # per-year stability of the two best families
    for y in (2023, 2024, 2025, 2026):
        report("year %d ALL BARS" % y, yr == y, [2, 4, 8])
    for y in (2023, 2024, 2025, 2026):
        report("year %d range>=1.5 & body>=0.5" % y,
               (yr == y) & (d["range_atr"] >= 1.5) & (d["body_ratio"] >= 0.5), [2, 4, 8, 16])
    # volatility regime
    for lo, hi in ((0, 0.8), (0.8, 1.2), (1.2, 2.0), (2.0, 99)):
        report("range>=1.5 & body>=0.5 & atr100/atr ratio in [%.1f,%.1f)" % (lo, hi),
               (d["range_atr"] >= 1.5) & (d["body_ratio"] >= 0.5) &
               (d["rng_atr100"] >= lo) & (d["rng_atr100"] < hi), [2, 4, 8])
    # ATR level in price terms: is the edge only there when ATR is big dollars?
    for lo in (1.0, 1.5, 2.0, 2.5, 3.0):
        report("range>=1.5 & body>=0.5 & ATR14 >= %.1f $/oz" % lo,
               (d["range_atr"] >= 1.5) & (d["body_ratio"] >= 0.5) & (d["atr14"] >= lo), [2, 4, 8])


if __name__ == "__main__":
    main()
