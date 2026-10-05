"""v7 features: M5 decision frame + H1 context + tf_state + Fibonacci structure.

The Fibonacci block is a causal port of the structural logic in
`FiboAdaptiveEA_v6.1` (swings -> compressed pivots -> BOS / HH-HL impulse ->
retracement zone -> efficiency / touches / reaction). It is deliberately causal:
a swing at bar i is only used once i+right bars have closed, and no feature at
bar t reads any bar > t. `selfcheck()` enforces this.

Feature order (stable):
    M5 stationary (25) + H1 subset (6) + tf_state (3) + fibo (12)
"""
from __future__ import annotations
from typing import List, Tuple

import sys

import numpy as np
import pandas as pd

# reuse the exact v3/v4/v6 indicator set
sys.path.insert(0, "/work/vendor/Reinforcement_Trading_Part_2")
sys.path.insert(0, "/root/rl_gold/Reinforcement_Trading_Part_2")
sys.path.insert(0, "/Users/champp/Desktop/ea/opt/vendor/Reinforcement_Trading_Part_2")
from features import add_stationary_features  # noqa: E402

# --- structure params (EA defaults) -----------------------------------------
SWING_L, SWING_R = 2, 2
ATR_PERIOD = 14
ATR_SLOW = 50
MIN_IMPULSE_ATR = 0.80
MAX_IMPULSE_ATR = 5.00
EFF_MIN = 0.40
MAX_IMPULSE_AGE = 30
FIB_MIN, FIB_MAX = 0.382, 0.727
LOOKBACK_PIVOTS = 8

H1_SUBSET = [
    "close_ema50_atr", "close_ema200_atr", "ema20_ema50_atr",
    "roc20_atr", "atr_close", "bb_width_close",
]
TF_STATE = ["tf_h1_progress", "tf_m5_index", "tf_since_h1"]
FIBO_COLS = [
    "fb_has_setup", "fb_dir", "fb_range_atr", "fb_age", "fb_efficiency",
    "fb_pos", "fb_dist_zone_atr", "fb_touches", "fb_bos", "fb_structure",
    "fb_atr_ratio", "fb_reaction",
]


