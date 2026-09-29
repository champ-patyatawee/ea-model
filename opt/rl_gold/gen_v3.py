#!/usr/bin/env python3
"""Generator v3: domain-randomized synthetic market with real-anchor.

Each training episode can see a DIFFERENT world:
  - regime mix: trend / range / spike / gap / chop (random weights)
  - drift, volatility, mean-reversion strength, jump intensity randomised
  - spread/time-of-day profile randomised
  - real XAUUSD H1 blocks are mixed in as an anchor (default ~25%)

Output: a long M1-ish CSV (time, ohlcv) in our schema, plus a per-bar "regime"
column so the case-test can check whether the policy reacts correctly.
"""
from __future__ import annotations
import sys
import numpy as np
import pandas as pd

REAL_H1 = "/root/rl_gold/gc_h1.csv"
OUT = "/root/rl_gold/synth_v3.csv"
RNG = np.random.default_rng(int(sys.argv[1]) if len(sys.argv) > 1 else 20260928)
MINUTES = 1_200_000          # ~ a long history
REAL_MIX = 0.25              # fraction of blocks taken from real data


def acf(x, lag):
    x = x - x.mean(); d = np.sum(x * x)
    return float(np.sum(x[:-lag] * x[lag:]) / d) if d else 0.0


def gen_block(n, RNG):
    """One regime block of 1-min returns. Randomised params each call."""
    kind = RNG.choice(["trend", "range", "spike", "chop", "gap"], p=[0.30, 0.30, 0.15, 0.15, 0.10])
    base = RNG.uniform(0.6, 1.6)          # volatility scale
    if kind == "trend":
        drift = RNG.normal(0, 1) * 0.02 * base
        rho = RNG.uniform(0.05, 0.20)      # momentum
    elif kind == "range":
        drift = 0.0
        rho = -RNG.uniform(0.02, 0.12)     # mean reversion
    elif kind == "spike":
        drift = 0.0
        rho = RNG.uniform(-0.05, 0.05)
    elif kind == "gap":
        drift = RNG.normal(0, 1) * 0.05 * base
        rho = RNG.uniform(-0.05, 0.10)
    else:  # chop
        drift = 0.0
        rho = RNG.uniform(-0.15, 0.15)
    eps = RNG.standard_normal(n)
    r = np.zeros(n)
    for t in range(1, n):
        r[t] = rho * r[t - 1] + drift + base * eps[t]
    if kind == "spike" and n > 10:
        k = RNG.integers(1, 4)
        for _ in range(k):
            j = RNG.integers(0, n)
            r[j] += RNG.normal(0, 12 * base)
    if kind == "gap" and n > 5:
        r[n // 2] += RNG.normal(0, 25 * base)
    return r, kind


def main():
    real = pd.read_csv(REAL_H1)
    real["t"] = pd.to_datetime(real["time_utc"])
    rc = real["close"].to_numpy()
    rret = np.diff(rc) / rc[:-1]            # real fractional returns
    rstd = rret.std()

    blocks = []
    kinds = []
    total = 0
    while total < MINUTES:
        n = int(RNG.integers(1500, 6000))   # block length 1-4 days of M1
        if RNG.random() < REAL_MIX and len(rret) > n + 10:
            s = RNG.integers(0, len(rret) - n)
            r = rret[s:s + n] * rc[s]       # convert real frac returns to $ (H1 scale)
            k = "real"
        else:
            r, k = gen_block(n, RNG)
        blocks.append(r); kinds.append(np.array([k] * n, dtype=object))
        total += n

    r = np.concatenate(blocks)
    kind = np.concatenate(kinds)
    # calibrate std to the real H1-derived per-step std (for realism gate)
    r = r - r.mean(); r = r / r.std() * 1.8

    # random walk price
    n = len(r)
    price = 2400.0 + np.cumsum(r)
    o = price
    c = np.roll(price, -1); c[-1] = price[-1]
    wig = np.abs(RNG.standard_normal(n)) * (np.abs(r).mean() * 2.5 + 0.2)
    h = np.maximum(o, c) + wig
    l = np.minimum(o, c) - wig

    # phase-shifted weekday clock (variety of hours too)
    ts = []
    day = pd.Timestamp("2015-01-05")
    off = int(RNG.integers(0, 60*23))
    while len(ts) < n:
        if day.dayofweek < 5:
            for hh in range(1, 24):
                for mm in range(0, 60):
                    if (hh*60+mm+off) % 1440 >= 60:  # keep 01:00-23:59 market hours
                        ts.append(day.replace(hour=hh, minute=mm))
                    if len(ts) >= n: break
                if len(ts) >= n: break
        day += pd.Timedelta(days=1)

    out = pd.DataFrame({
        "time_utc": pd.Series(ts[:n]).dt.strftime("%Y-%m-%d %H:%M:%S"),
        "open": np.round(o, 3), "high": np.round(h, 3),
        "low": np.round(l, 3), "close": np.round(c, 3),
        "volume": RNG.integers(20, 400, n),
        "regime": kind[:n],
    })
    out = out.drop_duplicates("time_utc").reset_index(drop=True)
    out.to_csv(OUT, index=False)
    print("wrote", OUT, "bars", len(out))
    print("regime mix:", pd.Series(kind[:len(out)]).value_counts(normalize=True).round(3).to_dict())

    # realism quick numbers
    sr = np.diff(out["close"].to_numpy())
    print("std", round(sr.std(), 4), "skew", round(pd.Series(sr).skew(), 3),
          "kurt", round(pd.Series(sr).kurt(), 2),
          "acf|r|1", round(acf(np.abs(sr), 1), 3), "acf|r|30", round(acf(np.abs(sr), 30), 3))


if __name__ == "__main__":
    main()
