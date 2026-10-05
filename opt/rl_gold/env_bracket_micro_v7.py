"""v7 micro-account environment: $100, min-lot 0.01, daily loss cap / target.

Observation = market features (N) + position state (6) + account state (5).
Action      = MultiDiscrete([3, 5, 4]) = dir {flat, long, short} x SL ATR bucket
              x TP R bucket.  The agent CANNOT size: a $100 XAUUSD account is
              always at the broker minimum (0.01 lot), so the SL bucket alone
              decides how many dollars are at risk.

Daily layer (the "$10-20/day" objective):
  - UTC day resets day_pnl / trades / loss streak
  - hard stop for the day at -DAILY_CAP (close + no new entries)
  - optional stop-at-target at +DAILY_TARGET (protect a good day)
  - terminal day reward: bonus if day_pnl >= target, penalty if <= -cap
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    import gymnasium as gym
    from gymnasium import spaces
except Exception as exc:  # pragma: no cover
    raise ImportError("Install gymnasium first: pip install gymnasium") from exc


SL_ATR = (0.3, 0.5, 0.75, 1.0, 1.5)
TP_R = (1.0, 1.5, 2.0, 3.0)


@dataclass
class Position:
    direction: int = 0
    entry_time: Optional[pd.Timestamp] = None
    entry_price: float = 0.0
    sl: float = 0.0
    tp: float = 0.0
    units: float = 0.0
    risk_cash: float = 0.0
    sl_distance: float = 0.0
    tp_r: float = 0.0
    sl_atr_mult: float = 0.0
    bars_in_trade: int = 0


class MicroTradingEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(
        self,
        decision_df: pd.DataFrame,
        m1_df: pd.DataFrame,
        feature_cols: List[str],
        sl_atr_multipliers=SL_ATR,
        tp_r_multipliers=TP_R,
        initial_equity: float = 100.0,
        contract_size: float = 100.0,
        min_lot: float = 0.01,
        spread_price: float = 0.24,
        slippage_price: float = 0.02,
        commission_per_trade: float = 0.0,
        daily_cap: float = 20.0,
        daily_target: float = 15.0,
        stop_at_target: bool = True,
        ruin_equity: float = 0.0,
        ruin_penalty: float = 5.0,
        giveback_penalty: float = 0.02,
        loss_penalty: float = 0.20,
        mtm_weight: float = 0.01,
        holding_penalty: float = 0.0,
        flat_penalty: float = 0.01,
        day_bonus: float = 1.0,
        day_cap_penalty: float = 2.0,
        max_episode_steps: Optional[int] = None,
        randomize_start: bool = False,
    ):
        super().__init__()
        self.feature_cols = list(feature_cols)
        self.decision_df = decision_df.dropna(subset=self.feature_cols + ["atr"]).copy()
        self.m1_df = m1_df.copy()
        self.sl_atr = tuple(sl_atr_multipliers)
        self.tp_r = tuple(tp_r_multipliers)
        self.initial_equity = float(initial_equity)
        self.contract = float(contract_size)
        self.min_lot = float(min_lot)
        self.units = self.min_lot * self.contract          # fixed min-lot size
        self.spread_price = float(spread_price)
        self.slippage_price = float(slippage_price)
        self.commission = float(commission_per_trade)
        self.daily_cap = float(daily_cap)
        self.daily_target = float(daily_target)
        self.stop_at_target = bool(stop_at_target)
        self.ruin_equity = float(ruin_equity)
        self.ruin_penalty = float(ruin_penalty)
        self.giveback_penalty = float(giveback_penalty)
        self.loss_penalty = float(loss_penalty)
        self.mtm_weight = float(mtm_weight)
        self.holding_penalty = float(holding_penalty)
        self.flat_penalty = float(flat_penalty)
        self.day_bonus = float(day_bonus)
        self.day_cap_penalty = float(day_cap_penalty)
        self.max_episode_steps = max_episode_steps or (len(self.decision_df) - 2)
        self.randomize_start = randomize_start

        self._m1_high = self.m1_df["High"].to_numpy(dtype=np.float64)
        self._m1_low = self.m1_df["Low"].to_numpy(dtype=np.float64)
        self._m1_index = self.m1_df.index

        self.action_space = spaces.MultiDiscrete([3, len(self.sl_atr), len(self.tp_r)])
        self.n_pos = 6
        self.n_acct = 5
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf,
            shape=(len(self.feature_cols) + self.n_pos + self.n_acct,),
            dtype=np.float32)

        self._mfe_r = 0.0
        self.reset()

    # ------------------------------------------------------------------ reset
    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        if self.randomize_start:
            headroom = max(self.max_episode_steps + 2, 2)
            max_start = max(len(self.decision_df) - headroom, 1)
            self.i = int(self.np_random.integers(0, max_start))
        else:
            self.i = 0
        self.steps = 0
        self.equity = self.initial_equity
        self.start_equity = self.initial_equity
        self.realized = 0.0
        self.position = Position()
        self.trades: List[Dict[str, Any]] = []
        self.history: List[Dict[str, Any]] = []
        self.daily: List[Dict[str, Any]] = []
        # day state
        self.day = self._current_time().date()
        self.day_start_equity = self.initial_equity
        self.day_pnl = 0.0
        self.day_trades = 0
        self.loss_streak = 0
        self.day_locked = False
        self.day_stopped = False
        self._mfe_r = 0.0
        return self._observation(), {}

    # ------------------------------------------------------------------ state
    def _current_row(self):
        return self.decision_df.iloc[self.i]

    def _current_time(self):
        return self.decision_df.index[self.i]

    def _next_time(self):
        return self.decision_df.index[min(self.i + 1, len(self.decision_df) - 1)]

    def _position_state(self) -> np.ndarray:
        row = self._current_row()
        close = float(row["Close"]); atr = max(float(row["atr"]), 1e-12)
        p = self.position
        if p.direction == 0:
            return np.zeros(self.n_pos, dtype=np.float32)
        unreal = (close - p.entry_price) * p.units * p.direction
        cur_r = unreal / max(p.risk_cash, 1e-12)
        return np.array([
            p.direction, cur_r, min(p.bars_in_trade / 100.0, 10.0),
            ((p.tp - close) * p.direction) / atr,
            ((close - p.sl) * p.direction) / atr, p.tp_r,
        ], dtype=np.float32)

    def _account_state(self) -> np.ndarray:
        tgt = max(self.daily_target, 1e-9)
        return np.array([
            self.equity / self.initial_equity - 1.0,
            self.day_pnl / max(self.day_start_equity, 1e-9),
            min(self.day_trades / 10.0, 1.0),
            min(self.loss_streak / 5.0, 1.0),
            float(np.clip(self.day_pnl / tgt, -2.0, 2.0)),
        ], dtype=np.float32)

    def _observation(self):
        row = self._current_row()
        market = row[self.feature_cols].astype(float).to_numpy(dtype=np.float32)
        obs = np.concatenate([market, self._position_state(), self._account_state()])
        return np.nan_to_num(obs, nan=0.0, posinf=10.0, neginf=-10.0).astype(np.float32)

    # --------------------------------------------------------------- trading
    def _entry_price(self, close, direction):
        return close + direction * (self.spread_price / 2.0 + self.slippage_price)

    def _exit_price(self, price, direction):
        return price - direction * (self.spread_price / 2.0 + self.slippage_price)

    def _open_position(self, direction, sl_idx, tp_idx):
        row = self._current_row()
        close = float(row["Close"]); atr = max(float(row["atr"]), 1e-12)
        sl_mult = self.sl_atr[sl_idx]
        sl_dist = max(sl_mult * atr, 1e-8)
        tp_r = self.tp_r[tp_idx]
        entry = self._entry_price(close, direction)
        self._mfe_r = 0.0
        self.position = Position(
            direction=direction, entry_time=self._current_time(), entry_price=entry,
            sl=entry - direction * sl_dist, tp=entry + direction * tp_r * sl_dist,
            units=self.units, risk_cash=self.units * sl_dist, sl_distance=sl_dist,
            tp_r=tp_r, sl_atr_mult=sl_mult, bars_in_trade=0)

    def _close_position(self, exit_raw, exit_time, reason):
        p = self.position
        if p.direction == 0:
            return 0.0
        exit_price = self._exit_price(exit_raw, p.direction)
        pnl = (exit_price - p.entry_price) * p.units * p.direction - self.commission
        self.equity += pnl
        self.realized += pnl
        self.day_pnl += pnl
        self.trades.append(dict(
            entry_time=p.entry_time, exit_time=exit_time, direction=p.direction,
            entry_price=p.entry_price, exit_price=exit_price, sl=p.sl, tp=p.tp,
            sl_atr_mult=p.sl_atr_mult, tp_r_bracket=p.tp_r, units=p.units,
            pnl=pnl, r_mult=pnl / max(p.risk_cash, 1e-12),
            bars_in_trade=p.bars_in_trade, exit_reason=reason))
        self.position = Position()
        return pnl

    def _simulate_m1(self):
        p = self.position
        if p.direction == 0:
            return 0.0
        lo = int(self._m1_index.searchsorted(self._current_time(), side="right"))
        hi = int(self._m1_index.searchsorted(self._next_time(), side="right"))
        realized = 0.0
        for idx in range(lo, hi):
            p = self.position
            if p.direction == 0:
                break
            high = self._m1_high[idx]; low = self._m1_low[idx]
            sl_hit = low <= p.sl if p.direction == 1 else high >= p.sl
            tp_hit = high >= p.tp if p.direction == 1 else low <= p.tp
            if sl_hit:
                realized += self._close_position(p.sl, self._m1_index[idx], "SL"); break
            if tp_hit:
                realized += self._close_position(p.tp, self._m1_index[idx], "TP"); break
        return realized

    # ------------------------------------------------------------------ step
    def step(self, action):
        action = np.asarray(action, dtype=int)
        d_raw, sl_idx, tp_idx = int(action[0]), int(action[1]), int(action[2])
        desired = {0: 0, 1: 1, 2: -1}[d_raw]

        prev_equity = self.equity
        reward_unit = max(prev_equity * 0.01, 1e-9)   # 1% of equity per reward unit
        row = self._current_row()
        close = float(row["Close"])

        # daily lock: no new risk once the day is done
        if self.day_locked or self.day_stopped:
            desired = 0 if self.position.direction == 0 else desired  # allow exit only

        # explicit close / flip
        can_enter = not (self.day_locked or self.day_stopped) and self.equity > self.ruin_equity
        if self.position.direction != 0:
            cur_dir = self.position.direction
            if desired == 0:
                self._close_position(close, self._current_time(), "flat_close")
            elif desired != cur_dir:
                self._close_position(close, self._current_time(), "flip_close")
                if can_enter:
                    self._open_position(desired, sl_idx, tp_idx)
                    self.day_trades += 1
        if self.position.direction == 0 and desired != 0 and can_enter:
            self._open_position(desired, sl_idx, tp_idx)
            self.day_trades += 1

        self._simulate_m1()

        if self.position.direction != 0:
            self.position.bars_in_trade += 1
        reward = (self.equity - prev_equity) / reward_unit
        realized_r = (self.equity - prev_equity) / reward_unit
        if realized_r < -0.5:
            reward += self.loss_penalty * realized_r
        if self.position.direction != 0:
            cur_close = float(row["Close"])
            unreal = (cur_close - self.position.entry_price) * self.position.units * self.position.direction
            cur_r = unreal / max(self.position.risk_cash, 1e-12)
            self._mfe_r = max(self._mfe_r, cur_r)
            reward -= self.giveback_penalty * max(0.0, self._mfe_r - cur_r)
            reward += cur_r * self.mtm_weight
            reward -= self.holding_penalty
        else:
            reward -= self.flat_penalty

        # -------- daily boundary --------
        nxt = self.i + 1
        day_ended = (nxt < len(self.decision_df) and
                     self.decision_df.index[nxt].date() != self._current_time().date())
        if day_ended:
            if self.day_pnl >= self.daily_target:
                reward += self.day_bonus
            if self.day_pnl <= -self.daily_cap:
                reward -= self.day_cap_penalty
            self.daily.append(dict(
                date=str(self._current_time().date()), pnl=round(self.day_pnl, 2),
                equity=round(self.equity, 2), trades=self.day_trades,
                win=int(self.day_pnl > 0)))
            nd = self.decision_df.index[nxt].date()
            self.day = nd
            self.day_start_equity = self.equity
            self.day_pnl = 0.0
            self.day_trades = 0
            self.loss_streak = 0
            self.day_locked = False
            self.day_stopped = False

        # re-evaluate daily lock/stop after the move
        if self.day_pnl <= -self.daily_cap and not self.day_locked:
            self.day_locked = True
            if self.position.direction != 0:
                self._close_position(close, self._current_time(), "daily_cap")
        if self.stop_at_target and self.day_pnl >= self.daily_target and not self.day_stopped:
            self.day_stopped = True
            if self.position.direction != 0:
                self._close_position(close, self._current_time(), "daily_target")

        # ruin: account wiped out -> close, penalise, stop the episode
        ruined = self.equity <= self.ruin_equity
        if ruined and self.position.direction != 0:
            self._close_position(close, self._current_time(), "ruin")
        if ruined:
            reward -= self.ruin_penalty

        self.history.append(dict(time=self._current_time(), equity=self.equity,
                                 realized_pnl=self.realized, position=self.position.direction,
                                 close=close, reward=float(reward), day_pnl=self.day_pnl))

        self.i += 1
        self.steps += 1
        terminated = self.i >= len(self.decision_df) - 2 or self.equity <= self.ruin_equity
        truncated = self.steps >= self.max_episode_steps
        obs = self._observation() if not (terminated or truncated) else np.zeros(
            self.observation_space.shape, dtype=np.float32)
        info = {"equity": self.equity, "n_trades": len(self.trades), "day_pnl": self.day_pnl}
        return obs, float(reward), terminated, truncated, info

    # --------------------------------------------------------------- reports
    def equity_curve(self):
        if not self.history:
            return pd.DataFrame(columns=["time", "equity", "realized_pnl", "position", "close", "reward"])
        return pd.DataFrame(self.history).set_index("time")

    def trade_log(self):
        return pd.DataFrame(self.trades)

    def daily_log(self):
        return pd.DataFrame(self.daily)
