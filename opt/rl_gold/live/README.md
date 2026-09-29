# RL-Gold v3 — Live Demo Runner (MT5)

Run the trained LSTM (RecurrentPPO) model live on an MT5 demo account.
Training happens on a GPU pod; **running** (inference) is light and runs inside
the local Docker MT5 stack.

- Model: `export_v3/models_v3/fold_*` (LSTM, reward v2, generator-v3 trained)
- Live stack: `mt5` container (Wine + MT5 + rpyc bridge on `:8001`) + `rl` container (Python + SB3)
- Symbol: `XAUUSDm` (Exness demo, account `434226308`)
- Decision cadence: H1 bar close (runner polls every `POLL_SECONDS`)

---

## 1. Prerequisites

Both containers must be up (they share nothing by default — the runner reaches MT5 over the Docker network):

```bash
D=/Applications/Docker.app/Contents/Resources/bin/docker
$D ps --format "{{.Names}} | {{.Image}} | {{.Status}}"
# mt5 | gmag11/metatrader5_vnc | Up
# rl  | python:3.11-slim       | Up
```

Get the MT5 container IP (the runner needs it as `MT5_HOST`):

```bash
$D inspect mt5 --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'
# e.g. 172.22.0.2
```

One-time setup inside the `rl` container (already done if you ran the runner before):

```bash
$D exec rl pip install -q sb3-contrib rpyc pandas
```

AutoTrading must be **enabled in MT5** (VNC `http://localhost:3000`, user `champ` / pass `2443`,
or the AutoTrading button in the toolbar). If an order returns
`retcode 10027 "AutoTrading disabled by client"`, this is what is off.

---

## 2. Paths (why `/work/...`)

The `rl` container mounts `opt/` → `/work`. So a file at
`opt/rl_gold/live/live_runner.py` on the Mac is `/work/rl_gold/live/live_runner.py`
inside the container. All commands below run *inside* `rl`.

Models live at `/work/rl_gold/export_v3/models_v3/fold_N/{best_model,final_model}`.

---

## 3. Quick start

```bash
cd /Users/champp/Desktop/ea
D=/Applications/Docker.app/Contents/Resources/bin/docker
M=/work/rl_gold/export_v3/models_v3
```

### 3a. Dry-run, single cycle (sends NO orders)

Prints the model's decision (direction / SL / TP / lot / risk) without trading:

```bash
$D exec rl bash -lc "cd /work/rl_gold/live && MT5_HOST=172.22.0.2 python3 live_runner.py \
  --model $M/fold_2/best_model/best_model.zip \
  --vecnorm $M/fold_2/best_model/best_model_vecnorm.pkl \
  --folds '$M/fold_3,$M/fold_4,$M/fold_5,$M/fold_9' \
  --max-risk-pct 20 --dry-run --once"
```

### 3b. Live, single cycle (sends a real demo order)

Drop `--dry-run`:

```bash
$D exec rl bash -lc "cd /work/rl_gold/live && MT5_HOST=172.22.0.2 python3 live_runner.py \
  --model $M/fold_2/best_model/best_model.zip \
  --vecnorm $M/fold_2/best_model/best_model_vecnorm.pkl \
  --folds '$M/fold_3,$M/fold_4,$M/fold_5,$M/fold_9' \
  --max-risk-pct 20 --once"
```

### 3c. Live, background loop (the normal way to trade)

Runs forever, polls every 300 s, logs to a JSONL file:

```bash
$D exec -d rl bash -lc "cd /work/rl_gold/live && MT5_HOST=172.22.0.2 POLL_SECONDS=300 \
  MAX_SPREAD_POINTS=800 nohup python3 -u live_runner.py \
  --model $M/fold_2/best_model/best_model.zip \
  --vecnorm $M/fold_2/best_model/best_model_vecnorm.pkl \
  --folds '$M/fold_3,$M/fold_4,$M/fold_5,$M/fold_9' \
  --max-risk-pct 20 --loop > /work/rl_gold/live/runner.out 2>&1 &"
```

---

## 4. (Optional) Local Python env instead of Docker

Not recommended: macOS Python has no `sb3-contrib` and would need the MT5 port
mapped to the host. If you must, install `stable-baselines3 sb3-contrib rpyc pandas`
and point `--host` at `127.0.0.1` (port `8001` is published on the host).

---

## 5. CLI options

| Flag | Default | Meaning |
|---|---|---|
| `--model` | — | primary model `.zip` (`best_model.zip` preferred) |
| `--vecnorm` | — | matching `*_vecnorm.pkl` (obs normalization stats) |
| `--folds` | empty | comma-separated extra fold **dirs** → ensemble vote |
| `--host` | `$MT5_HOST` or `172.22.0.2` | MT5 container IP |
| `--port` | `8001` | rpyc bridge port |
| `--symbol` | `XAUUSDm` | trading symbol |
| `--dry-run` | off | decide + log, never send orders |
| `--once` | off | one decision cycle then exit |
| `--loop` | off | continuous loop, sleep `POLL_SECONDS` |
| `--log` | `/work/rl_gold/live/live_decisions.jsonl` | decision log |
| `--risk` | `0.005` (CFG) | equity fraction risked per trade (sizing input) |
| `--max-risk-pct` | `20` | **skip** an entry if one trade would risk more than this % of equity |

