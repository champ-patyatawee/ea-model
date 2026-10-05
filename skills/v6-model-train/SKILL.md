---
name: v6-model-train
description: Train the RL-Gold v6 model (H1 LSTM, gen_v3 synthetic data) on a RunPod GPU pod, then export the models and deploy the demo runner
license: MIT
compatibility: opencode
metadata:
  audience: developers
---

## What I do

- Regenerate the synthetic training data (`gen_v3.py`) and launch the v6 walk-forward
  LSTM training (`train_v6.py`) on a RunPod pod, in a `tmux` session
- Monitor the per-fold train/val/score lines and the consistency-gate `BEST` checkpoints
- Read the out-of-sample `TEST` return / PF / Sharpe / DD per fold and the `summary.csv`
- Export the trained folds (`models_v6*/`) plus the training code back to the Mac
- Point the live demo runner at the chosen fold's `best_model.zip` + `best_model_vecnorm.pkl`

This is the v6 lineage. The result that matters: **v6c = 9/9 folds positive, mean +26.23%**
(trained on `gen_v3` synthetic data). A control run on block-bootstrap real data (v6b)
was much worse (2/10, mean -0.66%) — so the data choice, not just the algorithm, decides.

## When to use me

- When you need to (re)train the v6 model or a variant (different data source, reward, steps)
- When a RunPod GPU pod is available and you want the full train → validate → export loop
- When comparing v6 against v3 / v4 / v5 on the same walk-forward OOS table
- When preparing a model for the live demo runner (export + point the runner at it)

## Usage

### Prerequisites

- RunPod GPU pod running (RTX A4000 or better), reachable over SSH
- Pod has a venv with `stable-baselines3 sb3-contrib pandas` and CUDA torch
  (`python3 -m venv --system-site-packages /root/rl/venv` then pip install)
- The RL base package copied to the pod at `/root/rl_gold/Reinforcement_Trading_Part_2/`
  (config.py, data_loader.py, features.py, env_bracket.py, evaluate.py)
- Training scripts at `/root/rl_gold/`: `train_v6.py`, `train_lstm.py`,
  `gen_v3.py`, `env_bracket_v4.py`, `env_bracket_v5.py`, `features_multitf.py`
- Real M1 history at `/root/rl_gold/xauusdm_m1_all.csv` (only needed if using the
  empirical generator `gen_v4_empirical.py`; gen_v3 needs `gc_h1.csv`)

### Step 1 — SSH in and check the pod

```bash
ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new -i ./id_ed25519 -p <PORT> root@<HOST> \
  'hostname; nvidia-smi --query-gpu=name,memory.total --format=csv,noheader; tmux ls 2>/dev/null || echo NO_TMUX'
```

### Step 2 — (Re)generate the synthetic training data

v6c uses the hand-coded generator v3 — it produced the most learnable data:

```bash
ssh ... 'cd /root/rl_gold && /root/rl/venv/bin/python gen_v3.py 2>&1 | tail -4'
# writes /root/rl_gold/synth_v3.csv (~1.2M M1 bars)
# regime mix: trend 26% / real 22% / range 19% / spike 14% / chop 12% / gap 6%
```

Optional control — empirical block-bootstrap from 7y real M1 (known to be weaker):

```bash
ssh ... 'cd /root/rl_gold && /root/rl/venv/bin/python gen_v4_empirical.py 20260930 /root/rl_gold/synth_v4.csv 1.0'
```

### Step 3 — Launch v6 training in tmux

`train_v6.py` reads `SYNTH` (default `/root/rl_gold/synth_v3.csv`) and `OUT_ROOT`.
It builds H1 decisions, trains a RecurrentPPO (LSTM) walk-forward, and validates
every fold's test window.

```bash
ssh ... 'bash -lc "
tmux kill-session -t v6 2>/dev/null
rm -rf /root/rl_gold/models_v6
tmux new-session -d -s v6
tmux send-keys -t v6 \"cd /root/rl_gold && TOTAL_STEPS=300000 N_ENVS=24 VEC_START_METHOD=spawn FLAT_PEN=0.01 /root/rl/venv/bin/python -u train_v6.py > /root/rl_gold/v6.log 2>&1\" Enter
sleep 40; tmux ls; head -7 /root/rl_gold/v6.log"'
```

Key env vars:

