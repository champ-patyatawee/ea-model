#!/usr/bin/env python3
"""Stage B sweep: entry/regime toggles. Appends to sweep_b.csv."""
import csv, time
import run_bt as R

TRAIN = ("2026.01.01", "2026.07.01")
JUL = ("2026.07.01", "2026.08.01")

CONFIGS = [
    ("train_fadeoff", TRAIN, {"InpFadeMode": "false"}),
    ("train_gateoff", TRAIN, {"InpUseFadeRegimeGate": "false"}),
    ("train_eff075", TRAIN, {"InpFadeMinEfficiency": 0.75}),
    ("train_react35", TRAIN, {"InpMinReactionScore": 3.5}),
    ("train_deepoff", TRAIN, {"InpUseDeepProfile": "false"}),
    ("train_impulse2_6", TRAIN, {"InpMinImpulseATR": 2.0, "InpMaxImpulseATR": 6.0}),
    ("jul_fadeoff", JUL, {"InpFadeMode": "false"}),
    ("jul_gateoff", JUL, {"InpUseFadeRegimeGate": "false"}),
]

rows = []
t0 = time.time()
for label, period, params in CONFIGS:
    ini = R.build_ini(period[0], period[1], params)
    try:
        R.run(ini)
        m = R.parse()
    except Exception as e:
        print("ERR", label, repr(e), flush=True)
        continue
    row = {"label": label, **{k: m.get(k) for k in
           ("net", "pf", "trades", "payoff", "dd_pct")}, "params": params}
    rows.append(row)
    print("done", row, "elapsed=%.0fs" % (time.time() - t0), flush=True)
    with open("sweep_b.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["label", "net", "pf", "trades",
                                          "payoff", "dd_pct", "params"])
        w.writeheader()
        w.writerows(rows)
print("FINISHED", len(rows))
