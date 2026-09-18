#!/usr/bin/env python3
"""Stage A sweep: TP_R x SL_ATR. Train wall-clock cheap; writes sweep_a.csv."""
import itertools, csv, sys, time
import run_bt as R

TRAIN = ("2026.01.01", "2026.07.01")

TPS = [1.25, 1.5, 1.75, 2.0]
SLS = [1.25, 1.5, 2.0]

rows = []
t0 = time.time()
for tp, sl in itertools.product(TPS, SLS):
    params = {"InpTP_R": tp, "InpSL_ATR": sl}
    ini = R.build_ini(TRAIN[0], TRAIN[1], params)
    try:
        R.run(ini)
        m = R.parse()
    except Exception as e:
        print("ERR", tp, sl, repr(e), flush=True)
        continue
    row = {"tp": tp, "sl": sl, **{k: m.get(k) for k in
           ("net", "pf", "trades", "payoff", "dd_pct", "dd_eq")}}
    rows.append(row)
    print("done", row, "elapsed=%.0fs" % (time.time() - t0), flush=True)

with open("sweep_a.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["tp", "sl", "net", "pf", "trades",
                                      "payoff", "dd_pct", "dd_eq"])
    w.writeheader()
    w.writerows(rows)
print("FINISHED", len(rows), "runs in %.0fs" % (time.time() - t0))
