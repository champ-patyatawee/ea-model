"""Phase 3: backtest the synthetic-trained best_model on REAL Jul-Sep 2026
(the window never seen when the synthetic data was built)."""
from __future__ import annotations
import sys
from pathlib import Path

REPO = "/work/vendor/Reinforcement_Trading_Part_2"
sys.path.insert(0, REPO)

from config import CFG  # noqa: E402
CFG.csv_path = Path("/work/rl_gold/xauusdm_m1.csv")   # REAL data
CFG.time_col = "time_utc"; CFG.source_tz = "UTC"; CFG.timestamp_is_bar_open = True
CFG.decision_timeframe = "H1"; CFG.spread_price = 0.26; CFG.slippage_price = 0.02
CFG.commission_per_trade = 0.0; CFG.initial_equity = 10_000.0; CFG.risk_fraction = 0.005

from stable_baselines3 import PPO  # noqa: E402
from data_loader import load_mt_ohlcv_csv, resample_ohlcv  # noqa: E402
from features import prepare_feature_frame  # noqa: E402
from env_bracket import BracketTradingEnv  # noqa: E402
from evaluate import full_report  # noqa: E402
import train_ppo as T  # noqa: E402

MODEL = "/work/rl_gold/pod_results/best_model/best_model.zip"
VECN = "/work/rl_gold/pod_results/best_model/best_model_vecnorm.pkl"


def main():
    m1 = load_mt_ohlcv_csv(CFG.csv_path, time_col=CFG.time_col, source_tz=CFG.source_tz,
                           timestamp_is_bar_open=CFG.timestamp_is_bar_open,
                           bar_duration=CFG.pandas_execution_tf)
    dec = resample_ohlcv(m1, CFG.pandas_tf)
    feat, fc = prepare_feature_frame(dec, warmup_bars=CFG.warmup_bars,
                                     atr_period=CFG.atr_period, rsi_period=CFG.rsi_period)

    model = PPO.load(MODEL, device="cpu")

    periods = {
        "2026-07": ("2026-07-01", "2026-08-01"),
        "2026-08": ("2026-08-01", "2026-09-01"),
        "2026-09": ("2026-09-01", "2026-09-29"),
        "Jul-Sep": ("2026-07-01", "2026-09-29"),
    }
    # features need warmup -> slice from a bit earlier for July
    for name, (a, b) in periods.items():
        lo = (feat.index >= a)
        if name == "2026-07":  # include warmup bars before July
            lo = (feat.index >= "2026-06-01")
        sub = feat.loc[lo & (feat.index < b)]
        if len(sub) < 10:
            print(name, "too few bars"); continue
        eq, trades, rep = T._rollout_on_split(model, VECN, m1, fc, sub)
        m = rep if isinstance(rep, dict) else rep["value"].to_dict()
        # trim equity/trades to the actual requested window
        if name != "2026-07":
            eq = eq.loc[eq.index >= a]
        print(f"{name:9} ret={m.get('total_return_pct'):+7.2f}%  PF={m.get('profit_factor'):.3f}  "
              f"Sharpe={m.get('sharpe_like'):+6.2f}  DD={m.get('max_drawdown_pct'):+6.2f}%  "
              f"trades={m.get('n_trades')}")
        if name == "Jul-Sep" and eq is not None and not eq.empty:
            eq.to_csv("/work/rl_gold/phase3_julsep_equity.csv")


if __name__ == "__main__":
    main()
