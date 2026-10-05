"""Replay the v6c RL models (H1 decision, v3 action) over real XAUUSDm M1.

Default target: Jul/Aug/Sep 2026, using the M1 CSV fetched from the live MT5
(`xauusdm_m1_2026q3.csv`). Reports overall + per-month stats per fold.

Run inside the `rl` container:
    python3 /work/rl_gold/backtest_months_v6.py
"""
from __future__ import annotations
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
import gymnasium as gym
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize

# v6 used the pristine Reinforcement_Trading_Part_2 env/features.
sys.path.insert(0, "/work/vendor/Reinforcement_Trading_Part_2")
from config import CFG                       # noqa: E402
from data_loader import load_mt_ohlcv_csv, resample_ohlcv  # noqa: E402
from features import prepare_feature_frame   # noqa: E402
from env_bracket import BracketTradingEnv    # noqa: E402
from evaluate import full_report             # noqa: E402
from sb3_contrib import RecurrentPPO         # noqa: E402

# --- v6 training config (train_v6.py) ---------------------------------------
CFG.time_col = "time_utc"; CFG.source_tz = "UTC"; CFG.timestamp_is_bar_open = True
CFG.decision_timeframe = "H1"; CFG.execution_timeframe = "1min"
CFG.spread_price = 0.30; CFG.slippage_price = 0.02; CFG.commission_per_trade = 0.0
CFG.initial_equity = 10_000.0; CFG.risk_fraction = 0.005

SL_ATR = (1.0, 1.5, 2.0)
TP_R = (1.0, 1.5, 2.0, 3.0)
GIVEBACK = 0.02
LOSS_PEN = 0.20

CSV = sys.argv[1] if len(sys.argv) > 1 else "/work/rl_gold/xauusdm_m1_2026may_oct.csv"
MODELS = "/work/rl_gold/export_v6/models_v6c"
OUT = "/work/rl_gold/backtest_2026q3_v6c.csv"


def _slice_m1(m1, dec):
    if dec.empty:
        return m1.iloc[0:0].copy()
    return m1.loc[(m1.index > dec.index.min()) & (m1.index <= dec.index.max())].copy()


class _CaptureDone(gym.Wrapper):
    def __init__(self, env):
        super().__init__(env)
        self.saved_equity = None
        self.saved_trades = None

    def step(self, action):
        obs, r, term, trunc, info = self.env.step(action)
        if term or trunc:
            inner = self.env
            while hasattr(inner, "env"):
                inner = inner.env
            self.saved_equity = inner.equity_curve()
            self.saved_trades = inner.trade_log()
        return obs, r, term, trunc, info


def build_env(dec, m1, fc):
    return BracketTradingEnv(
        dec, m1, fc, sl_atr_multipliers=SL_ATR, tp_r_multipliers=TP_R,
        initial_equity=CFG.initial_equity, risk_fraction=CFG.risk_fraction,
        spread_price=CFG.spread_price, slippage_price=CFG.slippage_price,
        commission_per_trade=CFG.commission_per_trade,
        holding_penalty=CFG.holding_penalty, reward_mtm_weight=CFG.reward_mtm_weight,
        giveback_penalty=GIVEBACK, loss_penalty=LOSS_PEN)


def rollout(model, vecnorm_path, m1, fc, dec):
    m1s = _slice_m1(m1, dec)
    raw = DummyVecEnv([lambda: _CaptureDone(build_env(dec, m1s, fc))])
    venv = VecNormalize.load(str(vecnorm_path), raw)
    venv.training = False; venv.norm_reward = False
    obs = venv.reset(); lstm = None; done = [False]
    while not done[0]:
        action, lstm = model.predict(obs, state=lstm,
                                     episode_start=np.array([True]), deterministic=True)
        obs, _r, done, _i = venv.step(action)
    cap = venv.venv.envs[0]
    eq = cap.saved_equity if cap.saved_equity is not None else pd.DataFrame()
    tr = cap.saved_trades if cap.saved_trades is not None else pd.DataFrame()
    return eq, tr