| var | default | meaning |
|---|---|---|
| `TOTAL_STEPS` | 300000 | steps per fold |
| `N_ENVS` | 40 | parallel envs (24 is fine on a small GPU) |
| `VEC_START_METHOD` | forkserver | use `spawn` on the pod |
| `SYNTH` | `/root/rl_gold/synth_v3.csv` | training data CSV |
| `OUT_ROOT` | `/root/rl_gold/models_v6` | model output dir |
| `FLAT_PEN` | 0.0 | **set 0.01** — a small flat penalty stops the "never trade" collapse that appears on some data |

### Step 4 — Monitor

```bash
# eval lines: train=x/ddN% val=y/ddN% score=z  (BEST = checkpoint saved)
ssh ... 'grep -E "^\[" /root/rl_gold/v6.log | tail -6; grep -cE BEST /root/rl_gold/v6.log'
# per-fold OOS results as they finish
ssh ... 'grep -E "TEST|folds positive" /root/rl_gold/v6.log; cat /root/rl_gold/models_v6/summary.csv 2>/dev/null'
# is it still running?
ssh ... 'tmux ls 2>/dev/null || echo DONE'
```

**Watch for the no-trade trap:** if `train=+0.00/dd 0.0% val=+0.00` repeats, the agent
settled on "never trade" — relaunch with `FLAT_PEN=0.01`. This is the single most
common failure mode with the H1 + v3-action setup.

### Step 5 — Export to the Mac

```bash
ssh ... 'mkdir -p /root/export_v6 && cp -r /root/rl_gold/models_v6 /root/export_v6/ \
  && cp /root/rl_gold/v6.log /root/rl_gold/train_v6.py /root/export_v6/ \
  && tar czf /root/v6_export.tar.gz -C /root export_v6 && ls -lh /root/v6_export.tar.gz'
scp -i ./id_ed25519 -P <PORT> root@<HOST>:/root/v6_export.tar.gz ./opt/rl_gold/
cd opt/rl_gold && tar xzf v6_export.tar.gz   # -> export_v6/models_v6/<fold_N>/{best_model,final_model}
```

Each fold dir contains: `best_model/best_model.zip`, `best_model/best_model_vecnorm.pkl`,
`final_model.zip`, `final_vecnorm.pkl`, and `eval_logs/consistency_evals.csv`.

### Step 6 — Deploy to the live demo (Docker)

The v6c action space is the v3 one (`MultiDiscrete([3,3,4])`, H1 features), so use the
**v3 runner** `opt/rl_gold/live/live_runner.py`, pointing at a fold's `best_model`.

```bash
D=/Applications/Docker.app/Contents/Resources/bin/docker
M=/work/rl_gold/export_v6/models_v6c
$D exec rl bash -lc "cd /work/rl_gold/live && MT5_HOST=<mt5-ip> \
  MT5_HOST=172.22.0.2 H1_ONLY=1 MIN_HOLD_MIN=0 POLL_SECONDS=300 \
  nohup python3 -u live_runner.py \
  --model $M/fold_9/best_model/best_model.zip \
  --vecnorm $M/fold_9/best_model/best_model_vecnorm.pkl \
  --folds '$M/fold_7,$M/fold_8' --max-risk-pct 20 --loop \
  > /work/rl_gold/live/v6c_runner.out 2>&1 &"
```

**Live-must-equal-train (the rule the v6c live failure taught us):**

| dimension | train (env_bracket.py) | live runner must do |
|---|---|---|
| decision cadence | once per **H1 close** | `H1_ONLY=1` — act only on a new closed H1 bar |
| SL/TP | set **once** at `_open_position`, never modified | do **not** modify SL/TP while holding |
| exit | only on `flat` or `flip` | close only on flat/flip |

Running the runner faster than the training cadence (e.g. every 5-min poll) caused a
flip-fest: 9 round-trips in 3.5 h, spread drag, **balance -10.5% in 4 h** on the demo,
while the same model's backtest showed **+26%**. Match the cadence.

## Format / Templates

### Launch template

```
tmux kill-session -t v6 2>/dev/null
tmux new-session -d -s v6
tmux send-keys -t v6 "cd /root/rl_gold && TOTAL_STEPS=300000 N_ENVS=24 VEC_START_METHOD=spawn FLAT_PEN=0.01 SYNTH=/root/rl_gold/synth_v3.csv OUT_ROOT=/root/rl_gold/models_v6 /root/rl/venv/bin/python -u train_v6.py > /root/rl_gold/v6.log 2>&1" Enter
```

### Monitor template

```
grep -E "^\[" /root/rl_gold/v6.log | tail -6
grep -cE BEST /root/rl_gold/v6.log
grep -E "TEST|folds positive" /root/rl_gold/v6.log
cat /root/rl_gold/models_v6/summary.csv
```

