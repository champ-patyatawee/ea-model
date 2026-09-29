"""Train LSTM on REAL XAUUSD H1 (Yahoo GC=F, ~2y). H1 is used as both the
decision and the execution frame (no M1 available)."""
from __future__ import annotations
import sys, os, functools
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, "/root/rl_gold")
sys.path.insert(0, "/root/rl_gold/Reinforcement_Trading_Part_2")

from config import CFG
CFG.csv_path = Path("/root/rl_gold/gc_h1.csv")
CFG.time_col = "time_utc"; CFG.source_tz = "UTC"; CFG.timestamp_is_bar_open = True
CFG.decision_timeframe = "H1"
CFG.execution_timeframe = "H1"
CFG.spread_price = 0.30; CFG.slippage_price = 0.02; CFG.commission_per_trade = 0.0
CFG.initial_equity = 10_000.0; CFG.risk_fraction = 0.005
CFG.warmup_bars = 100
CFG.atr_period = 14; CFG.rsi_period = 14
# short-history walk-forward: train 9m -> val 3m -> test 3m, slide 3m
CFG.sliding_train_years = 0.75
CFG.sliding_val_months = 3
CFG.sliding_test_months = 3
CFG.sliding_step_months = 3
CFG.split_embargo_bars = 50
CFG.test_frac = 0.15

from data_loader import load_mt_ohlcv_csv, resample_ohlcv, make_sliding_folds
from features import prepare_feature_frame
import train_lstm as L

def main():
    m1 = load_mt_ohlcv_csv(CFG.csv_path, time_col=CFG.time_col, source_tz=CFG.source_tz,
                           timestamp_is_bar_open=True, bar_duration="1h")
    # decision frame == the H1 bars themselves
    dec = m1.copy()
    feat, fc = prepare_feature_frame(dec, warmup_bars=CFG.warmup_bars,
                                     atr_period=CFG.atr_period, rsi_period=CFG.rsi_period)
    print("H1 bars after warmup:", len(feat), feat.index.min(), feat.index.max(), flush=True)
    folds = make_sliding_folds(feat, train_years=CFG.sliding_train_years,
                               val_months=CFG.sliding_val_months,
                               test_months=CFG.sliding_test_months,
                               step_months=CFG.sliding_step_months,
                               embargo_bars=CFG.split_embargo_bars)
    print("folds:", len(folds), flush=True)
    Path("/root/rl_gold/models_real").mkdir(parents=True, exist_ok=True)
    rows = []
    for k, (tr, va, te) in enumerate(folds, 1):
        d = f"/root/rl_gold/models_real/fold_{k}"
        model = L.train_fold(tr, va, dec, fc, total_steps=300_000, n_envs=24,
                             out_dir=d, device="cuda", episode_steps=1024,
                             eval_freq=15_000)
        mp = Path(d)/"best_model"/"best_model.zip"
        vp = Path(d)/"best_model"/"best_model_vecnorm.pkl"
        if not mp.exists():
            mp, vp = Path(d)/"final_model.zip", Path(d)/"final_vecnorm.pkl"
        m = L.RecurrentPPO.load(str(mp), device="cpu")
        _eq, _tr, rep = L.rollout(m, vp, dec, fc, te)
        rows.append(dict(fold=k, test_start=str(te.index.min().date()),
                         test_end=str(te.index.max().date()),
                         ret=rep.get("total_return_pct"), pf=rep.get("profit_factor"),
                         sharpe=rep.get("sharpe_like"), dd=rep.get("max_drawdown_pct"),
                         trades=rep.get("n_trades")))
        print(f"fold {k} TEST ret={rep.get('total_return_pct'):+.2f}% "
              f"PF={rep.get('profit_factor'):.2f} Sharpe={rep.get('sharpe_like'):+.2f}", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv("/root/rl_gold/models_real/summary.csv", index=False)
    print(df.to_string(index=False))
    print(f"folds positive: {(df['ret']>0).sum()}/{len(df)}  mean={df['ret'].mean():+.2f}%")

if __name__ == "__main__":
    main()
