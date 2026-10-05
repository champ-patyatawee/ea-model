"""Train v6 — H1 decision, v3-style action, EMPIRICAL bootstrap data (real M1).

Data:  generator v4 (block bootstrap of 7y real XAUUSDm M1) -> resample H1.
Model: RecurrentPPO (LSTM), MultiDiscrete([3,3,4]) — direction + SL bucket + TP bucket
       (the v3 action, proven). Reward = v3 reward (giveback 0.02, no close_bonus).
Plan:  walk-forward folds + a monthly rolling forward test on real data.

Run on the pod:  python -u /root/rl_gold/train_v6.py
"""
from __future__ import annotations
import sys, os
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, "/root/rl_gold")
sys.path.insert(0, "/root/rl_gold/Reinforcement_Trading_Part_2")

from config import CFG
CFG.csv_path = Path(os.environ.get("SYNTH", "/root/rl_gold/synth_v4.csv"))
CFG.time_col = "time_utc"; CFG.source_tz = "UTC"; CFG.timestamp_is_bar_open = True
CFG.decision_timeframe = "H1"; CFG.execution_timeframe = "1min"
CFG.spread_price = 0.30; CFG.slippage_price = 0.02; CFG.commission_per_trade = 0.0
CFG.initial_equity = 10_000.0; CFG.risk_fraction = 0.005
CFG.sliding_train_years = 1.0; CFG.sliding_val_months = 2
CFG.sliding_test_months = 2; CFG.sliding_step_months = 3
CFG.split_embargo_bars = 100

from data_loader import load_mt_ohlcv_csv, resample_ohlcv, make_sliding_folds
from features import prepare_feature_frame
import train_lstm as L
from sb3_contrib import RecurrentPPO


def main():
    total_steps = int(os.environ.get("TOTAL_STEPS", "300000"))
    n_envs = int(os.environ.get("N_ENVS", "40"))
    OUT_ROOT = os.environ.get("OUT_ROOT", "/root/rl_gold/models_v6")
    m1 = load_mt_ohlcv_csv(CFG.csv_path, time_col=CFG.time_col, source_tz=CFG.source_tz,
                           timestamp_is_bar_open=True, bar_duration="1min")
    dec = resample_ohlcv(m1, CFG.pandas_tf)
    feat, fc = prepare_feature_frame(dec, warmup_bars=CFG.warmup_bars)
    print(f"H1 bars: {len(feat)} {feat.index.min()} -> {feat.index.max()}", flush=True)

    folds = make_sliding_folds(feat, train_years=CFG.sliding_train_years,
                               val_months=CFG.sliding_val_months,
                               test_months=CFG.sliding_test_months,
                               step_months=CFG.sliding_step_months,
                               embargo_bars=CFG.split_embargo_bars)
    print(f"folds: {len(folds)}", flush=True)

    rows = []
    for k, (tr, va, te) in enumerate(folds, 1):
        d = f"{OUT_ROOT}/fold_{k}"
        model = L.train_fold(tr, va, m1, fc, total_steps=total_steps, n_envs=n_envs,
                             out_dir=d, device="cuda")
        vp = Path(d)/"best_model"/"best_model_vecnorm.pkl"; mp = Path(d)/"best_model"/"best_model.zip"
        if not mp.exists():
            mp, vp = Path(d)/"final_model.zip", Path(d)/"final_vecnorm.pkl"
        m = RecurrentPPO.load(str(mp), device="cpu")
        _eq, _tr, rep = L.rollout(m, vp, m1, fc, te)
        row = dict(fold=k, test_start=str(te.index.min().date()), test_end=str(te.index.max().date()),
                   ret=rep.get("total_return_pct"), pf=rep.get("profit_factor"),
                   sharpe=rep.get("sharpe_like"), dd=rep.get("max_drawdown_pct"),
                   trades=rep.get("n_trades"))
        rows.append(row)
        print(f"fold {k} TEST ret={row['ret']:+.2f}% PF={row['pf']:.2f} "
              f"Sharpe={row['sharpe']:+.2f} DD={row['dd']:+.2f}%", flush=True)

    df = pd.DataFrame(rows); df.to_csv(f"{OUT_ROOT}/summary.csv", index=False)
    print(df.to_string(index=False))
    print(f"folds positive: {(df['ret']>0).sum()}/{len(df)}  mean={df['ret'].mean():+.2f}%")


if __name__ == "__main__":
    main()
