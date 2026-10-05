"""Train v5: multi-timeframe (H1 context + M5 decision), model controls everything.

Data:  generator-v3 synthetic (M1) -> M5 decisions with merged H1 context.
Policy: RecurrentPPO (LSTM), MultiDiscrete([3,8,8,6,2]).
Plan:  train one strong finale model, then validate on ALL walk-forward folds.

Run on the pod:  python -u /root/rl_gold/train_v5.py
"""
from __future__ import annotations
import sys, os, functools
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd
import gymnasium as gym
from stable_baselines3.common.callbacks import BaseCallback, CallbackList
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv, VecNormalize
from sb3_contrib import RecurrentPPO

RL = "/root/rl_gold/Reinforcement_Trading_Part_2"
sys.path.insert(0, "/root/rl_gold")
sys.path.insert(0, RL)

from config import CFG                      # noqa: E402
CFG.csv_path = Path("/root/rl_gold/synth_v3.csv")
CFG.time_col = "time_utc"; CFG.source_tz = "UTC"; CFG.timestamp_is_bar_open = True
CFG.decision_timeframe = "M5"; CFG.execution_timeframe = "1min"
CFG.spread_price = 0.30; CFG.slippage_price = 0.02; CFG.commission_per_trade = 0.0
CFG.initial_equity = 10_000.0; CFG.risk_fraction = 0.005
CFG.sliding_train_years = 1.0; CFG.sliding_val_months = 2
CFG.sliding_test_months = 2; CFG.sliding_step_months = 3
CFG.split_embargo_bars = 100
CFG.warmup_bars = 500

from data_loader import load_mt_ohlcv_csv, resample_ohlcv, make_sliding_folds  # noqa: E402
from features import prepare_feature_frame  # noqa: E402
from features_multitf import build_multitf  # noqa: E402
from env_bracket_v5 import BracketTradingEnvV5 as BracketTradingEnvV4  # noqa: E402
from evaluate import full_report, drawdown  # noqa: E402

GIVEBACK = float(os.environ.get("GIVEBACK", "0.10"))
LOSS_PEN = float(os.environ.get("LOSS_PEN", "0.20"))
CLOSE_BONUS = float(os.environ.get("CLOSE_BONUS", "0.05"))


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


def build_env(dec, m1, fc, randomize_start=False, episode_steps=None):
    env = BracketTradingEnvV4(
        dec, m1, fc, initial_equity=CFG.initial_equity,
        spread_price=CFG.spread_price, slippage_price=CFG.slippage_price,
        commission_per_trade=CFG.commission_per_trade,
        holding_penalty=CFG.holding_penalty, reward_mtm_weight=CFG.reward_mtm_weight,
        giveback_penalty=GIVEBACK, loss_penalty=LOSS_PEN, close_bonus=CLOSE_BONUS,
        randomize_start=randomize_start, max_episode_steps=episode_steps)
    return Monitor(env)


def _spawn(dec, m1, fc, steps):
    return build_env(dec, m1, fc, randomize_start=True, episode_steps=steps)


class _SyncNorm(BaseCallback):
    def __init__(self, tr, evals, freq):
        super().__init__(); self.tr = tr; self.evals = evals; self.freq = freq; self._last = 0

    def _on_step(self):
        if self.num_timesteps - self._last >= self.freq:
            for v in self.evals:
                v.obs_rms = deepcopy(self.tr.obs_rms); v.ret_rms = deepcopy(self.tr.ret_rms)
            self._last = self.num_timesteps
        return True


