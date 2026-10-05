"""Backtest the v4 model on a single month of real XAUUSDm M1 data, with DAILY results.

Runs the v4 best_model over the month's M5 decisions (built from M1) and reports
both the monthly summary and a per-day breakdown (return, trades, win rate).
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, "/work/rl_gold")
sys.path.insert(0, "/work/rl_gold/export_v3/RL_base")

from config import CFG
CFG.time_col = "time_utc"; CFG.source_tz = "UTC"; CFG.timestamp_is_bar_open = True
CFG.decision_timeframe = "M5"; CFG.execution_timeframe = "1min"
CFG.spread_price = 0.30; CFG.slippage_price = 0.02; CFG.commission_per_trade = 0.0
CFG.initial_equity = 10_000.0; CFG.risk_fraction = 0.005
CFG.warmup_bars = 500

from data_loader import load_mt_ohlcv_csv, resample_ohlcv
from features import prepare_feature_frame
from evaluate import full_report
import train_v4 as T
from sb3_contrib import RecurrentPPO

MODELS = "/work/rl_gold/models_v4_export/finale"


def main():
    csv = sys.argv[1] if len(sys.argv) > 1 else "/work/rl_gold/xauusdm_m1_202508.csv"
    m1 = load_mt_ohlcv_csv(Path(csv), time_col="time_utc", source_tz="UTC",
                           timestamp_is_bar_open=True, bar_duration="1min")
    m1 = m1.sort_index()
    dec = resample_ohlcv(m1, CFG.pandas_tf)
    feat, fc = prepare_feature_frame(dec, warmup_bars=CFG.warmup_bars)
    print(f"M1 bars: {len(m1)}  M5 decision bars: {len(feat)}  {feat.index.min()} -> {feat.index.max()}", flush=True)

    mp = Path(MODELS)/"best_model"/"best_model.zip"
    vp = Path(MODELS)/"best_model"/"best_model_vecnorm.pkl"
    if not mp.exists():
        mp, vp = Path(MODELS)/"final_model.zip", Path(MODELS)/"final_vecnorm.pkl"
    model = RecurrentPPO.load(str(mp), device="cpu")

    eq, tr, rep = T.rollout(model, vp, m1, fc, feat)
    print("\n=== MONTH SUMMARY (v4) ===")
    summ = {k: rep.get(k) for k in ["total_return_pct", "profit_factor", "win_rate_pct",
                                    "max_drawdown_pct", "n_trades", "avg_r", "sharpe_like"]}
    for k, v in summ.items():
        print(f"  {k}: {v}")

    # ---- DAILY breakdown from the equity curve ----
    if eq is None or eq.empty:
        print("no equity curve"); return
    eq = eq.copy()
    eq["equity"] = eq["equity"].astype(float)
    daily = eq.resample("1D").last().dropna()
    base = CFG.initial_equity
    rows = []
    prev = base
    for day, row in daily.iterrows():
        e = float(row["equity"])
        rows.append(dict(date=str(day.date()),
                         equity=round(e, 2),
                         day_pnl=round(e - prev, 2),
                         day_ret_pct=round(100.0 * (e - prev) / prev, 2)))
        prev = e
    # trades per day
    if tr is not None and not tr.empty and "exit_time" in tr:
        tr2 = tr.copy()
        tr2["exit_time"] = pd.to_datetime(tr2["exit_time"])
        per_day = tr2.groupby(tr2["exit_time"].dt.date).agg(
            trades=("pnl", "size"),
            wins=("pnl", lambda s: int((s > 0).sum())),
            pnl=("pnl", "sum"))
        for r in rows:
            d = pd.to_datetime(r["date"]).date()
            if d in per_day.index:
                r["trades"] = int(per_day.loc[d, "trades"])
                r["win_rate"] = round(100.0 * per_day.loc[d, "wins"] / per_day.loc[d, "trades"], 1)
                r["pnl"] = round(float(per_day.loc[d, "pnl"]), 2)
    df = pd.DataFrame(rows)
    df.to_csv("/work/rl_gold/backtest_aug2025_v4_daily.csv", index=False)
    print("\n=== DAILY (v4, Aug 2025) ===")
    print(df.to_string(index=False))
    print(f"\nbest day: {df['day_pnl'].max():+.2f}  worst day: {df['day_pnl'].min():+.2f}  "
          f"win days: {(df['day_pnl']>0).sum()}/{len(df)}  total: {df['day_pnl'].sum():+.2f}")


if __name__ == "__main__":
    main()
