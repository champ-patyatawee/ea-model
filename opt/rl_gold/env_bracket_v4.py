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


@dataclass
class Position:
    direction: int = 0  # +1 long, -1 short, 0 flat
    entry_time: Optional[pd.Timestamp] = None
    entry_price: float = 0.0
    sl: float = 0.0
    tp: float = 0.0
    units: float = 0.0
    risk_cash: float = 0.0
    sl_distance: float = 0.0
    tp_r: float = 0.0          # planned TP R-multiple (model choice, continuous)
    sl_atr_mult: float = 0.0   # planned SL ATR multiplier (model choice, continuous)
    bars_in_trade: int = 0


class BracketTradingEnvV4(gym.Env):
    """v4: the model controls EVERYTHING — direction, SL, TP, size, and exit.

    Action = Box(5), all continuous in [-1, 1] (scaled to real ranges):
        [0] direction  : < -0.33 short | > +0.33 long | between = flat/close
        [1] sl_mult_raw: scaled to [sl_min, sl_max] x ATR   (model-set stop distance)
        [2] tp_mult_raw: scaled to [tp_min, tp_max] x R     (model-set take-profit)
        [3] risk_raw   : scaled to [risk_min, risk_max]     (model-set size)
        [4] close_raw  : > close_thr => model closes the open position now

    One step = one decision bar (M5). TP/SL detection is still simulated on the
    M1 execution bars inside the interval, so a broker stop-out remains realistic.
    """

    metadata = {"render_modes": []}

    def __init__(
        self,
        decision_df: pd.DataFrame,
        m1_df: pd.DataFrame,
        feature_cols: List[str],
        sl_min: float = 0.5,
        sl_max: float = 3.0,
        tp_min: float = 0.5,
        tp_max: float = 5.0,
        risk_min: float = 0.001,
        risk_max: float = 0.02,
        close_thr: float = 0.5,
        initial_equity: float = 10_000.0,
        spread_price: float = 0.20,
        slippage_price: float = 0.02,
        commission_per_trade: float = 0.0,
        holding_penalty: float = 0.0,
        reward_mtm_weight: float = 0.01,
        giveback_penalty: float = 0.10,
        loss_penalty: float = 0.20,
        close_bonus: float = 0.05,
        max_episode_steps: Optional[int] = None,
        randomize_start: bool = False,
    ):
        super().__init__()
        self.decision_df = decision_df.dropna(subset=feature_cols + ["atr"]).copy()
        self.m1_df = m1_df.copy()
        self.feature_cols = list(feature_cols)
        self.sl_min, self.sl_max = float(sl_min), float(sl_max)
        self.tp_min, self.tp_max = float(tp_min), float(tp_max)
        self.risk_min, self.risk_max = float(risk_min), float(risk_max)
        self.close_thr = float(close_thr)
        self.initial_equity = float(initial_equity)
        self.spread_price = float(spread_price)
        self.slippage_price = float(slippage_price)
        self.commission_per_trade = float(commission_per_trade)
        self.holding_penalty = float(holding_penalty)
        self.reward_mtm_weight = float(reward_mtm_weight)
        self.giveback_penalty = float(giveback_penalty)
        self.loss_penalty = float(loss_penalty)
        self.close_bonus = float(close_bonus)
        self._mfe_r = 0.0
        self.max_episode_steps = max_episode_steps or (len(self.decision_df) - 2)
        self.randomize_start = randomize_start

        self._m1_high = self.m1_df["High"].to_numpy(dtype=np.float64)
        self._m1_low = self.m1_df["Low"].to_numpy(dtype=np.float64)
        self._m1_index = self.m1_df.index

        # Action = MultiDiscrete: discrete direction + fine-grained buckets for
        # SL / TP / risk / close.  (RecurrentPPO does not accept a Dict space, so
        # everything is bucketed.)  Direction stays discrete to avoid the
        # continuous "no-trade" stall.
        #   [0] direction : 0 flat, 1 long, 2 short
        #   [1] sl bucket : 8 steps across [sl_min, sl_max]
        #   [2] tp bucket : 8 steps across [tp_min, tp_max]
        #   [3] risk bucket: 6 steps across [risk_min, risk_max]
        #   [4] close     : 0 hold, 1 close now
        self.n_sl_buckets = 8
        self.n_tp_buckets = 8
        self.n_risk_buckets = 6
        self.action_space = spaces.MultiDiscrete(
            [3, self.n_sl_buckets, self.n_tp_buckets, self.n_risk_buckets, 2])

        # Market features + position state (now 8: added cur_r, peak_r).
        self.n_pos_features = 8
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(len(self.feature_cols) + self.n_pos_features,),
            dtype=np.float32,
        )
        self.reset()

    # ---------------------------------------------------------------- decode
    def _bucket(self, idx: int, n: int, lo: float, hi: float) -> float:
        """map bucket index in [0,n-1] to midpoint of its slice in [lo,hi]."""
        i = int(np.clip(idx, 0, n - 1))
        return lo + (i + 0.5) / n * (hi - lo)

    def _decode(self, action) -> Tuple[int, float, float, float, bool]:
        a = np.asarray(action, dtype=np.int64).reshape(-1)
        d = int(np.clip(a[0], 0, 2))
        direction = {0: 0, 1: 1, 2: -1}[d]
        sl_mult = self._bucket(a[1], self.n_sl_buckets, self.sl_min, self.sl_max)
        tp_mult = self._bucket(a[2], self.n_tp_buckets, self.tp_min, self.tp_max)
        risk_frac = self._bucket(a[3], self.n_risk_buckets, self.risk_min, self.risk_max)
        close_now = bool(int(np.clip(a[4], 0, 1)) == 1)
        return direction, sl_mult, tp_mult, risk_frac, close_now

    # ----------------------------------------------------------------- state
    def reset(self, *, seed: Optional[int] = None, options: Optional[dict] = None):
        super().reset(seed=seed)
        if self.randomize_start:
            headroom = max(self.max_episode_steps + 2, 2)
            max_start = max(len(self.decision_df) - headroom, 1)
            self.i = int(self.np_random.integers(0, max_start))
        else:
            self.i = 0
        self.steps = 0
        self.equity = self.initial_equity
        self.realized_pnl = 0.0
        self.position = Position()
        self.trades: List[Dict[str, Any]] = []
        self.history: List[Dict[str, Any]] = []
        obs = self._observation()
        return obs, {}

    def _current_row(self):
        return self.decision_df.iloc[self.i]

    def _current_time(self):
        return self.decision_df.index[self.i]

    def _next_time(self):
        return self.decision_df.index[min(self.i + 1, len(self.decision_df) - 1)]

    def _position_state_features(self) -> np.ndarray:
        row = self._current_row()
        close = float(row["Close"])
        atr = max(float(row["atr"]), 1e-12)
        p = self.position
        if p.direction == 0:
            return np.array([0, 0, 0, 0, 0, 0, 0, 0], dtype=np.float32)
        unrealized = (close - p.entry_price) * p.units * p.direction
        cur_r = unrealized / max(p.risk_cash, 1e-12)
        dist_tp_atr = ((p.tp - close) * p.direction) / atr
        dist_sl_atr = ((close - p.sl) * p.direction) / atr
        return np.array([
            p.direction,
            cur_r,
            min(p.bars_in_trade / 100.0, 10.0),
            dist_tp_atr,
            dist_sl_atr,
            p.tp_r,
            self._mfe_r,
            p.sl_atr_mult,
        ], dtype=np.float32)

    def _observation(self):
        row = self._current_row()
        market = row[self.feature_cols].astype(float).to_numpy(dtype=np.float32)
        pos = self._position_state_features()
        obs = np.concatenate([market, pos]).astype(np.float32)
        obs = np.nan_to_num(obs, nan=0.0, posinf=10.0, neginf=-10.0)
        return obs

    def _entry_price(self, close: float, direction: int) -> float:
        return close + direction * (self.spread_price / 2.0 + self.slippage_price)

    def _exit_price(self, price: float, direction: int) -> float:
        return price - direction * (self.spread_price / 2.0 + self.slippage_price)

    def _open_position(self, direction: int, sl_mult: float, tp_r: float, risk_frac: float):
        row = self._current_row()
        close = float(row["Close"])
        atr = max(float(row["atr"]), 1e-12)
        sl_dist = max(sl_mult * atr, 1e-8)
        entry = self._entry_price(close, direction)
        sl = entry - direction * sl_dist
        tp = entry + direction * tp_r * sl_dist
        risk_cash = max(self.equity * risk_frac, 1e-8)
        units = risk_cash / sl_dist

        self._mfe_r = 0.0
        self.position = Position(
            direction=direction,
            entry_time=self._current_time(),
            entry_price=entry,
            sl=sl,
            tp=tp,
            units=units,
            risk_cash=risk_cash,
            sl_distance=sl_dist,
            tp_r=tp_r,
            sl_atr_mult=sl_mult,
            bars_in_trade=0,
        )

    def _close_position(self, exit_price_raw: float, exit_time: pd.Timestamp, reason: str) -> float:
        p = self.position
        if p.direction == 0:
            return 0.0
        exit_price = self._exit_price(exit_price_raw, p.direction)
        pnl = (exit_price - p.entry_price) * p.units * p.direction - self.commission_per_trade
        self.equity += pnl
        self.realized_pnl += pnl
        r_mult = pnl / max(p.risk_cash, 1e-12)
        self.trades.append({
            "entry_time": p.entry_time,
            "exit_time": exit_time,
            "direction": p.direction,
            "entry_price": p.entry_price,
            "exit_price": exit_price,
            "sl": p.sl,
            "tp": p.tp,
            "sl_atr_mult": p.sl_atr_mult,
            "tp_r_bracket": p.tp_r,
            "units": p.units,
            "pnl": pnl,
            "r_mult": r_mult,
            "bars_in_trade": p.bars_in_trade,
            "exit_reason": reason,
        })
        self.position = Position()
        return pnl

    def _simulate_m1_until_next_decision(self) -> float:
        p = self.position
        if p.direction == 0:
            return 0.0
        start = self._current_time()
        end = self._next_time()
        lo = int(self._m1_index.searchsorted(start, side="right"))
        hi = int(self._m1_index.searchsorted(end, side="right"))
        realized = 0.0
        for idx in range(lo, hi):
            high = self._m1_high[idx]
            low = self._m1_low[idx]
            p = self.position
            if p.direction == 0:
                break
            if p.direction == 1:
                sl_hit = low <= p.sl
                tp_hit = high >= p.tp
            else:
                sl_hit = high >= p.sl
                tp_hit = low <= p.tp
            if sl_hit:
                realized += self._close_position(p.sl, self._m1_index[idx], "SL")
                break
            if tp_hit:
                realized += self._close_position(p.tp, self._m1_index[idx], "TP")
                break
        return realized

    def step(self, action):
        direction, sl_mult, tp_r, risk_frac, close_now = self._decode(action)
        desired_direction = direction

        prev_equity = self.equity
        reward_risk_unit = max(prev_equity * 0.005, 1e-12)  # fixed scale for reward
        row = self._current_row()
        close = float(row["Close"])

        # model-driven close: if it wants out and we hold, close now
        close_reward_bonus = 0.0
        if self.position.direction != 0 and close_now:
            if self._mfe_r > 0:
                close_reward_bonus = self.close_bonus * min(self._mfe_r, 3.0)
            self._close_position(close, self._current_time(), "model_close")
            desired_direction = 0

        # explicit flat/flip
        if self.position.direction != 0:
            current_dir = self.position.direction
            if desired_direction == 0:
                self._close_position(close, self._current_time(), "manual_close")
            elif desired_direction != current_dir:
                self._close_position(close, self._current_time(), "flip_close")
                self._open_position(desired_direction, sl_mult, tp_r, risk_frac)

        if self.position.direction == 0 and desired_direction != 0:
            self._open_position(desired_direction, sl_mult, tp_r, risk_frac)

        self._simulate_m1_until_next_decision()

        if self.position.direction != 0:
            self.position.bars_in_trade += 1
            current_close = float(self.decision_df.iloc[self.i]["Close"])
            unrealized = (current_close - self.position.entry_price) * self.position.units * self.position.direction
        else:
            unrealized = 0.0

        reward = (self.equity - prev_equity) / reward_risk_unit
        realized_r = reward
        if realized_r < -0.5:
            reward += self.loss_penalty * realized_r
        if self.position.direction != 0:
            cur_r = unrealized / max(self.position.risk_cash, 1e-12)
            if cur_r > self._mfe_r:
                self._mfe_r = cur_r
            giveback = max(0.0, self._mfe_r - cur_r)
            reward -= self.giveback_penalty * giveback
            reward += cur_r * self.reward_mtm_weight
            reward -= self.holding_penalty
        reward += close_reward_bonus

        self.history.append({
            "time": self._current_time(),
            "equity": self.equity,
            "realized_pnl": self.realized_pnl,
            "position": self.position.direction,
            "close": close,
            "reward": reward,
        })

        self.i += 1
        self.steps += 1
        terminated = self.i >= len(self.decision_df) - 2
        truncated = self.steps >= self.max_episode_steps
        obs = self._observation() if not (terminated or truncated) else np.zeros(self.observation_space.shape, dtype=np.float32)
        info = {"equity": self.equity, "n_trades": len(self.trades)}
        return obs, float(reward), terminated, truncated, info

    def equity_curve(self) -> pd.DataFrame:
        if not self.history:
            return pd.DataFrame(columns=["time", "equity", "realized_pnl", "position", "close", "reward"])
        return pd.DataFrame(self.history).set_index("time")

    def trade_log(self) -> pd.DataFrame:
        return pd.DataFrame(self.trades)