Environment: `MT5_HOST`, `POLL_SECONDS` (default 300), `MAX_SPREAD_POINTS` (default 800),
`M1_LEVELS` (default 40000 bars fetched), `MAGIC` (default 860001).

### Ensemble voting

Each fold is loaded with its own `obs_rms` (normalization). Every member predicts
`(direction, sl_idx, tp_idx)`. The runner takes the **majority direction** (requires
at least half the members to agree, else it stays flat), then the **median** SL/TP
bracket among the agreeing members. More folds → steadier, but more often flat.

Recommended ensemble (5 stable folds): `fold_2, fold_3, fold_4, fold_5, fold_9`.

---

## 6. How a cycle works

1. Fetch last `M1_LEVELS` M1 bars from MT5 (`copy_rates_from_pos`).
2. Resample to H1, add features (identical to training: `prepare_feature_frame`).
3. Rebuild `BracketTradingEnv` on the window, cursor at the last bar, inject the
   real open MT5 position (if any) so the observation matches training.
4. Ensemble `predict` → `(direction, sl_idx, tp_idx)`.
5. Reconcile with the live position:
   - model flat / opposite → **close** (and maybe reverse)
   - same direction → refresh SL/TP if they drifted (`TRADE_ACTION_SLTP`)
   - flat + model wants exposure → **open** with size/SL/TP from ATR
6. Sizing: `units = (equity * risk) / SL_dist`, then convert to lots
   (`lot = units / contract_size`, rounded to `volume_step`, min `volume_min`).
7. Risk cap: if the resulting trade would risk more than `--max-risk-pct` of equity,
   the entry is skipped (`risk_cap_skip`).

> Note on small accounts: at ~$150 with `volume_min 0.01`, a single 1.5×ATR stop
> can risk ~15% of equity. The default `--max-risk-pct 20` allows it; lower the cap
> to trade less, or fund the demo more to make 0.5% sizing meaningful.

---

## 7. Monitoring

```bash
D=/Applications/Docker.app/Contents/Resources/bin/docker

# tail the loop output
$D exec rl bash -lc 'tail -5 /work/rl_gold/live/runner.out'

# last decisions (JSONL)
$D exec rl bash -lc 'tail -3 /work/rl_gold/live/live_decisions.jsonl'

# account + open positions
$D exec rl bash -lc 'MT5_HOST=172.22.0.2 python3 -c "
import os,sys; sys.path.insert(0,\"/work/rl_gold/live\")
from mt5_bridge import MT5
b=MT5(os.environ[\"MT5_HOST\"],8001)
print(b.account()); print(b.positions(\"XAUUSDm\",860001))"'

# is the loop alive?
$D exec rl bash -lc 'ls /proc | grep -E "^[0-9]+$" | while read p; do \
  grep -q live_runner /proc/$p/cmdline 2>/dev/null && echo "pid $p alive"; done'
```

Key log events: `start`, `decision`, `entry`, `would_enter`, `hold`,
`would_close`/`close`, `modify`, `risk_cap_skip`, `spread_guard`,
`daily_cap_hit`, `error`.

---

## 8. Stop the runner

```bash
D=/Applications/Docker.app/Contents/Resources/bin/docker
$D exec rl bash -lc 'ls /proc | grep -E "^[0-9]+$" | while read p; do \
  grep -q live_runner /proc/$p/cmdline 2>/dev/null && kill $p; done'
```

Safety switches already in the runner:

- **Kill switch** — halt for the day if equity drops ≥10% below the day's start
  (`daily_cap_hit`).
- **Spread guard** — skip the cycle if the spread exceeds `MAX_SPREAD_POINTS`.
- **One position** — magic `860001`, single symbol; never pyramids.
- **Risk cap** — `--max-risk-pct` per-entry.

---

## 9. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `retcode 10027 "AutoTrading disabled by client"` | Enable AutoTrading in MT5 (VNC toolbar) |
| `mt5.initialize failed` | `mt5` container down, or wrong `MT5_HOST` IP |
| `connect ok` fails from `rl` | containers on different networks — use the `mt5` container IP |
| `order_check`/`order_send` returns None via `mt5linux` | known `mt5linux` dict f-string bug — use `mt5_bridge.py` (raw rpyc), not the `mt5linux` package |
| `filling_mode`/retcode quirks | symbol uses IOC (`ORDER_FILLING_IOC`); already handled |
| No fitted features / empty decision frame | increase `M1_LEVELS` so warmup bars (250 H1) exist |
| Order rejected for volume | account too small for the computed lot — raise capital or lower risk |

---

## 10. Files

| File | Role |
|---|---|
| `live/mt5_bridge.py` | rpyc client to MT5 (read bars, account, positions; send/close/modify orders) |
| `live/live_runner.py` | decision loop (features → ensemble predict → order) |
| `live/live_decisions.jsonl` | append-only decision log |
| `live/runner.out` | stdout of the background loop |
| `export_v3/` | models, `RL_base/` training code, data, logs |
| `backtest_jul.py` | offline July-2025 backtest (same predictor, historical data) |
