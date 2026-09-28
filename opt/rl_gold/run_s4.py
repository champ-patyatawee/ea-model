"""S4: sliding walk-forward on OUR data (short-history-adapted windows)."""
from __future__ import annotations
import sys
from pathlib import Path

REPO = "/work/vendor/Reinforcement_Trading_Part_2"
sys.path.insert(0, REPO)

from config import CFG  # noqa: E402

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

# short-history windows (we only have ~20 months of M1)
CFG.sliding_train_years = 0.75      # 9 months
CFG.sliding_val_months = 2
CFG.sliding_test_months = 2
CFG.sliding_step_months = 2
CFG.split_embargo_bars = 100

import train_ppo as T  # noqa: E402

if __name__ == "__main__":
    T.train_sliding_walk_forward(
        total_timesteps=500_000,
        seed=42,
        out_dir="/work/rl_gold/models_s4",
        train_episode_steps=2048,
        target_evals_per_fold=20,
        dd_penalty=1.0,
        n_envs=1,
        device="cpu",
    )
