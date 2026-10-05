"""Train v7 — micro-account ($100) daily-target fibo RL.

Data: real XAUUSDm M1 (2019-2026) -> v7 features (M5 + H1 + fibo).
Env : MicroTradingEnv (min-lot 0.01, daily cap -$20 / target +$15).
Plan: calendar walk-forward; per fold train RecurrentPPO, checkpoint by val
      score, then replay the untouched test window and report $/day stats.

Run on the pod:
    python3 -u train_v7.py
Env vars: TOTAL_STEPS N_ENVS OUT_ROOT MAX_FOLDS SMOKE SYNTH_CSV
"""
from __future__ import annotations
import os
import sys
import time
import functools
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd
import gymnasium as gym
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv, VecNormalize
from sb3_contrib import RecurrentPPO

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, "/root/rl_gold")
sys.path.insert(0, "/workspace/rl_gold")
from env_bracket_micro_v7 import MicroTradingEnv  # noqa: E402
import data_folds_real as D  # noqa: E402

REAL = os.environ.get("REAL_CSV", "/root/rl_gold/xauusdm_m1_all.csv")
EXTRA = os.environ.get("EXTRA_CSV", "/root/rl_gold/xauusdm_m1_2026may_oct.csv")
OUT_ROOT = os.environ.get("OUT_ROOT", "/root/rl_gold/models_v7")
TOTAL_STEPS = int(os.environ.get("TOTAL_STEPS", "300000"))
N_ENVS = int(os.environ.get("N_ENVS", "16"))
MAX_FOLDS = int(os.environ.get("MAX_FOLDS", "0"))          # 0 = all
SMOKE = os.environ.get("SMOKE", "0") == "1"
EPISODE_STEPS = int(os.environ.get("EPISODE_STEPS", "2016"))
EVAL_FREQ = int(os.environ.get("EVAL_FREQ", "25000"))
DD_PEN = float(os.environ.get("DD_PEN", "1.0"))

ENV_KW = dict(initial_equity=100.0, contract_size=100.0, min_lot=0.01,
              spread_price=0.24, slippage_price=0.02, commission_per_trade=0.0,
              daily_cap=20.0, daily_target=15.0, stop_at_target=True,
              ruin_equity=0.0, flat_penalty=0.001)


class _Capture(gym.Wrapper):
    def __init__(self, env):
        super().__init__(env)
        self.eq = None; self.tr = None; self.dl = None

    def step(self, action):
        obs, r, term, trunc, info = self.env.step(action)
        if term or trunc:
            inner = self.env
            while hasattr(inner, "env"):
                inner = inner.env
            self.eq = inner.equity_curve(); self.tr = inner.trade_log(); self.dl = inner.daily_log()
        return obs, r, term, trunc, info


def build_env(dec, m1, fc, randomize_start=False, episode_steps=None):
    env = MicroTradingEnv(dec, m1, fc, max_episode_steps=episode_steps,
                          randomize_start=randomize_start, **ENV_KW)
    return _Capture(env)


def _rollout(model, venv):
    obs = venv.reset(); lstm = None; done = [False]
    while not done[0]:
        action, lstm = model.predict(obs, state=lstm, episode_start=np.array([True]),
                                     deterministic=True)
        obs, _r, done, _i = venv.step(action)
    cap = venv.venv.envs[0]
    return cap.eq, cap.tr, cap.dl


def _greedy_rollout(model, vecnorm_path, dec, m1, fc):
    raw = DummyVecEnv([lambda: build_env(dec, m1, fc)])
    venv = VecNormalize.load(str(vecnorm_path), raw)
    venv.training = False; venv.norm_reward = False
    return _rollout(model, venv)


