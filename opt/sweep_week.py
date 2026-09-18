#!/usr/bin/env python3
"""Fast 1-week iteration."""
import csv, time
import run_bt as R

WK = ("2026.07.01", "2026.07.08")

CONFIGS = [
    ("wk_base", {}),
    ("wk_tp15", {"InpTP_R": 1.5}),
    ("wk_tp20", {"InpTP_R": 2.0}),
    ("wk_sl20", {"InpSL_ATR": 2.0}),
    ("wk_eff075", {"InpFadeMinEfficiency": 0.75}),
    ("wk_gateoff", {"InpUseFadeRegimeGate": "false"}),
    ("wk_be15", {"InpBreakEvenR": 1.5}),
    ("wk_notrail", {"InpUseTrailing": "false"}),
]

rows = []
t0 = time.time()
for label, params in CONFIGS:
    ini = R.build_ini(WK[0], WK[1], params)
    try:
        R.run(ini)
        m = R.parse()
    except Exception as e:
        print("ERR", label, repr(e), flush=True)
        continue
    row = {"label": label, **{k: m.get(k) for k in
           ("net", "pf", "trades", "payoff", "dd_pct", "win_pct")}, "params": params}
    rows.append(row)
    print("done", row, "elapsed=%.0fs" % (time.time() - t0), flush=True)
    with open("sweep_week.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["label", "net", "pf", "trades",
                                          "payoff", "dd_pct", "win_pct", "params"])
        w.writeheader()
        w.writerows(rows)
print("FINISHED", len(rows))
