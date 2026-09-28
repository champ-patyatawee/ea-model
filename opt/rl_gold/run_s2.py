"""S2: PPO smoke test on OUR data (single split, small budget)."""
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

import train_ppo as T  # noqa: E402

if __name__ == "__main__":
    T.train(
        total_timesteps=50_000,
        seed=42,
        out_dir="/work/rl_gold/models_s2",
        train_episode_steps=2048,
        eval_freq=10_000,
        dd_penalty=1.0,
        n_envs=1,
        device="cpu",
        reveal_test=False,
    )
