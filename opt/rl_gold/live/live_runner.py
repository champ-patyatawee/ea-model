"""Live demo runner for the RL-Gold v3 model on MT5.

Design
------
Every H1 bar close:
  1. fetch the last N H1 + M1 bars from MT5
  2. build the exact same feature frame used at training time
  3. rebuild a BracketTradingEnv on that window, place the cursor at the last
     bar, and inject the *real* currently-open MT5 position (if any)
  4. model.predict(env._observation()) -> (direction, sl_idx, tp_idx)
  5. translate to an MT5 order (lot from risk_fraction, SL/TP from ATR) and send

Guards: one position at a time, min volume 0.01, spread guard, daily loss cap,
dry-run mode, and a full JSONL decision log.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

RL = "/work/rl_gold/export_v3/RL_base"
sys.path.insert(0, "/work/rl_gold/export_v3")
sys.path.insert(0, RL)

from config import CFG                      # noqa: E402
CFG.time_col = "time_utc"; CFG.source_tz = "UTC"; CFG.timestamp_is_bar_open = True
CFG.execution_timeframe = "1min"; CFG.decision_timeframe = "H1"

from features import prepare_feature_frame  # noqa: E402
from env_bracket import BracketTradingEnv, Position  # noqa: E402
from sb3_contrib import RecurrentPPO        # noqa: E402
from mt5_bridge import MT5                  # noqa: E402

SL_ATR = (1.0, 1.5, 2.0)
TP_R = (1.0, 1.5, 2.0, 3.0)

# position tags kept in env Position so observation matches training
MAGIC = int(os.environ.get("MAGIC", "860001"))


def _df_from_rates(rates):
    if not rates:
        return pd.DataFrame()
    df = pd.DataFrame(rates, columns=["time", "open", "high", "low", "close", "volume"])
    df["dt"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df = df.set_index("dt").sort_index()
    return df.rename(columns={"open": "Open", "high": "High", "low": "Low",
                              "close": "Close", "volume": "Volume"})[
        ["Open", "High", "Low", "Close", "Volume"]]


def build_state(m1_df: pd.DataFrame, n_h1: int, feature_cols):
    """Resample M1 -> H1, add features, return (decision_df, m1_df, feature_cols)."""
    dec = m1_df.resample(CFG.pandas_tf, label="right", closed="right").agg({
        "Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum",
    }).dropna(subset=["Open", "High", "Low", "Close"])
    feat, fc = prepare_feature_frame(dec, warmup_bars=CFG.warmup_bars)
    return feat, m1_df, fc


class Runner:
    def __init__(self, model_path, vecnorm_path, host, port, symbol, dry_run,
                 log_path, risk_fraction=None, max_risk_pct=20.0, extra_folds=None):
        import pickle
        self.bridge = MT5(host, port)
        self.symbol = symbol
        self.dry = dry_run
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        # Ensemble: primary model + optional extra folds. Each is (model, obs_rms).
        self.members = []
        self.model = RecurrentPPO.load(model_path, device="cpu")
        with open(vecnorm_path, "rb") as f:
            vn = pickle.load(f)
        self.obs_rms = vn.obs_rms
        self.members.append((self.model, self.obs_rms))
        for mp, vp in (extra_folds or []):
            m = RecurrentPPO.load(mp, device="cpu")
            with open(vp, "rb") as f:
                ov = pickle.load(f)
            self.members.append((m, ov.obs_rms))
        self.max_risk_pct = float(max_risk_pct)  # skip an entry if a single trade risks more than this % of equity
        self.risk_fraction = risk_fraction if risk_fraction is not None else CFG.risk_fraction
        self.si = self.bridge.symbol_info(symbol)
        self.contract = float(self.si["trade_contract_size"])
        self.vol_min = float(self.si["volume_min"])
        self.vol_step = float(self.si["volume_step"])
        self.digits = int(self.si["digits"])
        self.daily_start_equity = None
        self.daily_cap_hit = False

    # ------------------------------------------------------------------ log
    def log(self, rec: dict):
        rec["ts"] = datetime.now(timezone.utc).isoformat()
        with open(self.log_path, "a") as f:
            f.write(json.dumps(rec) + "\n")
        print(json.dumps(rec), flush=True)

    # -------------------------------------------------------------- sizing
    def units_to_lot(self, units: float) -> float:
        lot = units / self.contract
        lot = round(lot / self.vol_step) * self.vol_step
        return max(self.vol_min, lot)

    # ---------------------------------------------------------------- state
    def current_position(self):
        ps = self.bridge.positions(self.symbol, MAGIC)
        return ps[0] if ps else None

    def build_env(self, m1_df, live_pos):
        dec, m1d, fc = build_state(m1_df, len(m1_df), None)
        env = BracketTradingEnv(
            dec, m1d, fc, sl_atr_multipliers=SL_ATR, tp_r_multipliers=TP_R,
            initial_equity=CFG.initial_equity, risk_fraction=self.risk_fraction,
            spread_price=CFG.spread_price, slippage_price=CFG.slippage_price,
            commission_per_trade=CFG.commission_per_trade,
            holding_penalty=CFG.holding_penalty, reward_mtm_weight=CFG.reward_mtm_weight,
            giveback_penalty=0.02, loss_penalty=0.20)
        env.i = len(env.decision_df) - 1
        if live_pos is not None:
            row = env._current_row()
            atr = max(float(row["atr"]), 1e-12)
            sl_mult = abs(live_pos["price_open"] - live_pos["sl"]) / atr if live_pos["sl"] else 1.5
            sl_idx = int(np.argmin([abs(m - sl_mult) for m in SL_ATR]))
            env.position = Position(
                direction=live_pos["dir"], entry_time=env._current_time(),
                entry_price=live_pos["price_open"], sl=live_pos["sl"], tp=live_pos["tp"],
                units=live_pos["volume"] * self.contract,
                risk_cash=env.equity * self.risk_fraction,
                sl_distance=abs(live_pos["price_open"] - live_pos["sl"]) or atr,
                tp_r=TP_R[1], sl_atr_mult=SL_ATR[sl_idx], bars_in_trade=0)
        return env

    def _norm(self, obs, obs_rms):
        obs_n = (obs - obs_rms.mean) / np.sqrt(obs_rms.var + 1e-8)
        return np.clip(obs_n, -10.0, 10.0).astype(np.float32)

    def predict_ensemble(self, env):
        """Majority vote over members for direction; median sl_idx/tp_idx on consensus."""
        raw = env._observation()
        votes = []
        for model, obs_rms in self.members:
            a, _ = model.predict(self._norm(raw, obs_rms), state=None,
                                 episode_start=np.array([True]), deterministic=True)
            votes.append((int(a[0]), int(a[1]), int(a[2])))
        dirs = [v[0] for v in votes]
        # majority direction (0/1/2)
        uniq, counts = np.unique(dirs, return_counts=True)
        direction = int(uniq[int(np.argmax(counts))])
        agree = int(np.max(counts))
        # only act on a real consensus (>= half of members agree)
        if agree < (len(votes) + 1) // 2:
            direction = 0
        sl_idx = int(np.median([v[1] for v in votes if v[0] == direction])) if direction else 1
        tp_idx = int(np.median([v[2] for v in votes if v[0] == direction])) if direction else 1
        return direction, sl_idx, tp_idx, votes

    # position tags kept in env Position so observation matches training
    # (module-level MAGIC)

    # ----------------------------------------------------------------- step
    def run_once(self):
        acct = self.bridge.account()
        eq = acct.get("equity", 0.0)
        if self.daily_start_equity is None:
            self.daily_start_equity = eq
        day_pnl = eq - self.daily_start_equity
        if day_pnl <= -0.10 * self.daily_start_equity:
            self.daily_cap_hit = True
        if self.daily_cap_hit:
            self.log({"event": "daily_cap_hit", "eq": eq, "day_pnl": day_pnl,
                      "action": "halt"})
            return

        # spread guard
        si = self.bridge.symbol_info(self.symbol)
        spread_pts = float(si["spread"])
        if spread_pts > float(os.environ.get("MAX_SPREAD_POINTS", "800")):
            self.log({"event": "spread_guard", "spread": spread_pts, "action": "skip"})
            return

        m1_levels = int(os.environ.get("M1_LEVELS", "40000"))
        m1 = _df_from_rates(self.bridge.fetch_m1(self.symbol, m1_levels))
        env = self.build_env(m1, self.current_position())
        direction, sl_idx, tp_idx, votes = self.predict_ensemble(env)
        desired = {0: 0, 1: 1, 2: -1}[direction]

        row = env._current_row()
        atr = max(float(row["atr"]), 1e-12)
        close = float(row["Close"])
        live = self.current_position()

        rec = {"event": "decision", "eq": eq, "close": close, "atr": atr,
               "desired": desired, "sl_idx": sl_idx, "tp_idx": tp_idx,
               "votes": votes, "live_pos": live}

        # ---- reconcile live position with the model's decision -------------
        if live is not None:
            if desired == 0 or desired != live["dir"]:
                if self.dry:
                    rec["action"] = "would_close"
                else:
                    res = self.bridge.close_position(live["ticket"], self.symbol,
                                                     live["dir"], live["volume"], MAGIC)
                    rec["action"] = "close"; rec["result"] = res
                self.log(rec)
                if desired == 0:
                    return
            else:
                # same direction: check whether SL/TP should be refreshed
                sl_mult = SL_ATR[sl_idx]; tp_r = TP_R[tp_idx]
                sl_dist = max(sl_mult * atr, 1e-8)
                new_sl = close - live["dir"] * sl_dist
                new_tp = close + live["dir"] * tp_r * sl_dist
                if abs((live["sl"] or 0) - new_sl) > 0.05 or abs((live["tp"] or 0) - new_tp) > 0.05:
                    if self.dry:
                        rec["action"] = "would_modify"; rec["new_sl"] = new_sl; rec["new_tp"] = new_tp
                    else:
                        res = self.bridge.modify_position(live["ticket"], new_sl, new_tp)
                        rec["action"] = "modify"; rec["new_sl"] = new_sl; rec["new_tp"] = new_tp
                        rec["result"] = res
                else:
                    rec["action"] = "hold"
                self.log(rec)
                return

        # ---- flat: consider an entry ---------------------------------------
        if desired == 0:
            rec["action"] = "stay_flat"
            self.log(rec)
            return

        sl_mult = SL_ATR[sl_idx]; tp_r = TP_R[tp_idx]
        sl_dist = max(sl_mult * atr, 1e-8)
        risk_cash = max(eq * self.risk_fraction, 1e-8)
        units = risk_cash / sl_dist
        lot = self.units_to_lot(units)
        risk_actual = lot * self.contract * sl_dist          # $ risked if SL hits
        risk_pct = 100.0 * risk_actual / eq if eq else 999.0
        entry = close + desired * (CFG.spread_price / 2.0 + CFG.slippage_price)
        sl = entry - desired * sl_dist
        tp = entry + desired * tp_r * sl_dist
        rec.update({"action": "entry", "lot": lot, "units": round(units, 3),
                    "risk_usd": round(risk_actual, 2), "risk_pct": round(risk_pct, 2),
                    "entry_ref": entry, "sl": sl, "tp": tp})
        if risk_pct > self.max_risk_pct:
            rec["action"] = "risk_cap_skip"
            rec["cap_pct"] = self.max_risk_pct
            self.log(rec)
            return
        if self.dry:
            rec["action"] = "would_enter"
            self.log(rec)
            return
        res = self.bridge.market_order(self.symbol, desired, lot, sl, tp, MAGIC)
        rec["result"] = res
        self.log(rec)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--vecnorm", required=True)
    ap.add_argument("--host", default=os.environ.get("MT5_HOST", "172.22.0.2"))
    ap.add_argument("--port", type=int, default=8001)
    ap.add_argument("--symbol", default="XAUUSDm")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--log", default="/work/rl_gold/live/live_decisions.jsonl")
    ap.add_argument("--risk", type=float, default=None)
    ap.add_argument("--max-risk-pct", type=float, default=20.0,
                    help="skip an entry if a single trade risks more than this %% of equity")
    ap.add_argument("--folds", default="",
                    help="comma-separated model dirs to add to the ensemble")
    args = ap.parse_args()

    def _load_pairs(dirs):
        pairs = []
        for d in dirs:
            d = d.strip()
            if not d:
                continue
            p = Path(d)
            mp = p/"best_model"/"best_model.zip"; vp = p/"best_model"/"best_model_vecnorm.pkl"
            if not mp.exists():
                mp = p/"final_model.zip"; vp = p/"final_vecnorm.pkl"
            if mp.exists():
                pairs.append((str(mp), str(vp)))
        return pairs

    extra = _load_pairs(args.folds.split(","))
    r = Runner(args.model, args.vecnorm, args.host, args.port, args.symbol,
               args.dry_run, args.log, risk_fraction=args.risk,
               max_risk_pct=args.max_risk_pct, extra_folds=extra)
    r.log({"event": "start", "dry": args.dry_run, "symbol": args.symbol,
           "model": args.model, "ensemble_size": len(r.members),
           "max_risk_pct": args.max_risk_pct,
           "acct": r.bridge.account(), "si": r.si})

    if args.loop:
        while True:
            try:
                r.run_once()
            except Exception as e:
                r.log({"event": "error", "err": repr(e)})
            time.sleep(int(os.environ.get("POLL_SECONDS", "300")))
    else:
        r.run_once()


if __name__ == "__main__":
    main()
