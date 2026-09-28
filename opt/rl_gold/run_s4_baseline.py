"""A: baseline trend-hold evaluated on the SAME sliding walk-forward windows as S4."""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

REPO = "/work/vendor/Reinforcement_Trading_Part_2"
sys.path.insert(0, REPO)

from config import CFG  # noqa: E402
CFG.csv_path = Path("/work/rl_gold/xauusdm_m1.csv")
CFG.time_col = "time_utc"; CFG.source_tz = "UTC"; CFG.timestamp_is_bar_open = True
CFG.decision_timeframe = "H1"; CFG.spread_price = 0.26; CFG.slippage_price = 0.02
CFG.commission_per_trade = 0.0; CFG.initial_equity = 10_000.0; CFG.risk_fraction = 0.005
CFG.sliding_train_years = 0.75; CFG.sliding_val_months = 2
CFG.sliding_test_months = 2; CFG.sliding_step_months = 2
CFG.split_embargo_bars = 100

from data_loader import load_mt_ohlcv_csv, resample_ohlcv, make_sliding_folds  # noqa: E402
from features import prepare_feature_frame  # noqa: E402
from env_bracket import BracketTradingEnv  # noqa: E402
from baselines import (  # noqa: E402
    ema_atr_trend_policy, make_trend_hold_policy, TrendHoldPolicyParams,
    evaluate_policy,
)
from evaluate import full_report  # noqa: E402


def slice_m1(m1, dec):
    if dec.empty:
        return m1.iloc[0:0].copy()
    return m1.loc[(m1.index > dec.index.min()) & (m1.index <= dec.index.max())].copy()


def make_env(dec, m1, fc):
    return BracketTradingEnv(dec, m1, fc,
        sl_atr_multipliers=CFG.sl_atr_multipliers, tp_r_multipliers=CFG.tp_r_multipliers,
        initial_equity=CFG.initial_equity, risk_fraction=CFG.risk_fraction,
        spread_price=CFG.spread_price, slippage_price=CFG.slippage_price,
        commission_per_trade=CFG.commission_per_trade, holding_penalty=CFG.holding_penalty,
        reward_mtm_weight=CFG.reward_mtm_weight)


def main():
    m1 = load_mt_ohlcv_csv(CFG.csv_path, time_col=CFG.time_col, source_tz=CFG.source_tz,
                           timestamp_is_bar_open=CFG.timestamp_is_bar_open,
                           bar_duration=CFG.pandas_execution_tf)
    dec = resample_ohlcv(m1, CFG.pandas_tf)
    feat, fc = prepare_feature_frame(dec, warmup_bars=CFG.warmup_bars,
                                     atr_period=CFG.atr_period, rsi_period=CFG.rsi_period)
    folds = make_sliding_folds(feat, train_years=CFG.sliding_train_years,
                               val_months=CFG.sliding_val_months,
                               test_months=CFG.sliding_test_months,
                               step_months=CFG.sliding_step_months,
                               embargo_bars=CFG.split_embargo_bars)
    print(f"folds: {len(folds)}")

    policies = {
        "trend_hold(thr.9,sl1.5,tp3R)": make_trend_hold_policy(
            TrendHoldPolicyParams(threshold_atr=0.9, sl_idx=1, tp_idx=3)),
        "ema_atr(thr.10,sl1.5,tp2R)": ema_atr_trend_policy,
    }

    for name, pol in policies.items():
        print("\n" + "=" * 70)
        print(name)
        rows = []
        parts = []
        running = CFG.initial_equity
        for k, (tr, va, te) in enumerate(folds, 1):
            te_m1 = slice_m1(m1, te)
            eq, trades, rep = evaluate_policy(make_env(te, te_m1, fc), pol,
                                              initial_equity=CFG.initial_equity,
                                              periods_per_year=CFG.periods_per_year)
            m = rep["value"].to_dict()
            rows.append(dict(fold=k, start=str(te.index.min().date()),
                             end=str(te.index.max().date()),
                             ret=m.get("total_return_pct"), pf=m.get("profit_factor"),
                             sharpe=m.get("sharpe_like"), dd=m.get("max_drawdown_pct"),
                             trades=m.get("n_trades")))
            if eq is not None and not eq.empty and "equity" in eq and not trades.empty:
                scaled = eq["equity"].astype(float) / CFG.initial_equity * running
                parts.append(scaled)
                running = float(scaled.iloc[-1])
        df = pd.DataFrame(rows)
        print(df.to_string(index=False))
        pos = int((df["ret"] > 0).sum()); pfok = int((df["pf"] > 1.0).sum())
        print(f"  folds positive: {pos}/{len(df)}   PF>1: {pfok}/{len(df)}   "
              f"mean ret={df['ret'].mean():+.2f}%  worst PF={df['pf'].min():.2f}")
        if parts:
            st = pd.concat(parts).to_frame("equity")
            oos = full_report(st, pd.DataFrame(), initial_equity=CFG.initial_equity,
                              periods_per_year=CFG.periods_per_year)["value"].to_dict()
            print(f"  STITCHED OOS: return={oos.get('total_return_pct'):+.1f}%  "
                  f"Sharpe={oos.get('sharpe_like'):+.2f}  maxDD={oos.get('max_drawdown_pct'):+.1f}%")


if __name__ == "__main__":
    main()
