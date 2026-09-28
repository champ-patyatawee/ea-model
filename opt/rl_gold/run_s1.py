"""S1: run the repo's baselines on OUR XAUUSDm M1 data (Gate 1).

Runs inside the `rl` container with /work mounted (repo at /work/vendor/...).
"""
from __future__ import annotations
import sys
from dataclasses import asdict
from pathlib import Path

REPO = "/work/vendor/Reinforcement_Trading_Part_2"
sys.path.insert(0, REPO)

from config import CFG               # noqa: E402
from data_loader import (            # noqa: E402
    describe_data, load_mt_ohlcv_csv, resample_ohlcv, split_train_val_test,
)
from features import prepare_feature_frame   # noqa: E402
from env_bracket import BracketTradingEnv     # noqa: E402
from baselines import (                        # noqa: E402
    ema_atr_trend_policy, evaluate_policy, make_trend_hold_policy,
    optimize_trend_hold_policy, random_policy,
)

# ---- patch config for our data ----
CFG.csv_path = Path("/work/rl_gold/xauusdm_m1.csv")
CFG.time_col = "time_utc"
CFG.source_tz = "UTC"
CFG.timestamp_is_bar_open = True
CFG.decision_timeframe = "H1"
CFG.spread_price = 0.26
CFG.slippage_price = 0.02
CFG.commission_per_trade = 0.0
CFG.initial_equity = 10_000.0
CFG.risk_fraction = 0.005


def slice_m1(m1, dec):
    if dec.empty:
        return m1.iloc[0:0].copy()
    return m1.loc[(m1.index > dec.index.min()) & (m1.index <= dec.index.max())].copy()


def make_env(dec, m1, fc):
    return BracketTradingEnv(
        dec, m1, fc,
        sl_atr_multipliers=CFG.sl_atr_multipliers,
        tp_r_multipliers=CFG.tp_r_multipliers,
        initial_equity=CFG.initial_equity,
        risk_fraction=CFG.risk_fraction,
        spread_price=CFG.spread_price,
        slippage_price=CFG.slippage_price,
        commission_per_trade=CFG.commission_per_trade,
        holding_penalty=CFG.holding_penalty,
        reward_mtm_weight=CFG.reward_mtm_weight,
    )


def main():
    print("loading M1...", flush=True)
    m1 = load_mt_ohlcv_csv(CFG.csv_path, time_col=CFG.time_col, source_tz=CFG.source_tz,
                           timestamp_is_bar_open=CFG.timestamp_is_bar_open,
                           bar_duration=CFG.pandas_execution_tf)
    print(describe_data(m1).to_string(), flush=True)

    dec = resample_ohlcv(m1, CFG.pandas_tf)
    feat, fc = prepare_feature_frame(dec, warmup_bars=CFG.warmup_bars,
                                     atr_period=CFG.atr_period, rsi_period=CFG.rsi_period)
    print(f"decision bars {len(feat):,}  features {len(fc)}", flush=True)

    tr, va, te = split_train_val_test(feat, train_frac=CFG.train_frac,
                                      val_frac=CFG.val_frac, embargo_bars=CFG.split_embargo_bars)
    print(f"train {len(tr):,}  val {len(va):,}  test(sealed) {len(te):,}", flush=True)

    tr_m1, va_m1 = slice_m1(m1, tr), slice_m1(m1, va)

    # random baseline on val
    _, _, rep_rand = evaluate_policy(make_env(va, va_m1, fc), random_policy,
                                     initial_equity=CFG.initial_equity,
                                     periods_per_year=CFG.periods_per_year)
    print("\n== RANDOM on val ==")
    print(rep_rand.to_string(), flush=True)

    # optimize trend-hold on train->val
    print("\n== optimize trend-hold ==", flush=True)
    best, search = optimize_trend_hold_policy(
        lambda: make_env(tr, tr_m1, fc),
        threshold_grid=CFG.baseline_threshold_grid,
        sl_idx_grid=CFG.baseline_sl_idx_grid,
        tp_idx_grid=CFG.baseline_tp_idx_grid,
        initial_equity=CFG.initial_equity,
        val_env_factory=lambda: make_env(va, va_m1, fc),
        periods_per_year=CFG.periods_per_year,
    )
    print("best params:", best, flush=True)
    pol = make_trend_hold_policy(best)
    _, _, rep_val = evaluate_policy(make_env(va, va_m1, fc), pol,
                                    initial_equity=CFG.initial_equity,
                                    periods_per_year=CFG.periods_per_year)
    print("\n== SELECTED trend-hold on val ==")
    print(rep_val.to_string(), flush=True)
    search.to_csv("/work/rl_gold/s1_policy_search.csv", index=False)


if __name__ == "__main__":
    main()