### Export template

```
tar czf /root/v6_export.tar.gz -C /root export_v6
# then scp to $HOME/opt/rl_gold/ and untar
```

## Workflow

1. **Pre-check** — pod up, venv ready, RL base + scripts present, GPU free.
2. **Data** — run `gen_v3.py` (default) → `synth_v3.csv`. (Optional: `gen_v4_empirical.py` for the weaker control.)
3. **Launch** — tmux `v6` with `TOTAL_STEPS=300000 N_ENVS=24 FLAT_PEN=0.01`.
4. **Monitor** — watch eval lines; if `train=0.00 val=0.00` repeats, kill and relaunch with `FLAT_PEN=0.01`.
5. **Validate** — per-fold `TEST` lines print automatically; read `models_v6/summary.csv`.
6. **Export** — tar `export_v6` on the pod, scp to `opt/rl_gold/`, untar.
7. **Deploy** — v3 runner (`live_runner.py`) with `H1_ONLY=1`, pointed at a fold's `best_model`.
8. **Verify parity** — confirm the runner only acts on H1 close and never modifies SL/TP, so live matches the backtest.

## Reference results (walk-forward OOS, gen_v3 data)

| model | data | positive folds | mean OOS | mean PF |
|---|---|---|---|---|
| v3 | gen_v3 | 10/10 | +19.78% | ~1.42 |
| v4 | gen_v3 | 7/9 | +14.46% | 1.57 |
| v5b | gen_v3, M5+H1 | 9/9 | +21.96% | 1.32 |
| **v6c** | **gen_v3, H1** | **9/9** | **+26.23%** | ~3.64 |
| v6b | bootstrap real | 2/10 | -0.66% | — |

**Lesson:** hand-coded regime data (`gen_v3`) beats block-bootstrap real data here.
"More realistic" is not the same as "more learnable" — the model needs structured signal.

## Troubleshooting

- `ModuleNotFoundError: train_lstm` → copy `train_lstm.py` to `/root/rl_gold/`
- `ModuleNotFoundError: openai gym / gymnasium` → install into the venv
- `train=+0.00 val=+0.00` forever → no-trade collapse; set `FLAT_PEN=0.01`
- `PEP 668 externally-managed` on pip → make a venv with `--system-site-packages`
- stale v6 processes keep respawning → `pkill -9 -f train_v6` and kill by pid; a new run is safe once `nvidia-smi` shows the GPU free
- live flips constantly / bleeds → the runner is acting faster than H1; set `H1_ONLY=1` and do not modify SL/TP while holding
- `retcode 10018 Market closed` → weekend; the runner will retry when the market opens
- `EOFError('stream has been closed')` in the runner → rpyc bridge restarted; the runner auto-reconnects (`bridge.reconnect()`)
</parameter>
</invoke>
</parameter>

Wait — I need to close the write call properly. Let me re-issue it.

<parameter name="write">content
I made a formatting error. Let me issue the write cleanly.

<parameter name="bash">mkdir -p /Users/champp/Desktop/ea/skills/v6-model-train && echo created</parameter>

Now write the file.

<parameter name="write">
<parameter name="filePath">/Users/champp/Desktop/ea/skills/v6-model-train/SKILL.md</parameter>
<parameter name="content" string="true">---
name: v6-model-train
description: Train the RL-Gold v6 model (H1 LSTM, gen_v3 synthetic data) on a RunPod GPU pod, then export the models and deploy the demo runner
license: MIT
compatibility: opencode
metadata:
  audience: developers
---

## What I do

- Regenerate the synthetic training data (`gen_v3.py`) and launch the v6 walk-forward LSTM training (`train_v6.py`) on a RunPod pod, in a `tmux` session
- Monitor the per-fold train/val/score lines and the consistency-gate `BEST` checkpoints
- Read the out-of-sample `TEST` return / PF / Sharpe / DD per fold and the `summary.csv`
- Export the trained folds (`models_v6*/`) plus the training code back to the Mac
- Point the live demo runner at the chosen fold's `best_model.zip` + `best_model_vecnorm.pkl`

This is the v6 lineage. The result that matters: **v6c = 9/9 folds positive, mean +26.23%** (trained on `gen_v3` synthetic data). A control run on block-bootstrap real data (v6b) was much worse (2/10, mean -0.66%) — so the data choice, not just the algorithm, decides.

## When to use me

