"""v5 multi-timeframe features: H1 context + M5 decision, built from one M1 series.

For every M5 decision bar we attach the most recent *closed* H1 bar's features
(no look-ahead) plus a small time-frame state block. Returns the merged M5 frame
and the ordered feature column list (H1 block + M5 block + tf_state).
"""
from __future__ import annotations
from typing import List, Tuple

import numpy as np
import pandas as pd

import sys
sys.path.insert(0, "/root/rl_gold/Reinforcement_Trading_Part_2")
from features import add_stationary_features  # noqa: E402


def _feature_cols(atr_period=14, rsi_period=14):
    """Reuse the exact v3/v4 indicator set (25 names)."""
    from features import prepare_feature_frame
    # build on a tiny synthetic frame just to read the column list order
    idx = pd.date_range("2020-01-01", periods=400, freq="5min", tz="UTC")
    px = pd.Series(np.linspace(100, 110, len(idx)), index=idx)
    df = pd.DataFrame({"Open": px, "High": px * 1.001, "Low": px * 0.999,
                       "Close": px, "Volume": 1.0}, index=idx)
    _f, cols = prepare_feature_frame(df, warmup_bars=1)
    return cols


def build_multitf(
    m1_df: pd.DataFrame,
    warmup_bars: int = 500,
    h1_subset: List[str] | None = None,
) -> Tuple[pd.DataFrame, List[str]]:
    """Return (m5_frame_with_h1_and_state, feature_cols).

    m5_frame index = M5 bar close (UTC). Contains the M5 feature columns, the
    selected H1 feature columns suffixed ``_h1``, and the tf_state columns.
    """
    # H1 kept small on purpose: only slow-context columns (trend + vol regime).
    # Passing all 25 duplicated most of the M5 block and blew the observation to
    # 61 dims, which under-fit a 69k-bar train window and hurt OOS badly.
    if h1_subset is None:
        h1_subset = [
            "close_ema50_atr", "close_ema200_atr", "ema20_ema50_atr",
            "roc20_atr", "atr_close", "bb_width_close",
        ]
    dec_m5 = m1_df.resample("5min", label="right", closed="right").agg({
        "Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum",
    }).dropna(subset=["Open", "High", "Low", "Close"])

    h1 = m1_df.resample("1h", label="right", closed="right").agg({
        "Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum",
    }).dropna(subset=["Open", "High", "Low", "Close"])

    m5_feat, m5_cols = add_stationary_features(dec_m5)
    h1_feat, h1_cols = add_stationary_features(h1)

    keep = h1_subset if h1_subset else h1_cols
    h1_sel = h1_feat[keep].add_suffix("_h1")

    # Align: each M5 bar gets the most recent H1 bar that has ALREADY CLOSED.
    # Shift the H1 index forward by one hour so an M5 bar at HH:00 uses the
    # 1h bar that closed at HH:00 but whose features are computed from data up
    # to HH:00 — we then match strictly backward + no exact match, so a bar at
    # exactly HH:00 does NOT consume its own just-forming hour.
    h1_shifted = h1_sel.copy()
    h1_shifted.index = h1_shifted.index  # already close-time stamped
    merged = pd.merge_asof(
        m5_feat.sort_index(), h1_shifted.sort_index(),
        left_index=True, right_index=True, direction="backward", allow_exact_matches=False)

    # timeframe state: position within the hour
    mins = merged.index.minute + merged.index.hour * 60
    in_hour = merged.index.minute  # 0,5,...,55 (M5 close)
    merged["tf_h1_progress"] = in_hour / 60.0
    merged["tf_m5_index"] = (in_hour // 5).astype(float)        # 0..11
    # bars since H1 close (0 at the top of the hour, 11 at :55)
    merged["tf_since_h1"] = ((in_hour // 5)).astype(float)

    tf_state = ["tf_h1_progress", "tf_m5_index", "tf_since_h1"]
    feature_cols = list(m5_cols) + [c for c in h1_sel.columns] + tf_state

    merged = merged.iloc[warmup_bars:].dropna(subset=feature_cols + ["atr"]).copy()
    return merged, feature_cols


if __name__ == "__main__":
    from data_loader import load_mt_ohlcv_csv
    m1 = load_mt_ohlcv_csv("/root/rl_gold/synth_v3.csv", time_col="time_utc",
                           source_tz="UTC", timestamp_is_bar_open=True, bar_duration="1min")
    frame, cols = build_multitf(m1, warmup_bars=500)
    print("bars", len(frame), frame.index.min(), "->", frame.index.max())
    print("n_features", len(cols))
    print(cols)
