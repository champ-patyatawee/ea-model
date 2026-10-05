"""v5 environment: multi-timeframe observation (H1 context + M5 decision).

Structurally identical to v4 (MultiDiscrete([3,8,8,6,2]) — the model controls
direction, SL, TP, size and exit), except the decision frame already carries the
merged H1 + M5 + tf_state columns, so the observation is wider. Nothing else in
the step logic changes.
"""
from __future__ import annotations

from env_bracket_v4 import BracketTradingEnvV4


class BracketTradingEnvV5(BracketTradingEnvV4):
    """v5 = v4 with the multi-timeframe feature frame. Kept as its own class so
    the v5 training/runner code never imports a v4 symbol by mistake."""

    pass