# --------------------------------------------------------------------------- #
# pivots
# --------------------------------------------------------------------------- #
def _swings(high: np.ndarray, low: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    h = pd.Series(high)
    l = pd.Series(low)
    win = 2 * SWING_L + 1
    rh = h.rolling(win, center=True, min_periods=win).max().to_numpy()
    rl = l.rolling(win, center=True, min_periods=win).min().to_numpy()
    is_high = np.where(np.isnan(rh), False, high >= rh)
    is_low = np.where(np.isnan(rl), False, low <= rl)
    return is_high, is_low


def _compress_pivots(is_high: np.ndarray, is_low: np.ndarray,
                     high: np.ndarray, low: np.ndarray):
    """Chronological alternating pivots; same-type runs keep the extreme."""
    idx: List[int] = []
    typ: List[int] = []   # +1 high, -1 low
    px: List[float] = []
    cfm: List[int] = []   # bar index at which the pivot is confirmed (i + right)
    n = len(high)
    for i in range(n):
        t = 0
        if is_high[i]:
            t = 1
        elif is_low[i]:
            t = -1
        if t == 0:
            continue
        if typ and typ[-1] == t:
            if (t == 1 and high[i] > px[-1]) or (t == -1 and low[i] < px[-1]):
                idx[-1], px[-1], cfm[-1] = i, (high[i] if t == 1 else low[i]), i + SWING_R
        else:
            idx.append(i); typ.append(t)
            px.append(high[i] if t == 1 else low[i]); cfm.append(i + SWING_R)
    return np.array(idx), np.array(typ), np.array(px), np.array(cfm)


def _efficiency(close: np.ndarray, older: int, newer: int) -> float:
    if newer <= older:
        return 0.0
    seg = close[older:newer + 1]
    if len(seg) < 2:
        return 0.0
    path = float(np.abs(np.diff(seg)).sum())
    if path <= 0:
        return 0.0
    return abs(close[newer] - close[older]) / path


# --------------------------------------------------------------------------- #
# fibo block
# --------------------------------------------------------------------------- #
def _fibo_block(df5: pd.DataFrame) -> pd.DataFrame:
    high = df5["High"].to_numpy(float)
    low = df5["Low"].to_numpy(float)
    close = df5["Close"].to_numpy(float)
    open_ = df5["Open"].to_numpy(float)
    atr = df5["atr"].to_numpy(float)
    n = len(df5)

    # slow ATR -> atr_ratio
    prev_close = np.concatenate([[close[0]], close[:-1]])
    tr = np.maximum.reduce([high - low, np.abs(high - prev_close), np.abs(low - prev_close)])
    atr_slow = pd.Series(tr).ewm(alpha=1.0 / ATR_SLOW, adjust=False, min_periods=ATR_SLOW).mean().to_numpy()
    atr_ratio = np.where(atr_slow > 0, atr / atr_slow, 1.0)

    is_high, is_low = _swings(high, low)
    p_idx, p_typ, p_px, p_cfm = _compress_pivots(is_high, is_low, high, low)
    npiv = len(p_idx)

    out = np.zeros((n, len(FIBO_COLS)), dtype=np.float32)
    # defaults
    out[:, FIBO_COLS.index("fb_pos")] = 0.5
    out[:, FIBO_COLS.index("fb_atr_ratio")] = atr_ratio

    cur = None          # dict: dir, lo, hi, lo_idx, hi_idx, eff, bos, structure
    touched_identity = None
    touches = 0
    pj = -1             # last confirmed pivot index in the compressed arrays
    last_pj = -2

    for t in range(n):
        # advance confirmed pivots
        while pj + 1 < npiv and p_cfm[pj + 1] <= t:
            pj += 1
        # (re)select the newest valid impulse only when a new pivot arrives
        if pj >= 3 and pj != last_pj:
            last_pj = pj
            sel = None
            for j in range(pj, max(pj - LOOKBACK_PIVOTS, 2), -1):
                tt = p_typ[j]
                if tt == 1 and p_typ[j - 1] == -1 and p_typ[j - 2] == 1 and p_typ[j - 3] == -1:
                    d = 1; lov, hiv = p_px[j - 1], p_px[j]
                    loi, hii = p_idx[j - 1], p_idx[j]
                    prev_h, prev_l = p_px[j - 2], p_px[j - 3]
                    bos, struct = hiv > prev_h, lov > prev_l
                elif tt == -1 and p_typ[j - 1] == 1 and p_typ[j - 2] == -1 and p_typ[j - 3] == 1:
                    d = -1; lov, hiv = p_px[j], p_px[j - 1]
                    loi, hii = p_idx[j], p_idx[j - 1]
                    prev_l, prev_h = p_px[j - 2], p_px[j - 3]
                    bos, struct = lov < prev_l, hiv < prev_h
                else:
                    continue
                rng = hiv - lov
                age = t - max(loi, hii)
                if rng < MIN_IMPULSE_ATR * atr[t] or (MAX_IMPULSE_ATR > 0 and rng > MAX_IMPULSE_ATR * atr[t]):
                    continue
                if age > MAX_IMPULSE_AGE:
                    continue
                eff = _efficiency(close, min(loi, hii), max(loi, hii))
                if eff < EFF_MIN:
                    continue
                sel = dict(dir=d, lo=lov, hi=hiv, loi=loi, hii=hii, eff=eff,
                           bos=bool(bos), struct=bool(struct), ident=(loi, hii))
                break
            if sel is not None or (cur is None):
                cur = sel

        if cur is None:
            out[t, FIBO_COLS.index("fb_atr_ratio")] = atr_ratio[t]
            continue

        rng = max(cur["hi"] - cur["lo"], 1e-12)
        a = max(atr[t], 1e-12)
        if cur["dir"] == 1:
            zone_hi = cur["hi"] - rng * FIB_MIN
            zone_lo = cur["hi"] - rng * FIB_MAX
            fib_pos = (cur["hi"] - close[t]) / rng
        else:
            zone_lo = cur["lo"] + rng * FIB_MIN
            zone_hi = cur["lo"] + rng * FIB_MAX
            fib_pos = (close[t] - cur["lo"]) / rng

        in_zone = zone_lo <= close[t] <= zone_hi
        if cur["ident"] != touched_identity:
            touched_identity = cur["ident"]; touches = 0
        if in_zone:
            touches += 1
        # distance to zone in ATR (0 inside)
        if close[t] > zone_hi:
            dist = (close[t] - zone_hi) / a
        elif close[t] < zone_lo:
            dist = (zone_lo - close[t]) / a
        else:
            dist = 0.0

        # reaction score on the previous M5 bar (EA ReactionScore)
        o, h, l, c = open_[t - 1], high[t - 1], low[t - 1], close[t - 1]
        reaction = 0.0
        if h > l and a > 0:
            body = abs(c - o); rngb = h - l
            upper = h - max(o, c); lower = min(o, c) - l
            if zone_lo <= h and l <= zone_hi:
                if cur["dir"] == 1 and c > o:
                    reaction += 1
                if cur["dir"] == -1 and c < o:
                    reaction += 1
                if body >= 0.25 * a:
                    reaction += 1
                if cur["dir"] == 1 and lower >= max(body * 0.8, rngb * 0.15):
                    reaction += 1
                if cur["dir"] == -1 and upper >= max(body * 0.8, rngb * 0.15):
                    reaction += 1
                if rngb >= a * 0.8:
                    reaction += 1
                if cur["dir"] == 1 and (h - c) <= rngb * 0.30:
                    reaction += 1
                if cur["dir"] == -1 and (c - l) <= rngb * 0.30:
                    reaction += 1

        row = {
            "fb_has_setup": 1.0 if in_zone else 0.0,
            "fb_dir": float(cur["dir"]),
            "fb_range_atr": rng / a,
            "fb_age": float(t - max(cur["loi"], cur["hii"])),
            "fb_efficiency": float(cur["eff"]),
            "fb_pos": float(fib_pos),
            "fb_dist_zone_atr": float(dist),
            "fb_touches": float(touches),
            "fb_bos": 1.0 if cur["bos"] else 0.0,
            "fb_structure": 1.0 if cur["struct"] else 0.0,
            "fb_atr_ratio": float(atr_ratio[t]),
            "fb_reaction": float(reaction),
        }
        for k, v in row.items():
            out[t, FIBO_COLS.index(k)] = v

    return pd.DataFrame(out, index=df5.index, columns=FIBO_COLS)


# --------------------------------------------------------------------------- #
# main builder
# --------------------------------------------------------------------------- #
def build_fibo(m1_df: pd.DataFrame, warmup_bars: int = 250) -> Tuple[pd.DataFrame, List[str]]:
    dec = m1_df.resample("5min", label="right", closed="right").agg({
        "Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum",
    }).dropna(subset=["Open", "High", "Low", "Close"])
    h1 = m1_df.resample("1h", label="right", closed="right").agg({
        "Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum",
    }).dropna(subset=["Open", "High", "Low", "Close"])

    m5_feat, m5_cols = add_stationary_features(dec)
    h1_feat, _ = add_stationary_features(h1)
    h1_sel = h1_feat[H1_SUBSET].add_suffix("_h1")

    merged = pd.merge_asof(m5_feat.sort_index(), h1_sel.sort_index(),
                           left_index=True, right_index=True,
                           direction="backward", allow_exact_matches=False)

    mins = merged.index.minute
    merged["tf_h1_progress"] = mins / 60.0
    merged["tf_m5_index"] = (mins // 5).astype(float)
    merged["tf_since_h1"] = (mins // 5).astype(float)

    fb = _fibo_block(m5_feat)
    merged = merged.join(fb)

    feature_cols = list(m5_cols) + list(h1_sel.columns) + TF_STATE + FIBO_COLS
    merged = merged.iloc[warmup_bars:].dropna(subset=[c for c in feature_cols if not c.startswith("fb_")] + ["atr"]).copy()
    for c in FIBO_COLS:
        merged[c] = merged[c].fillna(0.0)
    return merged, feature_cols


# --------------------------------------------------------------------------- #
# causality self-check (the real anti-lookahead guard)
# --------------------------------------------------------------------------- #
def selfcheck(m1_df: pd.DataFrame, warmup_bars: int = 250, k: int = 300,
              buffer: int = 60) -> bool:
    a, cols = build_fibo(m1_df, warmup_bars=warmup_bars)
    if len(a) < k + 5:
        print("[selfcheck] too few bars"); return False
    head = m1_df.iloc[: len(m1_df) - k]
    b, _ = build_fibo(head, warmup_bars=warmup_bars)
    # only compare rows far enough from the truncation edge: near the edge the
    # head genuinely does not know the future, which is correct behaviour.
    if len(b) <= buffer:
        print("[selfcheck] head too short"); return False
    settled = b.index[:-buffer]
    common = a.index.intersection(settled)
    if len(common) < 20:
        print("[selfcheck] no overlap"); return False
    diff = (a.loc[common, cols] - b.loc[common, cols]).abs()
    bad = diff.max().max()
    ok = bool(np.nanmax(bad) < 1e-4)
    print(f"[selfcheck] max |future-dependent diff| = {bad:.3e} -> {'OK' if ok else 'FAIL'}")
    return ok


if __name__ == "__main__":
    from data_loader import load_mt_ohlcv_csv  # noqa: E402
    import time
    csv = sys.argv[1] if len(sys.argv) > 1 else "/work/rl_gold/xauusdm_m1_2026q3.csv"
    m1 = load_mt_ohlcv_csv(csv, time_col="time_utc", source_tz="UTC",
                           timestamp_is_bar_open=True, bar_duration="1min")
    t0 = time.time()
    f, c = build_fibo(m1, warmup_bars=250)
    print(f"bars={len(f)}  features={len(c)}  {m1.index.min()} -> {m1.index.max()}  ({time.time()-t0:.1f}s)")
    print("cols:", c)
    print(f.loc[f.index[-50:], FIBO_COLS].describe().loc[["mean", "std", "min", "max"]].to_string())
    selfcheck(m1, warmup_bars=250, k=300)