def _eval_rollout(model, train_venv, dec, m1, fc):
    """Eval during training using the live training obs_rms (no file round-trip)."""
    raw = DummyVecEnv([lambda: build_env(dec, m1, fc)])
    venv = VecNormalize(raw, norm_obs=True, norm_reward=False, clip_obs=10.0, training=False)
    venv.obs_rms = deepcopy(train_venv.obs_rms)
    venv.ret_rms = deepcopy(train_venv.ret_rms)
    return _rollout(model, venv)


def _score(eq):
    if eq is None or eq.empty:
        return -1e9, 0.0, 0.0
    e = eq["equity"].astype(float)
    ret = e.iloc[-1] / 100.0 - 1.0
    dd = float((e / e.cummax() - 1.0).min())
    return ret - DD_PEN * abs(dd), ret * 100, dd * 100


class _ValCkpt(BaseCallback):
    def __init__(self, val_env_data, out_dir, freq, train_venv, seed=42, verbose=1):
        super().__init__(verbose=verbose)
        self.val = val_env_data; self.out = Path(out_dir); self.freq = freq
        self.train_venv = train_venv; self.best = -1e9; self._last = 0; self.rows = []

    def _on_step(self):
        if self.num_timesteps - self._last < self.freq:
            return True
        self._last = self.num_timesteps
        dec, m1, fc = self.val
        eq, tr, dl = _eval_rollout(self.model, self.train_venv, dec, m1, fc)
        sc, ret, dd = _score(eq)
        mark = ""
        if sc > self.best:
            self.best = sc; mark = "  <- BEST"
            self.out.mkdir(parents=True, exist_ok=True)
            self.model.save(str(self.out / "best_model"))
            # save a fresh vecnorm tied to the training stats
            self.train_venv.save(str(self.out / "best_model_vecnorm.pkl"))
        self.rows.append(dict(timesteps=self.num_timesteps, val_ret=round(ret, 3),
                              val_dd=round(dd, 3), score=round(sc, 4)))
        if self.verbose:
            print(f"[{self.num_timesteps:>8,}] val_ret={ret:+6.2f}% dd={dd:5.1f}% "
                  f"score={sc:+6.3f}{mark}", flush=True)
        return True


def daily_stats(dl):
    if dl is None or dl.empty:
        return dict(days=0, mean_day=float("nan"), median_day=float("nan"),
                    pct_ge10=float("nan"), pct_ge20=float("nan"), pct_green=float("nan"),
                    worst_day=float("nan"))
    p = dl["pnl"].astype(float)
    return dict(days=int(len(p)), mean_day=float(p.mean()), median_day=float(p.median()),
                pct_ge10=float((p >= 10).mean() * 100), pct_ge20=float((p >= 20).mean() * 100),
                pct_green=float((p > 0).mean() * 100), worst_day=float(p.min()))


def train_fold(tr, va, te, m1, fc, out_dir, device="cuda"):
    tr_m1 = D.slice_m1(m1, tr); va_m1 = D.slice_m1(m1, va); te_m1 = D.slice_m1(m1, te)

    fns = [functools.partial(build_env, tr, tr_m1, fc, True, EPISODE_STEPS) for _ in range(N_ENVS)]
    start_method = os.environ.get("VEC_START_METHOD", "spawn")
    train_raw = SubprocVecEnv(fns, start_method=start_method)
    train_env = VecNormalize(train_raw, norm_obs=True, norm_reward=True, clip_obs=10.0)

    Path(out_dir).mkdir(parents=True, exist_ok=True)
    ck = _ValCkpt((va, va_m1, fc), out_dir, EVAL_FREQ, train_env)

    model = RecurrentPPO(
        "MlpLstmPolicy", train_env, device=device, verbose=0, seed=42,
        learning_rate=6e-5, gamma=0.99, gae_lambda=0.95, clip_range=0.1,
        ent_coef=0.03, vf_coef=0.5, n_steps=EPISODE_STEPS, batch_size=512,
        n_epochs=5, target_kl=0.025,
        policy_kwargs=dict(net_arch=[128], lstm_hidden_size=128, n_lstm_layers=1,
                           shared_lstm=False, enable_critic_lstm=True))
    model.learn(total_timesteps=TOTAL_STEPS, callback=ck)
    model.save(Path(out_dir) / "final_model")
    train_env.save(str(Path(out_dir) / "final_vecnorm.pkl"))

    mp = Path(out_dir) / "best_model.zip"; vp = Path(out_dir) / "best_model_vecnorm.pkl"
    if not mp.exists():
        mp, vp = Path(out_dir) / "final_model.zip", Path(out_dir) / "final_vecnorm.pkl"
    best = RecurrentPPO.load(str(mp), device="cpu")
    eq, tr, dl = _greedy_rollout(best, vp, te, te_m1, fc)
    return eq, tr, dl, pd.DataFrame(ck.rows)


