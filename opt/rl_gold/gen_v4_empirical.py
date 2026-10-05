#!/usr/bin/env python3
"""Generator v4 — empirical block-bootstrap from REAL XAUUSDm M1.

Instead of hand-coding regimes (which caps at what we know), this cuts the real
7-year M1 history into short blocks and recombines them into fresh "worlds".
Session behaviour, volatility clustering, spikes and event days all travel with
the real blocks, so we do not have to name a single case.

Usage:
    python gen_v4_empirical.py <seed> <out_csv> [block_days] [real_mix]
"""
from __future__ import annotations
import sys
import numpy as np
import pandas as pd

SRC = "/root/rl_gold/xauusdm_m1_all.csv"       # real M1 (pod)
OUT = sys.argv[2] if len(sys.argv) > 2 else "/root/rl_gold/synth_v4.csv"
SEED = int(sys.argv[1]) if len(sys.argv) > 1 else 20260930
BLOCK_DAYS = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0    # block length
MINUTES_TARGET = 2_000_000


def acf(x, lag):
    x = x - x.mean(); d = np.sum(x * x)
    return float(np.sum(x[:-lag] * x[lag:]) / d) if d else 0.0


def main():
    rng = np.random.default_rng(SEED)
    real = pd.read_csv(SRC)
    real["t"] = pd.to_datetime(real["time_utc"])
    real = real.sort_values("t").reset_index(drop=True)

    # continuous segments (split on time gaps > 1 day = weekends/holidays)
    gap = real["t"].diff().dt.total_seconds().fillna(1) > 86400
    seg_id = gap.cumsum().to_numpy()
    segs = [g.index.to_numpy() for _, g in real.groupby(seg_id)]
    print(f"real bars {len(real)}  segments {len(segs)}  span {real['t'].min()} -> {real['t'].max()}")

    block_len = int(BLOCK_DAYS * 24 * 60)          # ~1 day of minutes
    frames = []
    total = 0
    while total < MINUTES_TARGET:
        seg = segs[rng.integers(0, len(segs))]
        if len(seg) <= block_len + 1:
            continue
        s = int(rng.integers(0, len(seg) - block_len))
        chunk = real.iloc[seg[s:s + block_len]].copy()
        # shift the block onto a synthetic continuous clock so gaps close
        frames.append(chunk)
        total += len(chunk)
    out = pd.concat(frames, ignore_index=True)

    # Re-stitch: re-price each block from its own RETURNS so the series has no
    # jumps at the seams (raw concatenation produced std 36 / kurt 4868 / acf 0).
    rel = out["close"].to_numpy(dtype=float)
    seg_breaks = []
    pos = 0
    for fr in frames:
        pos += len(fr)
        seg_breaks.append(pos)
    seg_breaks = set(seg_breaks[:-1])
    returns = np.zeros(len(rel))
    for i in range(1, len(rel)):
        returns[i] = 0.0 if i in seg_breaks else (rel[i] - rel[i - 1])
    # rescale returns to the median per-minute move of the real data (in $),
    # so block-to-block volatility level stays realistic
    real_move = np.median(np.abs(np.diff(real["close"].to_numpy(dtype=float))))
    r_std = returns.std()
    if r_std > 0:
        returns = returns / r_std * (real_move * 1.5)
    price = 1800.0 + np.cumsum(returns)

    o = price.copy()
    c = np.roll(price, -1); c[-1] = price[-1]
    rng2 = np.random.default_rng(SEED + 1)
    wig = np.abs(rng2.standard_normal(len(price))) * (np.abs(returns).mean() * 2.0 + 0.05)
    hi = np.maximum(o, c) + wig
    lo = np.minimum(o, c) - wig

    n = len(price)
    start = pd.Timestamp("2015-01-05 01:00:00")
    clock = pd.date_range(start, periods=n, freq="1min", tz="UTC")
    out = pd.DataFrame({
        "time_utc": clock.strftime("%Y-%m-%d %H:%M:%S"),
        "open": np.round(o, 3), "high": np.round(hi, 3),
        "low": np.round(lo, 3), "close": np.round(c, 3),
        "volume": frames[0]["volume"].iloc[0] if "volume" in frames[0] else 1,
    })
    out["volume"] = 100
    out.to_csv(OUT, index=False)
    print("wrote", OUT, "bars", len(out))

    r = np.diff(out["close"].to_numpy())
    print("std", round(r.std(), 4), "kurt", round(pd.Series(r).kurt(), 2),
          "acf|r|1", round(acf(np.abs(r), 1), 3), "acf|r|30", round(acf(np.abs(r), 30), 3))


if __name__ == "__main__":
    main()
