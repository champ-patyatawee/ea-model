# v5 — Multi-Timeframe LSTM (H1 context + M5 decision)

Status: **DESIGN / not yet trained.** This document is the build plan and
rationale. v3 is the deployed baseline; v4 is the all-control experiment.

## Why v5 exists

v3 (H1) works and is deployed. v4 (M5, model controls everything) trained fine
technically but was weaker:

| | v3 (H1) | v4 (M5) |
|---|---|---|
| positive folds | 10/10 | 7/9 |
| mean OOS return | +19.78% | +14.46% |
| mean PF | ~1.42 | 1.57 |
| win rate | ~42% | ~50% |
| trades/fold | 42–173 | 122–665 |

The diagnosis:
- **M5 alone is noisy** — the model over-fits noise and pays spread too often.
- v4's reward (giveback 0.10 + close_bonus) pushed it to trade too frequently.
- A pure single-timeframe view cannot see "the big picture" *and* "the tick" at once.

**v5's thesis:** give the model BOTH — an H1 context block (trend/regime, slow)
and an M5 decision block (momentum, fast) — so it can act every 5 minutes while
still seeing the hourly structure. This is "watch the chart all day" in model form.

## Architecture

### Decision cadence
- 1 step = 1 M5 bar (12 steps per H1 bar).
- The H1 feature block is refreshed only when an H1 bar **closes** (no look-ahead);
  it stays constant across the 12 M5 steps inside that hour.
- The M5 feature block changes every step.

### Observation (~61 floats)
```
H1 features    (25)  whole-hour context: trend, regime, ATR ratio, session
M5 features    (25)  same indicator set on the 5-min bars
tf_state        (3)  h1_progress (0..1), h1_m5_count (0..12), h1_bars_since_close
position state  (8)  direction, cur_r, peak_r, bars_in_trade, dist_tp_atr,
                     dist_sl_atr, tp_r, sl_atr_mult
```
H1 and M5 blocks must be built from the SAME M1 series, then aligned: for each M5
bar, join the most recent H1 bar whose close time is <= the M5 bar's time.

### Action space (same as v4 — model controls everything)
```
MultiDiscrete([3, 8, 8, 6, 2])
  [0] direction    0 flat, 1 long, 2 short
  [1] sl bucket    8 steps across 0.5..3.0 x ATR
  [2] tp bucket    8 steps across 0.5..5.0 R
  [3] risk bucket  6 steps across 0.1%..2% of equity   (model-set lot size)
  [4] close        0 hold, 1 close now                 (model-set exit)
```

## Reward contract

Deliberately starts from the v3 reward that is proven, NOT the v4 variant:

```
reward = d_equity / risk_unit                    # realized PnL (primary)
       + 0.01 * cur_r                            # mark-to-market shaping
       - 0.02 * giveback_from_peak               # teaches "don't give profit back"
       - 0.20 * loss (when realized_r < -0.5)    # loss aversion
       - holding_penalty                         # discourages dead time
```
No separate close_bonus. The exit behaviour must be learned from the giveback
penalty, so the model does not learn to churn trades for a bonus.

## Data

- Source: `synth_v3.csv` (generator v3: domain-randomized regimes + ~22% real anchor).
- Resample `M1 -> H1` for context and `M1 -> M5` for decisions from the same series.
- Execution/TP-SL fill simulation stays on the M1 bars (as in v3/v4).
- No new data generation required.

## Training plan

1. `features_multitf.py` — build M5 decision frame with merged H1 columns + tf_state.
2. `env_bracket_v5.py` — env with the ~61-float observation; step logic mirrors v4.
3. `train_v5.py` — one strong finale model + validate on ALL folds (not 2).
4. Sanity: random policy on a short window; smoke train ~50k steps.
5. Full train ~1M steps (v4 showed over-fit after ~725k; do not over-train).
6. `rollout_v5_allfolds.py` — replay every fold's true OOS test window.
7. Compare to v3 and v4 on the same table; only then consider deploy.

## Live runner plan (`live/live_runner_v5.py`)

- Poll every 1 minute; rebuild the H1+M5 observation from MT5 bars.
- **Preserve the LSTM hidden state across predictions** (unlike the v3 runner),
  so the model maintains continuity while it watches the live chart.
- Same safety layer: one position, risk cap, daily kill-switch, spread guard.

## Risks

| Risk | Level | Mitigation |
|---|---|---|
| Bigger observation (61) over-fits faster | high | early-stop, best_model checkpoint, weight decay |
| H1/M5 mis-alignment leaks future | high | only join H1 bars that have already closed |
| M5 noise remains | medium | H1 context filters it |
| Reward still needs tuning | medium | start from the proven v3 reward |
| Training time | ~3–5 h | comparable to v4 |

## Decision log (open questions)

- H1 features: full 25 or a reduced trend/regime subset? (smaller obs = less over-fit)
- Include tf_state 3 fields? (helps the model know where it is within the hour)
- Decision cadence: M5 only, or M1 for maximum frequency? (M1 is much heavier)
- Train pod: `e89nbyzwyuo83x` (RTX A4000) or a fresh one.

## File map (to create)

| File | Role |
|---|---|
| `opt/rl_gold/features_multitf.py` | H1+M5 merge + tf_state |
| `opt/rl_gold/env_bracket_v5.py` | v5 env (61-float obs, v4 action) |
| `opt/rl_gold/train_v5.py` | finale train + all-fold validate |
| `opt/rl_gold/rollout_v5_allfolds.py` | OOS replay per fold |
| `opt/rl_gold/live/live_runner_v5.py` | live multi-TF runner (stateful LSTM) |