class _Consistency(BaseCallback):
    """Checkpoint by min(train_eval, val) drawdown-penalised quality (LSTM aware)."""

    def __init__(self, train_env, val_env, freq, save_path, log_path=None,
                 dd_penalty=1.0, min_trades=5, verbose=1, train_venv=None):
        super().__init__(verbose=verbose)
        self.train_env = train_env; self.val_env = val_env; self.freq = freq
        self.save_path = Path(save_path); self.log_path = Path(log_path) if log_path else None
        self.dd = dd_penalty; self.min_trades = min_trades; self.best = -np.inf
        self.train_venv = train_venv; self._last = 0; self._rows = []

    def _one(self, venv):
        obs = venv.reset()
        lstm_states = None
        done = [False]
        while not done[0]:
            action, lstm_states = self.model.predict(
                obs, state=lstm_states, episode_start=np.array([True]), deterministic=True)
            obs, _r, done, _i = venv.step(action)
        cap = venv.venv.envs[0]
        eq = cap.saved_equity
        if eq is not None and not eq.empty and "equity" in eq:
            dd = float(abs(drawdown(eq["equity"].astype(float)).min()) * 100.0)
            n = len(cap.saved_trades) if cap.saved_trades is not None else 0
        else:
            dd, n = 0.0, 0
        return dd, n

    def _on_step(self):
        if self.num_timesteps - self._last < self.freq:
            return True
        self._last = self.num_timesteps
        for v in (self.train_env, self.val_env):
            v.training = False; v.norm_reward = False
        tr_dd, tr_n = self._one(self.train_env)
        va_dd, va_n = self._one(self.val_env)

        def ret(venv):
            eq = venv.venv.envs[0].saved_equity
            if eq is None or eq.empty:
                return -1e9
            return float(eq["equity"].iloc[-1] / CFG.initial_equity - 1) * 100.0

        tr_r, va_r = ret(self.train_env), ret(self.val_env)
        q_tr = tr_r - self.dd * tr_dd; q_va = va_r - self.dd * va_dd
        score = min(q_tr, q_va)
        elig = tr_r > 0 and va_r > 0 and tr_n >= self.min_trades and va_n >= self.min_trades
        if elig and score > self.best:
            self.best = score
            self.save_path.mkdir(parents=True, exist_ok=True)
            self.model.save(str(self.save_path / "best_model"))
            if self.train_venv is not None:
                self.train_venv.save(str(self.save_path / "best_model_vecnorm.pkl"))
            mark = "  <- BEST"
        else:
            mark = ""
        if self.verbose:
            print(f"[{self.num_timesteps:>9,}] train={tr_r:+6.2f}/dd{tr_dd:4.1f}% "
                  f"val={va_r:+6.2f}/dd{va_dd:4.1f}% score={score:+7.2f}"
                  f"{'' if elig else '  (ineligible)'}{mark}", flush=True)
        self._rows.append(dict(timesteps=self.num_timesteps, train_r=round(tr_r, 3),
                               val_r=round(va_r, 3), train_dd=round(tr_dd, 3),
                               val_dd=round(va_dd, 3), score=round(score, 3), eligible=elig))
        if self.log_path:
            self.log_path.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(self._rows).to_csv(self.log_path / "consistency_evals.csv", index=False)
        return True


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
    rep = full_report(eq, tr, initial_equity=CFG.initial_equity,
                      periods_per_year=CFG.periods_per_year)["value"].to_dict()
    return eq, tr, rep


def train_fold(tr, va, m1, fc, total_steps, n_envs=40, seed=42, out_dir="models_v4",
               episode_steps=2048, eval_freq=25_000, dd_penalty=1.0, device="cuda"):
    print(f"Device: {device}", flush=True)
    tr_m1, va_m1 = _slice_m1(m1, tr), _slice_m1(m1, va)

    env_fns = [functools.partial(_spawn, tr, tr_m1, fc, episode_steps) for _ in range(n_envs)]
    start_method = os.environ.get("VEC_START_METHOD", "forkserver")
    train_raw = SubprocVecEnv(env_fns, start_method=start_method)
    train_env = VecNormalize(train_raw, norm_obs=True, norm_reward=True, clip_obs=10.0)

    val_raw = DummyVecEnv([lambda: _CaptureDone(build_env(va, va_m1, fc))])
    val_env = VecNormalize(val_raw, norm_obs=True, norm_reward=False, clip_obs=10.0, training=False)

    te = tr.iloc[-len(va):]
    te_m1 = _slice_m1(m1, te)
    te_raw = DummyVecEnv([lambda: _CaptureDone(build_env(te, te_m1, fc))])
    te_env = VecNormalize(te_raw, norm_obs=True, norm_reward=False, clip_obs=10.0, training=False)

    Path(out_dir).mkdir(parents=True, exist_ok=True)
    sync = _SyncNorm(train_env, [val_env, te_env], eval_freq)
    cons = _Consistency(te_env, val_env, eval_freq, Path(out_dir) / "best_model",
                        Path(out_dir) / "eval_logs", dd_penalty=dd_penalty, train_venv=train_env)

    model = RecurrentPPO(
        "MlpLstmPolicy", train_env, device=device, verbose=1, seed=seed,
        learning_rate=3e-4, gamma=0.99, gae_lambda=0.95,
        clip_range=0.2, ent_coef=0.01, vf_coef=0.5,
        n_steps=episode_steps, batch_size=2048, n_epochs=5, target_kl=0.03,
        policy_kwargs=dict(net_arch=[128], lstm_hidden_size=128, n_lstm_layers=1,
                           shared_lstm=False, enable_critic_lstm=True),
    )
    model.learn(total_timesteps=total_steps, callback=CallbackList([sync, cons]))
    model.save(Path(out_dir) / "final_model.zip")
    train_env.save(str(Path(out_dir) / "final_vecnorm.pkl"))
    return model


