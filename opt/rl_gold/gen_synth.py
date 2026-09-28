"""Generate synthetic XAUUSD-like M1 with a PLANTED edge (regime-switching AR(1)).
Trending blocks have positive autocorrelation (momentum edge); ranging blocks
negative (mean-reversion edge). If RL can't learn to profit HERE, the problem is
env/reward/architecture, not the market."""
from __future__ import annotations
import numpy as np
import pandas as pd

rng = np.random.default_rng(7)

# 12 months of M1, gold-like hours (weekdays, skip 00:00 UTC hour)
idx = pd.date_range("2023-01-01", periods=400 * 24 * 60, freq="1min", tz="UTC")
idx = idx[(idx.dayofweek < 5) & (idx.hour >= 1)]
n = len(idx)

# regime blocks: alternate TREND (+) and RANGE (-) every ~7 days
block = 7 * 24 * 60
rho = np.empty(n)
for i in range(0, n, block):
    rho[i:i + block] = 0.12 if (i // block) % 2 == 0 else -0.08

eps = rng.standard_normal(n)
step = np.zeros(n)
for t in range(1, n):
    step[t] = rho[t] * step[t - 1] + 0.35 * eps[t]   # $ per minute

price = 2000.0 + np.cumsum(step)
o = price
c = np.roll(price, -1)
c[-1] = price[-1]
wig = np.abs(rng.standard_normal(n)) * 0.4
h = np.maximum(o, c) + wig
l = np.minimum(o, c) - wig
v = rng.integers(20, 200, n)

df = pd.DataFrame({
    "time_utc": idx.strftime("%Y-%m-%d %H:%M:%S"),
    "open": np.round(o, 3), "high": np.round(h, 3),
    "low": np.round(l, 3), "close": np.round(c, 3), "volume": v,
})
out = "/work/rl_gold/synth_m1.csv"
df.to_csv(out, index=False)
print("wrote", out, len(df), "bars", df['time_utc'].iloc[0], "->", df['time_utc'].iloc[-1])
