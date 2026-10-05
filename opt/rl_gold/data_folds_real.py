"""v7 data: real M1 -> features -> walk-forward folds (+ optional synthetic).

Real M1 spans 2019-05 .. 2026-09 (~2.6M bars). We build the v7 feature frame
once, then cut calendar walk-forward folds. Synthetic (gen_v3) is optional and,
when used, is appended to each TRAIN window only (never val/test).
"""
from __future__ import annotations
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

import sys
sys.path.insert(0, "/work/vendor/Reinforcement_Trading_Part_2")
sys.path.insert(0, "/root/rl_gold/Reinforcement_Trading_Part_2")
sys.path.insert(0, "/Users/champp/Desktop/ea/opt/vendor/Reinforcement_Trading_Part_2")
from data_loader import load_mt_ohlcv_csv, make_sliding_folds  # noqa: E402
from features_fibo import build_fibo  # noqa: E402


def load_real(csv: str, extra: Optional[str] = None) -> pd.DataFrame:
    m1 = load_mt_ohlcv_csv(csv, time_col="time_utc", source_tz="UTC",
                           timestamp_is_bar_open=True, bar_duration="1min")
    if extra:
        m2 = load_mt_ohlcv_csv(extra, time_col="time_utc", source_tz="UTC",
                               timestamp_is_bar_open=True, bar_duration="1min")
        m1 = pd.concat([m1, m2])
    m1 = m1[~m1.index.duplicated(keep="last")].sort_index()
    return m1


def load_synth(csv: str) -> pd.DataFrame:
    return load_mt_ohlcv_csv(csv, time_col="time_utc", source_tz="UTC",
                             timestamp_is_bar_open=True, bar_duration="1min")


def slice_m1(m1: pd.DataFrame, dec: pd.DataFrame) -> pd.DataFrame:
    if dec.empty:
        return m1.iloc[0:0].copy()
    return m1.loc[(m1.index > dec.index.min()) & (m1.index <= dec.index.max())].copy()


def make_folds(feat: pd.DataFrame, train_years=1.5, val_months=3, test_months=3,
               step_months=3, embargo_bars=100):
    return make_sliding_folds(feat, train_years=train_years, val_months=val_months,
                              test_months=test_months, step_months=step_months,
                              embargo_bars=embargo_bars)


def prepare(real_csv: str, extra_csv: Optional[str] = None, warmup_bars: int = 250):
    """Return (m1_full, feat_full, feature_cols)."""
    m1 = load_real(real_csv, extra_csv)
    feat, cols = build_fibo(m1, warmup_bars=warmup_bars)
    return m1, feat, cols


def with_synth(m1_real: pd.DataFrame, dec_real: pd.DataFrame, synth_m1: pd.DataFrame,
               dec_synth: pd.DataFrame, frac: float = 0.30):
    """Append a slice of synthetic AFTER the real window (times shifted).

    Only for the TRAIN env. Keeps one monotonic clock so searchsorted works.
    """
    if frac <= 0 or len(dec_synth) == 0:
        return m1_real, dec_real
    k = max(int(len(dec_synth) * frac), 1)
    ds = dec_synth.iloc[:k].copy()
    ms = synth_m1.loc[(synth_m1.index > ds.index.min()) & (synth_m1.index <= ds.index.max())].copy()
    off = (dec_real.index.max() - ds.index.min()) + pd.Timedelta(minutes=10)
    ds.index = ds.index + off
    ms.index = ms.index + off
    dec = pd.concat([dec_real, ds]).sort_index()
    m1 = pd.concat([m1_real, ms]).sort_index()
    return m1, dec


if __name__ == "__main__":
    import time
    t0 = time.time()
    m1, feat, cols = prepare("/root/rl_gold/xauusdm_m1_all.csv",
                             extra_csv="/root/rl_gold/xauusdm_m1_2026may_oct.csv")
    print(f"real M1 bars={len(m1)}  feat bars={len(feat)}  "
          f"{feat.index.min()} -> {feat.index.max()}  ({time.time()-t0:.1f}s)")
    folds = make_folds(feat)
    print(f"folds={len(folds)}")
    for k, (tr, va, te) in enumerate(folds, 1):
        print(f"  fold {k}: train {tr.index.min().date()}..{tr.index.max().date()} n={len(tr)} | "
              f"val {va.index.min().date()}..{va.index.max().date()} | "
              f"test {te.index.min().date()}..{te.index.max().date()}")
