"""Baseline: deterministic Fibonacci rule inside the v7 env.

If a fibo setup is active -> enter in the impulse direction (SL = 1.0*ATR,
TP = 1.5R). Exit when the setup disappears or flips. Reports daily $ stats,
so we can tell whether ANY representable edge exists before blaming the RL.

Usage: python3 baseline_fibo.py [fold ...]
"""
from __future__ import annotations
import sys

sys.path.insert(0, "/root/rl_gold")
sys.path.insert(0, "/workspace/rl_gold")
sys.path.insert(0, "/root/rl_gold/Reinforcement_Trading_Part_2")
import numpy as np  # noqa: E402
import data_folds_real as D  # noqa: E402
from env_bracket_micro_v7 import MicroTradingEnv  # noqa: E402
import train_v7 as T  # noqa: E402


def make_env(dec, m1, fc):
    return MicroTradingEnv(dec, m1, fc, **T.ENV_KW)


def daily_stats(dl):
    if dl is None or dl.empty:
        return dict(days=0, mean_day=float("nan"), median_day=float("nan"),
                    pct_green=float("nan"), worst_day=float("nan"))
    p = dl["pnl"].astype(float)
    return dict(days=int(len(p)), mean_day=float(p.mean()), median_day=float(p.median()),
                pct_green=float((p > 0).mean() * 100), worst_day=float(p.min()))


def run(env, min_reaction=0.0, sl_idx=3, tp_idx=1, exit_on_flip=True, one_per_setup=True,
        invert=False):
    """Fresh-setup entry (rising edge) + reaction filter; optional hold-to-bracket."""
    obs, _ = env.reset(); done = False
    prev_has = 0.0
    entered = False
    while not done:
        row = env._current_row()
        has = float(row["fb_has_setup"]); d = int(row["fb_dir"]); rx = float(row["fb_reaction"])
        if invert:
            d = -d
        pos = env.position.direction
        want = 1 if d > 0 else (2 if d < 0 else 0)
        if has == 0:
            entered = False
        if pos == 0:
            fresh = has > 0 and prev_has == 0
            if fresh and want != 0 and rx >= min_reaction and not (one_per_setup and entered):
                a = [want, sl_idx, tp_idx]; entered = True
            else:
                a = [0, sl_idx, tp_idx]
        else:
            pos_raw = 1 if pos > 0 else 2
            if exit_on_flip and (has == 0 or want == 0 or want != pos_raw):
                a = [0, sl_idx, tp_idx]
            else:
                a = [pos_raw, sl_idx, tp_idx]
        prev_has = has
        obs, r, term, trunc, info = env.step(a); done = term or trunc
    return env.equity_curve(), env.trade_log(), env.daily_log()


def main():
    folds_arg = [int(x) for x in sys.argv[1:]] or [1, 22]
    m1, feat, fc = D.prepare(T.REAL, T.EXTRA)
    folds = D.make_folds(feat)
    configs = [
        dict(min_reaction=2.5, invert=True, exit_on_flip=False),   # FADE mode (EA default)
        dict(min_reaction=0.0, invert=True, exit_on_flip=False),
        dict(min_reaction=2.5, invert=True, exit_on_flip=True),
        dict(min_reaction=2.5, invert=True, exit_on_flip=False, sl_idx=4, tp_idx=1),
    ]
    for cfg in configs:
        print(f"\n### cfg {cfg}")
        print(f"{'fold':>4} {'ret%':>8} {'medDay':>8} {'green%':>7} {'worst':>7} {'trades':>6}")
        for k in folds_arg:
            tr, va, te = folds[k - 1]
            env = make_env(te, D.slice_m1(m1, te), fc)
            eq, tr_log, dl = run(env, **cfg)
            ret = float(eq["equity"].iloc[-1] / 100.0 - 1.0) * 100
            ds = daily_stats(dl)
            print(f"{k:>4} {ret:>+8.2f} {ds['median_day']:>+8.2f} {ds['pct_green']:>7.0f} "
                  f"{ds['worst_day']:>+7.2f} {len(tr_log):>6}", flush=True)


if __name__ == "__main__":
    main()