def main():
    total_steps = int(os.environ.get("TOTAL_STEPS", "1000000"))
    n_envs = int(os.environ.get("N_ENVS", "40"))
    h1_subset_env = os.environ.get("H1_SUBSET", "").strip()
    h1_subset = [c for c in h1_subset_env.split(",") if c] or None
    print("loading data...", flush=True)
    m1 = load_mt_ohlcv_csv(CFG.csv_path, time_col=CFG.time_col, source_tz=CFG.source_tz,
                           timestamp_is_bar_open=True, bar_duration="1min")
    feat, fc = build_multitf(m1, warmup_bars=CFG.warmup_bars, h1_subset=h1_subset)
    print(f"M5 bars: {len(feat)} {feat.index.min()} -> {feat.index.max()}", flush=True)
    print(f"features: {len(fc)} (H1+M5+tf_state) +8 pos  action: MultiDiscrete", flush=True)

    folds = make_sliding_folds(feat, train_years=CFG.sliding_train_years,
                               val_months=CFG.sliding_val_months,
                               test_months=CFG.sliding_test_months,
                               step_months=CFG.sliding_step_months,
                               embargo_bars=CFG.split_embargo_bars)
    print(f"folds: {len(folds)}", flush=True)
    if not folds:
        print("no folds; abort"); return

    # Finale model: train on the FIRST fold's train window (largest early data),
    # then validate on EVERY fold's test window (true OOS).
    # Finale model: train on a LARGE slice (first ~60% of history) so a wider
    # observation has enough data to fit; validate on the last fold's val window
    # for checkpoint selection, then replay EVERY fold's test window as OOS.
    cut = int(len(feat) * 0.6)
    tr0 = feat.iloc[:cut - len(folds[-1][1])]
    va0 = feat.iloc[cut - len(folds[-1][1]):cut]
    print(f"Finale train: {len(tr0)} bars  val {len(va0)}", flush=True)
    OUT = "/root/rl_gold/models_v5/finale"
    model = train_fold(tr0, va0, m1, fc, total_steps=total_steps, n_envs=n_envs,
                       out_dir=OUT, device="cuda")

    rows = []
    for k, (_tr, _va, te) in enumerate(folds, 1):
        mp = Path(OUT) / "best_model" / "best_model.zip"; vp = Path(OUT) / "best_model" / "best_model_vecnorm.pkl"
        if not mp.exists():
            mp, vp = Path(OUT) / "final_model.zip", Path(OUT) / "final_vecnorm.pkl"
        m = RecurrentPPO.load(str(mp), device="cpu")
        _eq, _tr2, rep = rollout(m, vp, m1, fc, te)
        rows.append(dict(fold=k, test_start=str(te.index.min().date()), test_end=str(te.index.max().date()),
                         ret=rep.get("total_return_pct"), pf=rep.get("profit_factor"),
                         winrate=rep.get("win_rate_pct"), sharpe=rep.get("sharpe_like"),
                         dd=rep.get("max_drawdown_pct"), trades=rep.get("n_trades")))
        print(f"val fold {k}: ret={rep.get('total_return_pct'):+.2f}% PF={rep.get('profit_factor'):.2f} "
              f"win={rep.get('win_rate_pct'):.1f}% DD={rep.get('max_drawdown_pct'):+.2f}%", flush=True)

    df = pd.DataFrame(rows)
    df.to_csv("/root/rl_gold/models_v5/summary.csv", index=False)
    print(df.to_string(index=False), flush=True)
    print(f"validation positive: {(df['ret'] > 0).sum()}/{len(df)}  mean={df['ret'].mean():+.2f}%  "
          f"mean PF={df['pf'].mean():.2f}")


if __name__ == "__main__":
    main()