- When you need to (re)train the v6 model or a variant (different data source, reward, steps)
- When a RunPod GPU pod is available and you want the full train -> validate -> export loop
- When comparing v6 against v3 / v4 / v5 on the same walk-forward OOS table
- When preparing a model for the live demo runner (export + point the runner at it)

## Usage

### Prerequisites

- RunPod GPU pod running (RTX A4000 or better), reachable over SSH
- Pod has a venv with `stable-baselines3 sb3-contrib pandas` and CUDA torch (`python3 -m venv --system-site-packages /root/rl/venv` then pip install)
- The RL base package copied to the pod at `/root/rl_gold/Reinforcement_Trading_Part_2/` (config.py, data_loader.py, features.py, env_bracket.py, evaluate.py)
- Training scripts at `/root/rl_gold/`: `train_v6.py`, `train_lstm.py`, `gen_v3.py`, `env_bracket_v4.py`, `env_bracket_v5.py`, `features_multitf.py`
- Real M1 history at `/root/rl_gold/xauusdm_m1_all.csv` (only needed for the empirical generator `gen_v4_empirical.py`; gen_v3 needs `gc_h1.csv`)

### Step 1 — SSH in and check the pod

```bash
ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new -i ./id_ed25519 -p <PORT> root@<HOST> \
  'hostname; nvidia-smi --query-gpu=name,memory.total --format=csv,noheader; tmux ls 2>/dev/null || echo NO_TMUX'
```

### Step 2 — (Re)generate the synthetic training data

v6c uses the hand-coded generator v3 — it produced the most learnable data:

```bash
ssh ... 'cd /root/rl_gold && /root/rl/venv/bin/python gen_v3.py 2>&1 | tail -4'
# writes /root/rl_gold/synth_v3.csv (~1.2M M1 bars)
# regime mix: trend 26% / real 22% / range 19% / spike 14% / chop 12% / gap 6%
```

Optional control — empirical block-bootstrap from 7y real M1 (known to be weaker):

```bash
ssh ... 'cd /root/rl_gold && /root/rl/venv/bin/python gen_v4_empirical.py 20260930 /root/rl_gold/synth_v4.csv 1.0'
```

### Step 3 — Launch v6 training in tmux

`train_v6.py` reads `SYNTH` (default `/root/rl_gold/synth_v3.csv`) and `OUT_ROOT`. It builds H1 decisions, trains a RecurrentPPO (LSTM) walk-forward, and validates every fold's test window.

```bash
ssh ... 'bash -lc "
tmux kill-session -t v6 2>/dev/null
rm -rf /root/rl_gold/models_v6
tmux new-session -d -s v6
tmux send-keys -t v6 \"cd /root/rl_gold && TOTAL_STEPS=300000 N_ENVS=24 VEC_START_METHOD=spawn FLAT_PEN=0.01 /root/rl/venv/bin/python -u train_v6.py > /root/rl_gold/v6.log 2>&1\" Enter
sleep 40; tmux ls; head -7 /root/rl_gold/v6.log"'
```

Key env vars:

| var | default | meaning |
|---|---|---|
| `TOTAL_STEPS` | 300000 | steps per fold |
| `N_ENVS` | 40 | parallel envs (24 is fine on a small GPU) |
| `VEC_START_METHOD` | forkserver | use `spawn` on the pod |
| `SYNTH` | `/root/rl_gold/synth_v3.csv` | training data CSV |
| `OUT_ROOT` | `/root/rl_gold/models_v6` | model output dir |
| `FLAT_PEN` | 0.0 | set 0.01 — a small flat penalty stops the "never trade" collapse that appears on some data |

### Step 4 — Monitor

```bash
# eval lines: train=x/ddN% val=y/ddN% score=z  (BEST = checkpoint saved)
ssh ... 'grep -E "^\[" /root/rl_gold/v6.log | tail -6; grep -cE BEST /root/rl_gold/v6.log'
# per-fold OOS results as they finish
ssh ... 'grep -E "TEST|folds positive" /root/rl_gold/v6.log; cat /root/rl_gold/models_v6/summary.csv 2>/dev/null'
# is it still running?
ssh ... 'tmux ls 2>/dev/null || echo DONE'
```

Watch for the no-trade trap: if `train=+0.00/dd 0.0% val=+0.00` repeats, the agent settled on "never trade" — relaunch with `FLAT_PEN=0.01`. This is the most common failure mode with the H1 + v3-action setup.

### Step 5 — Export to the Mac

