"""Collect every FADE-rule trade across all walk-forward TEST folds, with the
market features at entry, then rank candidate regime filters by expectancy.

FADE = EA default (InpFadeMode): trade AGAINST the impulse direction.
Entry: fresh setup + reaction >= MIN_REACTION, hold to bracket (SL/TP).
"""
from __future__ import annotations
import sys

sys.path.insert(0, "/root/rl_gold")
sys.path.insert(0, "/workspace/rl_gold")
sys.path.insert(0, "/root/rl_gold/Reinforcement_Trading_Part_2")
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import data_folds_real as D  # noqa: E402
from env_bracket_micro_v7 import MicroTradingEnv  # noqa: E402
import train_v7 as T  # noqa: E402

MIN_REACTION = float(sys.argv[1]) if len(sys.argv) > 1 else 2.5
FOLDS = [int(x) for x in sys.argv[2:]] or list(range(1, 23))
CAND = ["fb_atr_ratio", "fb_efficiency", "fb_range_atr", "fb_age", "fb_touches",
        "fb_reaction", "close_ema50_atr_h1", "close_ema200_atr_h1", "atr_close",
        "atr_fast_slow", "bb_width_close", "roc20_atr", "session_london",
        "session_newyork", "session_london_ny_overlap", "atr_close_h1", "tf_h1_progress"]


def run_collect(env):
    obs, _ = env.reset(); done = False
    prev_has = 0.0; entered = False; snaps = {}
    while not done:
        row = env._current_row()
        has = float(row["fb_has_setup"]); d = int(row["fb_dir"])
        rx = float(row["fb_reaction"])
        want = 1 if (-d) > 0 else (2 if (-d) < 0 else 0)   # FADE (inverted)
        pos = env.position.direction
        if has == 0:
            entered = False
        if pos == 0:
            fresh = has > 0 and prev_has == 0
            if fresh and want != 0 and rx >= MIN_REACTION and not entered:
                a = [want, 3, 1]; entered = True
                snaps[str(env._current_time())] = {c: float(row[c]) for c in CAND}
            else:
                a = [0, 3, 1]
        else:
            a = [1 if pos > 0 else 2, 3, 1]
        prev_has = has
        obs, r, term, trunc, info = env.step(a); done = term or trunc
    tr = env.trade_log()
    if len(tr):
        tr = tr.copy(); tr["entry_time"] = tr["entry_time"].astype(str)
        tr["fold"] = FOLD_IDX
        for c in CAND:
            tr[c] = tr["entry_time"].map(lambda t: snaps.get(t, {}).get(c, np.nan))
    return tr


m1, feat, fc = D.prepare(T.REAL, T.EXTRA)
folds = D.make_folds(feat)
allrows = []
for k in FOLDS:
    tr, va, te = folds[k - 1]
    FOLD_IDX = k
    env = MicroTradingEnv(te, D.slice_m1(m1, te), fc, **T.ENV_KW)
    allrows.append(run_collect(env))
tr = pd.concat(allrows, ignore_index=True) if allrows else pd.DataFrame()
print("total trades", len(tr))
if len(tr):
    tr.to_csv("/root/rl_gold/fade_trades.csv", index=False)
    print("overall mean R %.3f  winrate %.1f%%" % (tr["r_mult"].mean(), (tr["pnl"] > 0).mean() * 100))
    print("\nby fold:")
    print(tr.groupby("fold")["r_mult"].agg(["count", "mean"]).round(3).to_string())
    print("\n--- expectancy by feature tercile (mean R / n / winrate) ---")
    for c in CAND:
        v = tr[c]
        if v.isna().all():
            continue
        try:
            q = pd.qcut(v, 3, duplicates="drop")
        except Exception:
            continue
        g = tr.groupby(q)["r_mult"].agg(["mean", "count"])
        wr = tr.groupby(q)["pnl"].apply(lambda s: (s > 0).mean() * 100)
        print(f"\n{c}:")
        for idx in g.index:
            print(f"  {str(idx):<28} meanR={g.loc[idx,'mean']:+.3f} n={int(g.loc[idx,'count'])} win={wr.loc[idx]:.0f}%")
