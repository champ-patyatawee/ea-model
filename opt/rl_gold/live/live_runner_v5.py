"""Live demo runner for the v5 model (H1 context + M5 decision).

v5 observation = merged M5 frame carrying M5 features + a small H1 subset +
tf_state, then + 8 position-state floats. Actions are MultiDiscrete([3,8,8,6,2])
(the model controls direction, SL, TP, size and exit).
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

sys.path.insert(0, "/work/rl_gold")
sys.path.insert(0, "/work/rl_gold/export_v3/RL_base")

from config import CFG                      # noqa: E402
CFG.time_col = "time_utc"; CFG.source_tz = "UTC"; CFG.timestamp_is_bar_open = True
CFG.execution_timeframe = "1min"; CFG.decision_timeframe = "M5"
CFG.spread_price = 0.30; CFG.slippage_price = 0.02; CFG.commission_per_trade = 0.0
CFG.warmup_bars = 500

from features_multitf import build_multitf   # noqa: E402
from env_bracket_v5 import BracketTradingEnvV5  # noqa: E402
from env_bracket_v4 import Position             # noqa: E402
from sb3_contrib import RecurrentPPO        # noqa: E402
from mt5_bridge import MT5                  # noqa: E402

MAGIC = int(os.environ.get("MAGIC", "860003"))


def _df_from_rates(rates):
    if not rates:
        return pd.DataFrame()
    df = pd.DataFrame(rates, columns=["time", "open", "high", "low", "close", "volume"])
    df["dt"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df = df.set_index("dt").sort_index()
    return df.rename(columns={"open": "Open", "high": "High", "low": "Low",
                              "close": "Close", "volume": "Volume"})[
        ["Open", "High", "Low", "Close", "Volume"]]


class RunnerV5:
    def __init__(self, model_path, vecnorm_path, host, port, symbol, dry_run,
                 log_path, max_risk_pct=20.0):
        import pickle
        self.bridge = MT5(host, port)
        self.symbol = symbol
        self.dry = dry_run
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.model = RecurrentPPO.load(model_path, device="cpu")
        with open(vecnorm_path, "rb") as f:
            vn = pickle.load(f)
        self.obs_rms = vn.obs_rms
        self.max_risk_pct = float(max_risk_pct)
        self.si = self.bridge.symbol_info(symbol)
        self.contract = float(self.si["trade_contract_size"])
        self.vol_min = float(self.si["volume_min"])
        self.vol_step = float(self.si["volume_step"])
        self.daily_start_equity = None
        self.daily_cap_hit = False

    def log(self, rec: dict):
        rec["ts"] = datetime.now(timezone.utc).isoformat()
        line = json.dumps(rec, default=str)
        with open(self.log_path, "a") as f:
            f.write(line + "\n")
        print(line, flush=True)

    def units_to_lot(self, units: float) -> float:
        lot = round((units / self.contract) / self.vol_step) * self.vol_step
        return max(self.vol_min, lot)

    def current_position(self):
        ps = self.bridge.positions(self.symbol, MAGIC)
        return ps[0] if ps else None

    def build_env(self, m1_df, live_pos):
        dec, fc = build_multitf(m1_df, warmup_bars=CFG.warmup_bars)
        env = BracketTradingEnvV5(dec, m1_df, fc, initial_equity=CFG.initial_equity,
                                  spread_price=CFG.spread_price, slippage_price=CFG.slippage_price,
                                  commission_per_trade=CFG.commission_per_trade)
        env.i = len(env.decision_df) - 1
        if live_pos is not None:
            row = env._current_row()
            atr = max(float(row["atr"]), 1e-12)
            sl_mult = abs(live_pos["price_open"] - live_pos["sl"]) / atr if live_pos["sl"] else 1.5
            env.position = Position(
                direction=live_pos["dir"], entry_time=env._current_time(),
                entry_price=live_pos["price_open"], sl=live_pos["sl"], tp=live_pos["tp"],
                units=live_pos["volume"] * self.contract,
                risk_cash=env.equity * 0.005,
                sl_distance=abs(live_pos["price_open"] - live_pos["sl"]) or atr,
                tp_r=1.5, sl_atr_mult=sl_mult, bars_in_trade=0)
        return env

    def predict(self, env):
        raw = env._observation()
        obs = np.clip((raw - self.obs_rms.mean) / np.sqrt(self.obs_rms.var + 1e-8), -10.0, 10.0).astype(np.float32)
        action, _ = self.model.predict(obs, state=None, episode_start=np.array([True]), deterministic=True)
        return env._decode(np.asarray(action).ravel())

    def run_once(self):
        acct = self.bridge.account()
        eq = acct.get("equity", 0.0)
        if self.daily_start_equity is None:
            self.daily_start_equity = eq
        if eq - self.daily_start_equity <= -0.10 * self.daily_start_equity:
            self.daily_cap_hit = True
        if self.daily_cap_hit:
            self.log({"event": "daily_cap_hit", "eq": eq, "action": "halt"}); return

        si = self.bridge.symbol_info(self.symbol)
        if float(si["spread"]) > float(os.environ.get("MAX_SPREAD_POINTS", "800")):
            self.log({"event": "spread_guard", "spread": si["spread"], "action": "skip"}); return

        m1_levels = int(os.environ.get("M1_LEVELS", "60000"))
        m1 = _df_from_rates(self.bridge.fetch_m1(self.symbol, m1_levels))
        env = self.build_env(m1, self.current_position())
        direction, sl_mult, tp_r, risk_frac, close_now = self.predict(env)
        desired = direction

        row = env._current_row()
        atr = max(float(row["atr"]), 1e-12)
        close = float(row["Close"])
        live = self.current_position()
        rec = {"event": "decision", "eq": eq, "close": close, "atr": atr, "desired": desired,
               "sl_mult": round(sl_mult, 2), "tp_r": round(tp_r, 2),
               "risk_frac": round(risk_frac, 4), "close_now": close_now, "live_pos": live}

        if live is not None:
            if close_now or desired == 0 or desired != live["dir"]:
                if not self.dry:
                    rec["result"] = self.bridge.close_position(live["ticket"], self.symbol, live["dir"], live["volume"], MAGIC)
                rec["action"] = "model_close" if close_now else ("manual_close" if desired == 0 else "flip_close")
                self.log(rec)
                if desired == 0 or close_now:
                    return
            else:
                sl_dist = max(sl_mult * atr, 1e-8)
                new_sl = close - live["dir"] * sl_dist
                new_tp = close + live["dir"] * tp_r * sl_dist
                if abs((live["sl"] or 0) - new_sl) > 0.05 or abs((live["tp"] or 0) - new_tp) > 0.05:
                    rec.update({"action": "modify", "new_sl": new_sl, "new_tp": new_tp})
                    if self.dry:
                        rec["action"] = "would_modify"
                    else:
                        rec["result"] = self.bridge.modify_position(live["ticket"], new_sl, new_tp)
                else:
                    rec["action"] = "hold"
                self.log(rec)
                return

        if desired == 0:
            rec["action"] = "stay_flat"; self.log(rec); return

        sl_dist = max(sl_mult * atr, 1e-8)
        units = max(eq * risk_frac, 1e-8) / sl_dist
        lot = self.units_to_lot(units)
        risk_actual = lot * self.contract * sl_dist
        risk_pct = 100.0 * risk_actual / eq if eq else 999.0
        entry = close + desired * (CFG.spread_price / 2.0 + CFG.slippage_price)
        sl = entry - desired * sl_dist
        tp = entry + desired * tp_r * sl_dist
        rec.update({"action": "entry", "lot": lot, "units": round(units, 3),
                    "risk_usd": round(risk_actual, 2), "risk_pct": round(risk_pct, 2),
                    "sl": sl, "tp": tp})
        if risk_pct > self.max_risk_pct:
            rec["action"] = "risk_cap_skip"; rec["cap_pct"] = self.max_risk_pct; self.log(rec); return
        if self.dry:
            rec["action"] = "would_enter"; self.log(rec); return
        rec["result"] = self.bridge.market_order(self.symbol, desired, lot, sl, tp, MAGIC)
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
    ap.add_argument("--log", default="/work/rl_gold/live/v5_decisions.jsonl")
    ap.add_argument("--max-risk-pct", type=float, default=20.0)
    args = ap.parse_args()

    r = RunnerV5(args.model, args.vecnorm, args.host, args.port, args.symbol,
                 args.dry_run, args.log, max_risk_pct=args.max_risk_pct)
    r.log({"event": "start", "dry": args.dry_run, "symbol": args.symbol, "model": args.model,
           "acct": r.bridge.account(), "si": r.si})

    if args.loop:
        while True:
            try:
                r.run_once()
            except Exception as e:
                r.log({"event": "error", "err": repr(e)})
                try:
                    r.bridge.reconnect(); r.log({"event": "reconnected"})
                except Exception as e2:
                    r.log({"event": "reconnect_failed", "err": repr(e2)})
            time.sleep(int(os.environ.get("POLL_SECONDS", "60")))
    else:
        r.run_once()


if __name__ == "__main__":
    main()