```bash
ssh ... 'mkdir -p /root/export_v6 && cp -r /root/rl_gold/models_v6 /root/export_v6/ \
  && cp /root/rl_gold/v6.log /root/rl_gold/train_v6.py /root/export_v6/ \
  && tar czf /root/v6_export.tar.gz -C /root export_v6 && ls -lh /root/v6_export.tar.gz'
scp -i ./id_ed25519 -P <PORT> root@<HOST>:/root/v6_export.tar.gz ./opt/rl_gold/
cd opt/rl_gold && tar xzf v6_export.tar.gz   # -> export_v6/models_v6/<fold_N>/{best_model,final_model}
```

Each fold dir contains: `best_model/best_model.zip`, `best_model/best_model_vecnorm.pkl`, `final_model.zip`, `final_vecnorm.pkl`, and `eval_logs/consistency_evals.csv`.

### Step 6 — Deploy to the live demo (Docker)

The v6c action space is the v3 one (`MultiDiscrete([3,3,4])`, H1 features), so use the v3 runner `opt/rl_gold/live/live_runner.py`, pointing at a fold's `best_model`.

```bash
D=/Applications/Docker.app/Contents/Resources/bin/docker
M=/work/rl_gold/export_v6/models_v6c
$D exec rl bash -lc "cd /work/rl_gold/live && MT5_HOST=172.22.0.2 H1_ONLY=1 MIN_HOLD_MIN=0 POLL_SECONDS=300 \
  nohup python3 -u live_runner.py \
  --model $M/fold_9/best_model/best_model.zip \
  --vecnorm $M/fold_9/best_model/best_model_vecnorm.pkl \
  --folds '$M/fold_7,$M/fold_8' --max-risk-pct 20 --loop \
  > /work/rl_gold/live/v6c_runner.out 2>&1 &"
```

Live-must-equal-train (the rule the v6c live failure taught us):

| dimension | train (env_bracket.py) | live runner must do |
|---|---|---|
| decision cadence | once per H1 close | `H1_ONLY=1` — act only on a new closed H1 bar |
| SL/TP | set once at `_open_position`, never modified | do not modify SL/TP while holding |
| exit | only on `flat` or `flip` | close only on flat/flip |

Running the runner faster than the training cadence (e.g. every 5-min poll) caused a flip-fest: 9 round-trips in 3.5 h, spread drag, **balance -10.5% in 4 h** on the demo, while the same model's backtest showed **+26%**. Match the cadence.

## Format / Templates

### Launch template

```
tmux kill-session -t v6 2>/dev/null
tmux new-session -d -s v6
tmux send-keys -t v6 "cd /root/rl_gold && TOTAL_STEPS=300000 N_ENVS=24 VEC_START_METHOD=spawn FLAT_PEN=0.01 SYNTH=/root/rl_gold/synth_v3.csv OUT_ROOT=/root/rl_gold/models_v6 /root/rl/venv/bin/python -u train_v6.py > /root/rl_gold/v6.log 2>&1" Enter
```

### Monitor template

```
grep -E "^\[" /root/rl_gold/v6.log | tail -6
grep -cE BEST /root/rl_gold/v6.log
grep -E "TEST|folds positive" /root/rl_gold/v6.log
cat /root/rl_gold/models_v6/summary.csv
```

### Export template

```
tar czf /root/v6_export.tar.gz -C /root export_v6
# then scp to $HOME/opt/rl_gold/ and untar
```

## Workflow

1. Pre-check — pod up, venv ready, RL base + scripts present, GPU free.
2. Data — run `gen_v3.py` (default) -> `synth_v3.csv`. (Optional: `gen_v4_empirical.py` for the weaker control.)
3. Launch — tmux `v6` with `TOTAL_STEPS=300000 N_ENVS=24 FLAT_PEN=0.01`.
4. Monitor — watch eval lines; if `train=0.00 val=0.00` repeats, kill and relaunch with `FLAT_PEN=0.01`.
5. Validate — per-fold `TEST` lines print automatically; read `models_v6/summary.csv`.
6. Export — tar `export_v6` on the pod, scp to `opt/rl_gold/`, untar.
7. Deploy — v3 runner (`live_runner.py`) with `H1_ONLY=1`, pointed at a fold's `best_model`.
8. Verify parity — confirm the runner only acts on H1 close and never modifies SL/TP, so live matches the backtest.

## Reference results (walk-forward OOS, gen_v3 data)

