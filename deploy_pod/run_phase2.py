"""Phase 2: train PPO on the realistic synthetic data (CPU pod, 8 vCPU)."""
from __future__ import annotations
import sys
from pathlib import Path

REPO = "/root/rl_gold/Reinforcement_Trading_Part_2"
sys.path.insert(0, REPO)

from config import CFG  # noqa: E402
CFG.csv_path = Path("/root/rl_gold/synth_real_m1.csv")
CFG.time_col = "time_utc"; CFG.source_tz = "UTC"; CFG.timestamp_is_bar_open = True
CFG.decision_timeframe = "H1"; CFG.spread_price = 0.26; CFG.slippage_price = 0.02
CFG.commission_per_trade = 0.0; CFG.initial_equity = 10_000.0; CFG.risk_fraction = 0.005
CFG.sliding_train_years = 1.0
CFG.sliding_val_months = 3
CFG.sliding_test_months = 3
CFG.sliding_step_months = 3
CFG.split_embargo_bars = 100

import train_ppo as T  # noqa: E402

if __name__ == "__main__":
    # FAST run: fewer folds x fewer steps (user asked to finish quickly)
    T.train_sliding_walk_forward(
        total_timesteps=200_000, seed=42, out_dir="/root/rl_gold/models_phase2",
        train_episode_steps=2048, target_evals_per_fold=12, dd_penalty=1.0,
        n_envs=8, device="cpu",
    )
