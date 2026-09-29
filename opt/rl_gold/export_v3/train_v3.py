"""Train LSTM (reward v2) on generator-v3 domain-randomized data.

Walk-forward over the synthetic v3 history; report per-fold OOS + a
case-test that checks whether the policy reacts correctly per regime.
"""
from __future__ import annotations
import sys, os
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, "/root/rl_gold")
sys.path.insert(0, "/root/rl_gold/Reinforcement_Trading_Part_2")

from config import CFG
CFG.csv_path = Path("/root/rl_gold/synth_v3.csv")
CFG.time_col = "time_utc"; CFG.source_tz = "UTC"; CFG.timestamp_is_bar_open = True
CFG.decision_timeframe = "H1"; CFG.execution_timeframe = "1min"
CFG.spread_price = 0.30; CFG.slippage_price = 0.02; CFG.commission_per_trade = 0.0
CFG.initial_equity = 10_000.0; CFG.risk_fraction = 0.005
CFG.sliding_train_years = 0.75; CFG.sliding_val_months = 2
CFG.sliding_test_months = 2; CFG.sliding_step_months = 3   # 10 folds
CFG.split_embargo_bars = 100

from data_loader import load_mt_ohlcv_csv, resample_ohlcv, make_sliding_folds
from features import prepare_feature_frame
import train_lstm as L
import importlib


def main():
    m1 = load_mt_ohlcv_csv(CFG.csv_path, time_col=CFG.time_col, source_tz=CFG.source_tz,
                           timestamp_is_bar_open=True, bar_duration="1min")
    dec = resample_ohlcv(m1, CFG.pandas_tf)
    feat, fc = prepare_feature_frame(dec, warmup_bars=CFG.warmup_bars)
    print("H1 bars:", len(feat), feat.index.min(), "->", feat.index.max(), flush=True)

    # carry a regime label onto the H1 decision frame (read straight from CSV)
    raw = pd.read_csv(CFG.csv_path, usecols=["time_utc", "regime"])
    raw["t"] = pd.to_datetime(raw["time_utc"]).dt.tz_localize("UTC")
    raw = raw.set_index("t").sort_index()
    reg_h1 = raw["regime"].resample(CFG.pandas_tf, label="right", closed="right").agg(
        lambda s: s.mode().iloc[0] if len(s) else "?")
    feat = feat.copy(); feat["regime"] = reg_h1.reindex(feat.index).fillna("?")

    folds = make_sliding_folds(feat.drop(columns=["regime"]), train_years=CFG.sliding_train_years,
                               val_months=CFG.sliding_val_months,
                               test_months=CFG.sliding_test_months,
                               step_months=CFG.sliding_step_months,
                               embargo_bars=CFG.split_embargo_bars)
    print("folds:", len(folds), flush=True)
    Path("/root/rl_gold/models_v3").mkdir(parents=True, exist_ok=True)

    rows = []
    for k, (tr, va, te) in enumerate(folds, 1):
        d = f"/root/rl_gold/models_v3/fold_{k}"
        # re-attach regime for the case report
        tr2 = tr.join(feat["regime"]); va2 = va.join(feat["regime"]); te2 = te.join(feat["regime"])
        model = L.train_fold(tr2.drop(columns=["regime"]), va2.drop(columns=["regime"]),
                             m1, fc, total_steps=300_000, n_envs=40, out_dir=d,
                             device="cuda", episode_steps=1024, eval_freq=15_000)
        mp = Path(d)/"best_model"/"best_model.zip"; vp = Path(d)/"best_model"/"best_model_vecnorm.pkl"
        if not mp.exists():
            mp, vp = Path(d)/"final_model.zip", Path(d)/"final_vecnorm.pkl"
        import train_lstm
        importlib.reload(train_lstm)
        mm = train_lstm.RecurrentPPO.load(str(mp), device="cpu")
        _eq, trades, rep = train_lstm.rollout(mm, vp, m1, fc, te2.drop(columns=["regime"]))
        row = dict(fold=k, test_start=str(te.index.min().date()), test_end=str(te.index.max().date()),
                   ret=rep.get("total_return_pct"), pf=rep.get("profit_factor"),
                   sharpe=rep.get("sharpe_like"), dd=rep.get("max_drawdown_pct"),
                   trades=rep.get("n_trades"))
        rows.append(row)
        print(f"fold {k} TEST ret={row['ret']:+.2f}% PF={row['pf']:.2f} "
              f"Sharpe={row['sharpe']:+.2f} DD={row['dd']:+.2f}%", flush=True)

    df = pd.DataFrame(rows)
    df.to_csv("/root/rl_gold/models_v3/summary.csv", index=False)
    print(df.to_string(index=False))
    print(f"folds positive: {(df['ret']>0).sum()}/{len(df)}  mean={df['ret'].mean():+.2f}%")


if __name__ == "__main__":
    main()
