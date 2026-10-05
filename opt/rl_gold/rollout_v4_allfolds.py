"""Rollout the v4 best_model over EVERY walk-forward fold's test window.

This is the fair OOS comparison against v3's 10-fold summary. It trains nothing;
it just replays each fold's true out-of-sample test window with the saved model.
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np, pandas as pd

RL = "/root/rl_gold/Reinforcement_Trading_Part_2"
sys.path.insert(0, "/root/rl_gold")
sys.path.insert(0, RL)

from config import CFG
CFG.csv_path = Path("/root/rl_gold/synth_v3.csv")
CFG.time_col = "time_utc"; CFG.source_tz = "UTC"; CFG.timestamp_is_bar_open = True
CFG.decision_timeframe = "M5"; CFG.execution_timeframe = "1min"
CFG.spread_price = 0.30; CFG.slippage_price = 0.02; CFG.commission_per_trade = 0.0
CFG.initial_equity = 10_000.0; CFG.risk_fraction = 0.005
CFG.sliding_train_years = 1.0; CFG.sliding_val_months = 2
CFG.sliding_test_months = 2; CFG.sliding_step_months = 3
CFG.split_embargo_bars = 100; CFG.warmup_bars = 500

from data_loader import load_mt_ohlcv_csv, resample_ohlcv, make_sliding_folds
from features import prepare_feature_frame
from evaluate import full_report
import train_v4 as T
from sb3_contrib import RecurrentPPO

MODELS = "/root/rl_gold/models_v4/finale"


def main():
    m1 = load_mt_ohlcv_csv(CFG.csv_path, time_col=CFG.time_col, source_tz=CFG.source_tz,
                           timestamp_is_bar_open=True, bar_duration="1min")
    dec = resample_ohlcv(m1, CFG.pandas_tf)
    feat, fc = prepare_feature_frame(dec, warmup_bars=CFG.warmup_bars)
    folds = make_sliding_folds(feat, train_years=CFG.sliding_train_years,
                               val_months=CFG.sliding_val_months,
                               test_months=CFG.sliding_test_months,
                               step_months=CFG.sliding_step_months,
                               embargo_bars=CFG.split_embargo_bars)
    print(f"M5 bars: {len(feat)}  folds: {len(folds)}", flush=True)

    mp = Path(MODELS)/"best_model"/"best_model.zip"
    vp = Path(MODELS)/"best_model"/"best_model_vecnorm.pkl"
    if not mp.exists():
        mp, vp = Path(MODELS)/"final_model.zip", Path(MODELS)/"final_vecnorm.pkl"
    model = RecurrentPPO.load(str(mp), device="cpu")

    rows = []
    for k, (_tr, _va, te) in enumerate(folds, 1):
        _eq, _tr2, rep = T.rollout(model, vp, m1, fc, te)
        row = dict(fold=k, test_start=str(te.index.min().date()), test_end=str(te.index.max().date()),
                   ret=rep.get("total_return_pct"), pf=rep.get("profit_factor"),
                   winrate=rep.get("win_rate_pct"), avg_r=rep.get("avg_r"),
                   sharpe=rep.get("sharpe_like"), dd=rep.get("max_drawdown_pct"),
                   trades=rep.get("n_trades"))
        rows.append(row)
        print(f"fold {k}: ret={row['ret']:+.2f}% PF={row['pf']:.2f} win={row['winrate']:.1f}% "
              f"DD={row['dd']:+.2f}% trades={int(row['trades'])}", flush=True)

    df = pd.DataFrame(rows)
    df.to_csv("/root/rl_gold/models_v4/rollout_all_folds.csv", index=False)
    print("\n=== v4 all-fold OOS ===")
    print(df.to_string(index=False))
    print(f"positive: {(df['ret']>0).sum()}/{len(df)}  mean ret={df['ret'].mean():+.2f}%  "
          f"mean PF={df['pf'].mean():.2f}  mean win={df['winrate'].mean():.1f}%")


if __name__ == "__main__":
    main()