def main():
    if SMOKE:
        globals()["TOTAL_STEPS"] = int(os.environ.get("TOTAL_STEPS", "20000"))
        globals()["MAX_FOLDS"] = int(os.environ.get("MAX_FOLDS", "1"))
        globals()["EVAL_FREQ"] = int(os.environ.get("EVAL_FREQ", "10000"))
    print(f"device={'cuda' if __import__('torch').cuda.is_available() else 'cpu'} "
          f"steps={TOTAL_STEPS} n_envs={N_ENVS} out={OUT_ROOT}", flush=True)

    t0 = time.time()
    m1, feat, fc = D.prepare(REAL, EXTRA)
    folds = D.make_folds(feat)
    if MAX_FOLDS:
        folds = folds[:MAX_FOLDS]
    print(f"M1={len(m1)} feat={len(feat)} features={len(fc)} folds={len(folds)} "
          f"({time.time()-t0:.0f}s build)", flush=True)

    rows = []
    for k, (tr, va, te) in enumerate(folds, 1):
        d = f"{OUT_ROOT}/fold_{k}"
        t1 = time.time()
        print(f"--- fold {k}/{len(folds)}  test {te.index.min().date()}..{te.index.max().date()} ---", flush=True)
        eq, tr_log, dl, ck = train_fold(tr, va, te, m1, fc, d,
                                        device="cuda" if __import__('torch').cuda.is_available() else "cpu")
        ck.to_csv(Path(d) / "consistency_evals.csv", index=False)
        ds = daily_stats(dl)
        ret = float(eq["equity"].iloc[-1] / 100.0 - 1.0) * 100 if eq is not None and not eq.empty else float("nan")
        n_trades = int(len(tr_log)) if tr_log is not None else 0
        row = dict(fold=k, test_start=str(te.index.min().date()), test_end=str(te.index.max().date()),
                   ret_pct=ret, trades=n_trades, **ds)
        rows.append(row)
        print(f"fold {k} TEST ret={ret:+.2f}%  mean_day=${ds['mean_day']:+.2f}  "
              f"median=${ds['median_day']:+.2f}  green={ds['pct_green']:.0f}%  "
              f">=10={ds['pct_ge10']:.0f}%  worst=${ds['worst_day']:+.2f}  "
              f"trades={n_trades}  ({time.time()-t1:.0f}s)", flush=True)

    df = pd.DataFrame(rows)
    Path(OUT_ROOT).mkdir(parents=True, exist_ok=True)
    df.to_csv(f"{OUT_ROOT}/summary.csv", index=False)
    print("\n=== v7 walk-forward OOS (real XAUUSDm) ===")
    print(df.to_string(index=False))
    if len(df):
        print(f"folds positive: {(df['ret_pct']>0).sum()}/{len(df)}  "
              f"mean ret {df['ret_pct'].mean():+.2f}%  mean $/day {df['mean_day'].mean():+.2f}  "
              f"median $/day {df['median_day'].mean():+.2f}  green {df['pct_green'].mean():.0f}%")


if __name__ == "__main__":
    main()