| model | data | positive folds | mean OOS | mean PF |
|---|---|---|---|---|
| v3 | gen_v3 | 10/10 | +19.78% | ~1.42 |
| v4 | gen_v3 | 7/9 | +14.46% | 1.57 |
| v5b | gen_v3, M5+H1 | 9/9 | +21.96% | 1.32 |
| v6c | gen_v3, H1 | 9/9 | +26.23% | ~3.64 |
| v6b | bootstrap real | 2/10 | -0.66% | — |

Lesson: hand-coded regime data (`gen_v3`) beats block-bootstrap real data here. "More realistic" is not the same as "more learnable" — the model needs structured signal.

## Troubleshooting

- `ModuleNotFoundError: train_lstm` -> copy `train_lstm.py` to `/root/rl_gold/`
- `ModuleNotFoundError: gymnasium` -> install into the venv
- `train=+0.00 val=+0.00` forever -> no-trade collapse; set `FLAT_PEN=0.01`
- `PEP 668 externally-managed` on pip -> make a venv with `--system-site-packages`
- stale v6 processes keep respawning -> `pkill -9 -f train_v6` and kill by pid; a new run is safe once `nvidia-smi` shows the GPU free
- live flips constantly / bleeds -> the runner is acting faster than H1; set `H1_ONLY=1` and do not modify SL/TP while holding
- `retcode 10018 Market closed` -> weekend; the runner will retry when the market opens
- `EOFError('stream has been closed')` in the runner -> rpyc bridge restarted; the runner auto-reconnects (`bridge.reconnect()`)
</parameter>
</parameter>
</invoke>
</parameter>
</invoke>
</parameter>

I keep mis-forming. Let me do it as a single clean call now.

<parameter name="write">
<parameter name="filePath">/Users/champp/Desktop/ea/skills/v6-model-train/SKILL.md</parameter>
<parameter name="content" string="true">---
name: v6-model-train
description: Train the RL-Gold v6 model (H1 LSTM, gen_v3 synthetic data) on a RunPod GPU pod, then export the models and deploy the demo runner
license: MIT
compatibility: opencode
metadata:
  audience: developers
---

## What I do

- Regenerate the synthetic training data (`gen_v3.py`) and launch the v6 walk-forward LSTM training (`train_v6.py`) on a RunPod pod, in a `tmux` session
- Monitor the per-fold train/val/score lines and the consistency-gate `BEST` checkpoints
- Read the out-of-sample `TEST` return / PF / Sharpe / DD per fold and the `summary.csv`
- Export the trained folds (`models_v6*/`) plus the training code back to the Mac
- Point the live demo runner at the chosen fold's `best_model.zip` + `best_model_vecnorm.pkl`

This is the v6 lineage. The result that matters: **v6c = 9/9 folds positive, mean +26.23%** (trained on `gen_v3` synthetic data). A control run on block-bootstrap real data (v6b) was much worse (2/10, mean -0.66%) — so the data choice, not just the algorithm, decides.

## When to use me

- When you need to (re)train the v6 model or a variant (different data source, reward, steps)
- When a RunPod GPU pod is available and you want the full train -> validate -> export loop
- When comparing v6 against v3 / v4 / v5 on the same walk-forward OOS table
- When preparing a model for the live demo runner (export + point the runner at it)

## Usage

### Prerequisites

- RunPod GPU pod running (RTX A4000 or better), reachable over SSH
- Pod has a venv with `stable-baselines3 sb3-contrib pandas` and CUDA torch (`python3 -m venv --system-site-packages /root/rl/venv` then pip install)
- The RL base package copied to the pod at `/root/rl_gold/Reinforcement_Trading_Part_2/` (config.py, data_loader.py, features.py, env_bracket.py, evaluate.py)
- Training scripts at `/root/rl_gold/`: `train_v6.py`, `train_lstm.py`, `gen_v3.py`, `env_bracket_v4.py`, `env_bracket_v5.py`, `features_multitf.py`
- Real M1 history at `/root/rl_gold/xauusdm_m1_all.csv` (only needed for the empirical generator `gen_v4_empirical.py`; gen_v3 needs `gc_h1.csv`)

### Step 1 — SSH in and check the pod

```bash
ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new -i ./id_ed25519 -p <PORT> root@<HOST> \
  'hostname; nvidia-smi --query-gpu=name,memory.total --format=csv,noheader; tmux ls 2>/dev/null || echo NO_TMUX'
```

### Step 2 — (Re)generate the synthetic training data

v6c uses the hand-coded generator v3 — it produced the most learnable data:

