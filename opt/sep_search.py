#!/usr/bin/env python3
"""Search configs on September 2026 (v5.0). Always pass explicit OFF base
so the tester cache cannot leak previous runs."""
import run_bt as R

OFF = {
    "InpUseRegimeFilter": "false", "InpRegimeStrengthMin": 1.0,
    "InpUseATRAdaptiveZone": "false", "InpATRZoneShift": 0.10,
    "InpUseDualMode": "false", "InpUseHTFTrendFilter": "false",
    "InpUseDailyDirLock": "false", "InpRandomEntry": "false",
    "InpFixedLot": 0.02,
}
SEP = ("2026.09.01", "2026.09.19")

CASES = [
    ("base", {}),
    ("reg0.5", {"InpUseRegimeFilter": "true", "InpRegimeStrengthMin": 0.5}),
    ("reg1.0", {"InpUseRegimeFilter": "true", "InpRegimeStrengthMin": 1.0}),
    ("atrzone", {"InpUseATRAdaptiveZone": "true", "InpATRZoneShift": 0.10}),
    ("dual", {"InpUseDualMode": "true"}),
    ("dir_lock2", {"InpUseDailyDirLock": "true", "InpMaxDirLossesPerDay": 2}),
    ("eff0.55", {"InpFadeMinEfficiency": 0.55}),
    ("eff0.65", {"InpFadeMinEfficiency": 0.65}),
    ("react3.5", {"InpMinReactionScore": 3.5}),
    ("fib_deep", {"InpEntryFibMin": 0.50, "InpEntryFibMax": 0.786}),
]

for name, ov in CASES:
    p = dict(OFF); p.update(ov)
    R.run(R.build_ini(SEP[0], SEP[1], p, deposit=10000))
    m = R.parse()
    print(name, {k: m.get(k) for k in ("net", "pf", "trades", "dd_pct")}, flush=True)
