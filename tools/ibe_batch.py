#!/usr/bin/env python3
"""Compare many ImpulseBasketEA equity paths on the brief's metrics.

Usage
  python3 tools/ibe_batch.py <glob-prefix> [deposit] [window_days]

Every metric here comes from the raw dollar equity path of a full-period run,
so the numbers are deposit-independent up to the ruin floor.
"""
import glob
import os
import sys
from collections import OrderedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ibe_report import load, day_key, month_key          # noqa: E402


def series(eq, ts):
    days = OrderedDict()
    for i, s in enumerate(ts):
        days.setdefault(day_key(s), i)
    return list(days.items())


def windows(eq, day_list, wdays):
    out = []
    for a in range(len(day_list)):
        b = a + wdays - 1
        if b >= len(day_list):
            break
        out.append((day_list[a][1], day_list[b][1]))
    return out


def metrics(eq, ts, dep=1000.0, wdays=21, from_date=None, to_date=None):
    day_list = series(eq, ts)
    if from_date:
        day_list = [(d, i) for d, i in day_list if d >= from_date]
    if to_date:
        day_list = [(d, i) for d, i in day_list if d <= to_date]
    if len(day_list) < 5:
        return None
    win = []
    for a in range(len(day_list) - wdays + 1):
        i0, i1 = day_list[a][1], day_list[a + wdays - 1][1]
        e0 = eq[i0]
        pl = eq[i1] - e0
        dd = e0 - min(eq[i0:i1 + 1])
        ruined = dd >= dep
        win.append((-dep if ruined else pl, dd, ruined))
    n = len(win)
    ev = sum(w[0] for w in win) / n
    ruin = 100.0 * sum(1 for w in win if w[2]) / n
    pls = sorted(w[0] for w in win)
    dday = []
    for a in range(len(day_list) - 1):
        i0, i1 = day_list[a][1], day_list[a + 1][1]
        dday.append(eq[i1] - eq[i0])
    dday.sort()
    return {
        "n": n, "ev": ev, "ruin": ruin,
        "med": pls[n // 2], "p05": pls[int(0.05 * n)], "worst": pls[0], "best": pls[-1],
        "dmean": sum(dday) / len(dday),
        "dwin": 100.0 * sum(1 for x in dday if x > 0) / len(dday),
        "days": len(day_list),
    }


def fmt(name, m):
    if m is None:
        return "%-22s  (no data)" % name
    return ("%-22s EV/run %+8.2f  ruin %5.1f%%  med %+7.2f  p05 %+8.2f  "
            "worst %+8.2f  daymean %+6.2f  daywin %4.1f%%  n=%d" %
            (name, m["ev"], m["ruin"], m["med"], m["p05"], m["worst"],
             m["dmean"], m["dwin"], m["n"]))


def main():
    prefix = sys.argv[1]
    dep = float(sys.argv[2]) if len(sys.argv) > 2 else 1000.0
    wdays = int(sys.argv[3]) if len(sys.argv) > 3 else 21
    paths = sorted(glob.glob(prefix))
    print("%d files, deposit %.0f, window %d trading days\n" % (len(paths), dep, wdays))
    rows = []
    for p in paths:
        bal, eq, ts = load(p)
        m = metrics(eq, ts, dep, wdays)
        name = os.path.basename(p).replace(".csv", "")
        rows.append((name, m))
    rows.sort(key=lambda r: -(r[1]["ev"] if r[1] else -1e9))
    print("--- FULL PERIOD 2023.01-2026.10 ---")
    for name, m in rows:
        print(fmt(name, m))
    print("\n--- TUNE 2023.01-2024.12 / VALIDATE 2025.01-2026.10 ---")
    print("%-22s %26s %26s" % ("", "tune (EV/run, ruin%)", "validate (EV/run, ruin%)"))
    val = []
    for name, _ in rows:
        p = [x for x in paths if os.path.basename(x).replace(".csv", "") == name][0]
        bal, eq, ts = load(p)
        mt = metrics(eq, ts, dep, wdays, to_date="2024.12.31")
        mv = metrics(eq, ts, dep, wdays, from_date="2025.01.01")
        val.append((name, mt, mv))
    val.sort(key=lambda r: -((r[1]["ev"] if r[1] else -1e9) + (r[2]["ev"] if r[2] else -1e9)))
    for name, mt, mv in val:
        if mt and mv:
            print("%-22s %+9.2f / %5.1f%% %+14s %+9.2f / %5.1f%%" %
                  (name, mt["ev"], mt["ruin"], "", mv["ev"], mv["ruin"]))


if __name__ == "__main__":
    main()