```bash
ssh ... 'cd /root/rl_gold && /root/rl/venv/bin/python gen_v3.py 2>&1 | tail -4'
# writes /root/rl_gold/synth_v3.csv (~1.2M M1 bars)
# regime mix: trend 26% / real 22% / range 19% / spike 14% / chop 12% / gap 6%
```

Optional control — empirical block-bootstrap from 7y real M1 (known to be weaker):

```bash
ssh ... 'cd /root/rl_gold && /root/rl/venv/bin/python gen_v4_empirical.py 20260930 /root/rl_gold/synth_v4.csv 1.0'
```

### Step 3 — Launch v6 training in tmux

`train_v6.py` reads `SYNTH` (default `/root/rl_gold/synth_v3.csv`) and `OUT_ROOT`. It builds H1 decisions, trains a RecurrentPPO (LSTM) walk-forward, and validates every fold's test window.

```bash
ssh ... 'bash -lc "
tmux kill-session -t v6 2>/dev/null
rm -rf /root/rl_gold/models_v6
tmux new-session -d -s v6
tmux send-keys -t v6 \"cd /root/rl_gold && TOTAL_STEPS=300000 N_ENVS=24 VEC_START_METHOD=spawn FLAT_PEN=0.01 /root/rl/venv/bin/python -u train_v6.py > /root/rl_gold/v6.log 2>&1\" Enter
sleep 40; tmux ls; head -7 /root/rl_gold/v6.log"'
```

Key env vars:

| var | default | meaning |
|---|---|---|
| `TOTAL_STEPS` | 300000 | steps per fold |
| `N_ENVS` | 40 | parallel envs (24 is fine on a small GPU) |
| `VEC_START_METHOD` | forkserver | use `spawn` on the pod |
| `SYNTH` | `/root/rl_gold/synth_v3.csv` | training data CSV |
| `OUT_ROOT` | `/root/rl_gold/models_v6` | model output dir |
| `FLAT_PEN` | 0.0 | set 0.01 — a small flat penalty stops the "never trade" collapse that appears on some data |

### Step 4 — Monitor

```bash
# eval lines: train=x/ddN% val=y/ddN% score=z  (BEST = checkpoint saved)
ssh ... 'grep -E "^\[" /root/rl_gold/v6.log | tail -6; grep -cE BEST /root/rl_gold/v6.log'
# per-fold OOS results as they finish
ssh ... 'grep -E "TEST|folds positive" /root/rl_gold/v6.log; cat /root/rl_gold/models_v6/summary.csv 2>/dev/null'
# is it still running?
ssh ... 'tmux ls 2>/dev/null || echo DONE'
```

Watch for the no-trade trap: if `train=+0.00/dd 0.0% val=+0.00` repeats, the agent settled on "never trade" — relaunch with `FLAT_PEN=0.01`. This is the most common failure mode with the H1 + v3-action setup.

### Step 5 — Export to the Mac

```bash
ssh ... 'mkdir -p /root/export_v6 && cp -r /root/rl_gold/models_v6 /root/export_v6/ \
  && cp /root/rl_gold/v6.log /root/rl_gold/train_v6.py /root/export_v6/ \
  && tar czf /root/v6_export.tar.gz -C /root export_v6 && ls -lh /root/v6_export.tar.gz'
scp -i ./id_ed25519 -P <PORT> root@<HOST>:/root/v6_export.tar.gz ./opt/rl_gold/
cd opt/rl_gold && tar xzf v6_export.tar.gz   # -> export_v6/models_v6/<fold_N>/{best_model,final_model}
```

Each fold dir contains: `best_model/best_model.zip`, `best_model/best_model_vecnorm.pkl`, `final_model.zip`, `final_vecnorm.pkl`, and `eval_logs/consistency_evals.csv`.

### Step 6 — Deploy to the live demo (Docker)

The v6c action space is the v3 one (`MultiDiscrete([3,3,4])`, H1 features), so use the v3 runner `opt/rl_gold/live/live_runner.py`, pointing at a fold's `best_model`.

```bash
D=/Applications/Docker.app/Contents/Resources/bin/docker
M=/work/rl_gold/export_v6/models_v6c
$D exec rl bash -lc "cd /work/rl_gold/live && MT5_HOST=172.22.0.2 H1_ONLY=1 MIN_HOLD_MIN=0 POLL_SECONDS=300 \
  nohup python3 -u live_runner.py \
  --model $M/fold_9/best_model/best_model.zip \
  --vecnorm $M/fold_9/best_model/best_model_vecnorm.pkl \
  --folds '$M/fold_7,$M/fold_8' --max-risk-pct 20 --loop \
  > /work/rl_gold/live/v6c_runner.out 2>&1 &"
```