def monthly(eq, tr):
    """Return list of dicts: one row per calendar month with ret% and trades."""
    if eq is None or eq.empty:
        return []
    eq = eq.copy()
    eq["equity"] = eq["equity"].astype(float)
    rows = []
    months = sorted(set(eq.index.to_period("M")))
    for m in months:
        seg = eq[eq.index.to_period("M") == m]
        start = float(seg["equity"].iloc[0]); end = float(seg["equity"].iloc[-1])
        n = 0; wins = 0; pnl = 0.0
        if tr is not None and not tr.empty and "exit_time" in tr:
            t = tr[pd.to_datetime(tr["exit_time"]).dt.to_period("M") == m]
            n = len(t); wins = int((t["pnl"] > 0).sum()); pnl = float(t["pnl"].sum())
        rows.append(dict(month=str(m), ret_pct=100.0 * (end - start) / start,
                         equity_end=round(end, 2), trades=n,
                         winrate_pct=(100.0 * wins / n if n else float("nan")),
                         pnl=round(pnl, 2)))
    return rows


def main():
    m1 = load_mt_ohlcv_csv(Path(CSV), time_col=CFG.time_col, source_tz=CFG.source_tz,
                           timestamp_is_bar_open=True, bar_duration="1min")
    m1 = m1.sort_index()
    dec = resample_ohlcv(m1, CFG.pandas_tf)
    feat, fc = prepare_feature_frame(dec, warmup_bars=CFG.warmup_bars)
    print(f"full H1 feature bars: {len(feat)}  "
          f"{feat.index.min()} -> {feat.index.max()}", flush=True)

    # Warm up on the earlier bars, but only start TRADING at START (so the
    # reported Jul/Aug/Sep windows are complete and start from initial equity).
    start = pd.Timestamp("2026-07-01", tz="UTC")
    feat = feat.loc[feat.index >= start].copy()
    print(f"trading window: {len(feat)} H1 bars  "
          f"{feat.index.min()} -> {feat.index.max()}", flush=True)

    folds = sorted([p for p in Path(MODELS).glob("fold_*") if p.is_dir()],
                   key=lambda p: int(p.name.split("_")[1]))
    all_rows, mon_rows = [], []
    for d in folds:
        k = int(d.name.split("_")[1])
        mp = d / "best_model" / "best_model.zip"
        vp = d / "best_model" / "best_model_vecnorm.pkl"
        if not mp.exists():
            mp, vp = d / "final_model.zip", d / "final_vecnorm.pkl"
        if not mp.exists():
            print(f"fold {k}: no model"); continue
        t0 = time.time()
        model = RecurrentPPO.load(str(mp), device="cpu")
        eq, tr = rollout(model, vp, m1, fc, feat)
        el = time.time() - t0
        rep = full_report(eq, tr, initial_equity=CFG.initial_equity,
                          periods_per_year=CFG.periods_per_year)["value"].to_dict()
        row = dict(fold=k, ret_pct=rep.get("total_return_pct"),
                   pf=rep.get("profit_factor"), winrate_pct=rep.get("win_rate_pct"),
                   avg_r=rep.get("avg_r"), sharpe=rep.get("sharpe_like"),
                   dd_pct=rep.get("max_drawdown_pct"), trades=rep.get("n_trades"))
        all_rows.append(row)
        for mr in monthly(eq, tr):
            mr["fold"] = k
            mon_rows.append(mr)
        print(f"fold {k}: ret={row['ret_pct']:+.2f}%  PF={row['pf']:.2f}  "
              f"win={row['winrate_pct']:.1f}%  avgR={row['avg_r']:+.2f}  "
              f"Sharpe={row['sharpe']:+.2f}  DD={row['dd_pct']:+.2f}%  "
              f"trades={row['trades']}  ({el:.0f}s)", flush=True)

    df = pd.DataFrame(all_rows)
    df.to_csv(OUT, index=False)
    print("\n=== Q3-2026 (Jul/Aug/Sep) XAUUSDm — v6c folds ===")
    print(df.to_string(index=False))
    if len(df):
        print(f"positive folds: {(df['ret_pct']>0).sum()}/{len(df)}  "
              f"mean ret: {df['ret_pct'].mean():+.2f}%  mean PF: {df['pf'].mean():.2f}  "
              f"mean win: {df['winrate_pct'].mean():.1f}%  mean trades: {df['trades'].mean():.0f}")

    md = pd.DataFrame(mon_rows)
    if len(md):
        print("\n=== per fold x month ===")
        print(md.to_string(index=False))
        print(f"\nsaved: {OUT}")


if __name__ == "__main__":
    main()
