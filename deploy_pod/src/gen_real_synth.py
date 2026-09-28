"""Phase 1 (clean): realistic synthetic XAUUSD M1.

Builds a long close series by block-bootstrap of real 1-min returns, then
attaches REAL (high-open)/(open-low) wick ratios sampled from the real data so
OHLC + ATR stay realistic. Ends with a Realism Gate.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

REAL = "/root/rl_gold/xauusdm_m1.csv"
OUT = "/root/rl_gold/synth_real_m1.csv"
RNG = np.random.default_rng(20260928)
TARGET = 1_200_000


def acf(x, lag):
    x = x - x.mean()
    d = np.sum(x * x)
    return float(np.sum(x[:-lag] * x[lag:]) / d) if d else 0.0


def main():
    real = pd.read_csv(REAL)
    real["time_utc"] = pd.to_datetime(real["time_utc"])
    real = real.sort_values("time_utc").reset_index(drop=True)
    c = real["close"].to_numpy()
    o = real["open"].to_numpy()
    h = real["high"].to_numpy()
    l = real["low"].to_numpy()

    ret = np.diff(c)
    rstd = ret.std()
    up = (h - np.maximum(o, c))          # upper wick
    dn = (np.minimum(o, c) - l)          # lower wick
    body = np.abs(c - o)
    up = up[up > 0]; dn = dn[dn > 0]

    # ---- long return series via block bootstrap, calibrate std ----
    block = 390
    nb = int(np.ceil(TARGET * 1.1 / block))
    starts = RNG.integers(0, len(ret) - block, size=nb)
    boot = np.concatenate([ret[s:s + block] for s in starts])
    boot = boot - boot.mean()
    boot = boot / boot.std() * rstd
    boot = np.clip(boot, -40 * rstd, 40 * rstd)
    boot = boot - boot.mean(); boot = boot / boot.std() * rstd
    n = len(boot)

    price = c[0] + np.cumsum(boot)
    price = np.round(price, 3)
    o_ = np.empty(n); h_ = np.empty(n); l_ = np.empty(n)
    o_[:] = price
    cl = np.empty(n); cl[:-1] = price[1:]; cl[-1] = price[-1]
    cl = np.round(cl, 3)

    # wick + body from REAL distributions (scaled to synth's local scale)
    scale = np.abs(boot)
    sc = np.clip(scale / rstd, 0.3, 4.0)
    uw = RNG.choice(up, size=n) * sc
    dw = RNG.choice(dn, size=n) * sc
    hi = np.maximum(o_, cl) + uw
    lo = np.minimum(o_, cl) - dw
    h_ = np.round(hi, 3); l_ = np.round(lo, 3)

    # timestamps: build a clean weekday calendar of n minutes (market hours
    # 01:00-23:59 UTC), which avoids runaway/duplicate dates entirely.
    ts = []
    day = pd.Timestamp("2021-01-04")
    while len(ts) < n:
        if day.dayofweek < 5:
            for hh in range(1, 24):
                for mm in range(0, 60):
                    ts.append(day.replace(hour=hh, minute=mm))
                    if len(ts) >= n:
                        break
                if len(ts) >= n:
                    break
        day = day + pd.Timedelta(days=1)
    ts = pd.Series(ts)
    hidx = RNG.integers(0, len(real), size=len(ts))

    out = pd.DataFrame({
        "time_utc": ts.dt.strftime("%Y-%m-%d %H:%M:%S"),
        "open": o_, "high": h_, "low": l_, "close": cl,
        "volume": real["volume"].to_numpy()[hidx],
    })
    out = out.drop_duplicates(subset="time_utc").reset_index(drop=True)

    # final std calibration on emitted closes
    for _ in range(6):
        r = np.diff(out["close"].to_numpy())
        if r.std() == 0 or abs(r.std() / rstd - 1) < 0.01:
            break
        k = rstd / r.std()
        np_ = out["close"].to_numpy()[0] + np.cumsum(np.concatenate([[0.0], r * k]))
        bo = out["close"].to_numpy() - out["open"].to_numpy()
        out["close"] = np.round(np_, 3)
        out["open"] = np.round(np_ - bo, 3)
        out["high"] = np.round(np.maximum(out["high"], np.maximum(out["open"], out["close"])), 3)
        out["low"] = np.round(np.minimum(out["low"], np.minimum(out["open"], out["close"])), 3)
        out = out.drop_duplicates(subset="time_utc").reset_index(drop=True)

    out.to_csv(OUT, index=False)
    print(f"wrote {OUT} bars={len(out):,}")

    # ---------------- Realism Gate ----------------
    sr = np.diff(out["close"].to_numpy())
    print("\n== Realism Gate ==")
    print(f"{'metric':10}{'real':>12}{'synth':>12}")
    for name, a, b in [
        ("std", ret.std(), sr.std()),
        ("absmean", np.abs(ret).mean(), np.abs(sr).mean()),
        ("skew", pd.Series(ret).skew(), pd.Series(sr).skew()),
        ("kurt", pd.Series(ret).kurt(), pd.Series(sr).kurt()),
    ]:
        print(f"{name:10}{a:>12.5f}{b:>12.5f}")
    print("autocorr:")
    for lag in (1, 5, 30):
        print(f"  ACF(ret,{lag:<2}) real={acf(ret,lag):+.4f} synth={acf(sr,lag):+.4f}")
    for lag in (1, 5, 30):
        print(f"  ACF(|r|,{lag:<2}) real={acf(np.abs(ret),lag):+.4f} synth={acf(np.abs(sr),lag):+.4f}")
    for nm, df in (("real", real), ("synth", out)):
        tr = np.maximum(df["high"] - df["low"],
                        np.maximum((df["high"] - df["close"].shift(1)).abs(),
                                   (df["low"] - df["close"].shift(1)).abs())).dropna()
        print(f"  {nm} ATR14 mean={tr.rolling(14).mean().mean():.4f}")

    ok_std = abs(sr.std() - ret.std()) / ret.std() < 0.05
    ok_kurt = abs(pd.Series(sr).kurt() - pd.Series(ret).kurt()) < 30
    ok_acf = abs(acf(np.abs(ret), 30) - acf(np.abs(sr), 30)) < 0.10
    print(f"\nGATE: std_ok={ok_std} kurt_ok={ok_kurt} volclust_ok={ok_acf} "
          f"=> {'PASS' if (ok_std and ok_kurt and ok_acf) else 'REVIEW'}")


if __name__ == "__main__":
    main()
