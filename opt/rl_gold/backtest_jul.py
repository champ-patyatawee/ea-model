"""Backtest v3 LSTM models (all folds) on real XAUUSDm July-2025 M1 data.

Pulls the July M1 CSV, builds H1 decision + M1 execution frames, then replays
each fold's best_model over the whole month and reports trade stats.
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np, pandas as pd

RL = "/work/rl_gold/export_v3/RL_base"
sys.path.insert(0, "/work/rl_gold/export_v3")
sys.path.insert(0, RL)

from config import CFG
CFG.time_col = "time_utc"; CFG.source_tz = "UTC"; CFG.timestamp_is_bar_open = True
CFG.execution_timeframe = "1min"; CFG.decision_timeframe = "H1"
CFG.spread_price = 0.30; CFG.slippage_price = 0.02; CFG.commission_per_trade = 0.0
CFG.initial_equity = 1000.0; CFG.risk_fraction = 0.005

from data_loader import load_mt_ohlcv_csv, resample_ohlcv
from features import prepare_feature_frame
import train_lstm as L
from sb3_contrib import RecurrentPPO

CSV = "/work/rl_gold/xauusdm_m1_202507.csv"
MODELS = "/work/rl_gold/export_v3/models_v3"


def main():
    m1 = load_mt_ohlcv_csv(Path(CSV), time_col="time_utc", source_tz="UTC",
                           timestamp_is_bar_open=True, bar_duration="1min")
    dec = resample_ohlcv(m1, CFG.pandas_tf)
    feat, fc = prepare_feature_frame(dec, warmup_bars=CFG.warmup_bars)
    print(f"H1 bars: {len(feat)} {feat.index.min()} -> {feat.index.max()}", flush=True)

    folds = sorted([p for p in Path(MODELS).glob("fold_*") if p.is_dir()],
                   key=lambda p: int(p.name.split("_")[1]))
    rows = []
    for d in folds:
        k = int(d.name.split("_")[1])
        mp = d/"best_model"/"best_model.zip"; vp = d/"best_model"/"best_model_vecnorm.pkl"
        if not mp.exists():
            mp = d/"final_model.zip"; vp = d/"final_vecnorm.pkl"
        if not mp.exists():
            print(f"fold {k}: no model"); continue
        model = RecurrentPPO.load(str(mp), device="cpu")
        eq, tr, rep = L.rollout(model, vp, m1, fc, feat)
        pnl = float(eq["equity"].iloc[-1] - CFG.initial_equity) if not eq.empty else float("nan")
        row = dict(fold=k, profit_usd=pnl, ret_pct=rep.get("total_return_pct"),
                   winrate_pct=rep.get("win_rate_pct"), pf=rep.get("profit_factor"),
                   avg_r=rep.get("avg_r"), sharpe=rep.get("sharpe_like"),
                   dd_pct=rep.get("max_drawdown_pct"), trades=rep.get("n_trades"))
        rows.append(row)
        print(f"fold {k}: profit=${pnl:+.2f} ({row['ret_pct']:+.2f}%)  winrate={row['winrate_pct']:.1f}%  "
              f"PF={row['pf']:.2f}  avgR={row['avg_r']:+.2f}  Sharpe={row['sharpe']:+.2f}  "
              f"DD={row['dd_pct']:+.2f}%  trades={row['trades']}", flush=True)

    df = pd.DataFrame(rows)
    df.to_csv("/work/rl_gold/backtest_jul_summary.csv", index=False)
    print("\n=== JULY 2025 XAUUSDm BACKTEST ===")
    print(df.to_string(index=False))
    print(f"positive: {(df['ret_pct']>0).sum()}/{len(df)}")
    print(f"mean profit: ${df['profit_usd'].mean():+.2f}  mean ret: {df['ret_pct'].mean():+.2f}%")
    print(f"mean winrate: {df['winrate_pct'].mean():.1f}%  mean PF: {df['pf'].mean():.2f}  mean avgR: {df['avg_r'].mean():+.2f}")
    print(f"total profit (10 folds): ${df['profit_usd'].sum():+.2f}")


if __name__ == "__main__":
    main()