Live-must-equal-train (the rule the v6c live failure taught us):

| dimension | train (env_bracket.py) | live runner must do |
|---|---|---|
| decision cadence | once per H1 close | `H1_ONLY=1` — act only on a new closed H1 bar |
| SL/TP | set once at `_open_position`, never modified | do not modify SL/TP while holding |
| exit | only on `flat` or `flip` | close only on flat/flip |

Running the runner faster than the training cadence (e.g. every 5-min poll) caused a flip-fest: 9 round-trips in 3.5 h, spread drag, **balance -10.5% in 4 h** on the demo, while the same model's backtest showed **+26%**. Match the cadence.

## Format / Templates

### Launch template

```
tmux kill-session -t v6 2>/dev/null
tmux new-session -d -s v6
tmux send-keys -t v6 "cd /root/rl_gold && TOTAL_STEPS=300000 N_ENVS=24 VEC_START_METHOD=spawn FLAT_PEN=0.01 SYNTH=/root/rl_gold/synth_v3.csv OUT_ROOT=/root/rl_gold/models_v6 /root/rl/venv/bin/python -u train_v6.py > /root/rl_gold/v6.log 2>&1" Enter
```

### Monitor template

```
grep -E "^\[" /root/rl_gold/v6.log | tail -6
grep -cE BEST /root/rl_gold/v6.log
grep -E "TEST|folds positive" /root/rl_gold/v6.log
cat /root/rl_gold/models_v6/summary.csv
```

### Export template

```
tar czf /root/v6_export.tar.gz -C /root export_v6
# then scp to $HOME/opt/rl_gold/ and untar
```

## Workflow

1. Pre-check — pod up, venv ready, RL base + scripts present, GPU free.
2. Data — run `gen_v3.py` (default) -> `synth_v3.csv`. (Optional: `gen_v4_empirical.py` for the weaker control.)
3. Launch — tmux `v6` with `TOTAL_STEPS=300000 N_ENVS=24 FLAT_PEN=0.01`.
4. Monitor — watch eval lines; if `train=0.00 val=0.00` repeats, kill and relaunch with `FLAT_PEN=0.01`.
5. Validate — per-fold `TEST` lines print automatically; read `models_v6/summary.csv`.
6. Export — tar `export_v6` on the pod, scp to `opt/rl_gold/`, untar.
7. Deploy — v3 runner (`live_runner.py`) with `H1_ONLY=1`, pointed at a fold's `best_model`.
8. Verify parity — confirm the runner only acts on H1 close and never modifies SL/TP, so live matches the backtest.

## Reference results (walk-forward OOS, gen_v3 data)

| model | data | positive folds | mean OOS | mean PF |
|---|---|---|---|---|
| v3 | gen_v3 | 10/10 | +19.78% | ~1.42 |
| v4 | gen_v3 | 7/9 | +14.46% | 1.57 |
| v5b | gen_v3, M5+H1 | 9/9 | +21.96% | 1.32 |
| v6c | gen_v3, H1 | 9/9 | +26.23% | ~3.64 |
| v6b | bootstrap real | 2/10 | -0.66% | — |

Lesson: hand-coded regime data (`gen_v3`) beats block-bootstrap real data here. "More realistic" is not the same as "more learnable" — the model needs structured signal.

## Troubleshooting

- `ModuleNotFoundError: train_lstm` -> copy `train_lstm.py` to `/root/rl_gold/`
- `ModuleNotFoundError: gymnasium` -> install into the venv
- `train=+0.00 val=+0.00` forever -> no-trade collapse; set `FLAT_PEN=0.01`
- `PEP 668 externally-managed` on pip -> make a venv with `--system-site-packages`
- stale v6 processes keep respawning -> `pkill -9 -f train_v6` and kill by pid; a new run is safe once `nvidia-smi` shows the GPU free
- live flips constantly / bleeds -> the runner is acting faster than H1; set `H1_ONLY=1` and do not modify SL/TP while holding
- `retcode 10018 Market closed` -> weekend; the runner will retry when the market opens
- `EOFError('stream has been closed')` in the runner -> rpyc bridge restarted; the runner auto-reconnects (`bridge.reconnect()`)
</parameter>
</invoke>
</parameter>
</invoke>
</parameter>
</invoke>
</parameter>
</invoke>
</parameter>
</invoke>