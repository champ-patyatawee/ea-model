#!/usr/bin/env bash
set -e
PY=/root/rl/venv/bin/python
ROOT=/root/rl_gold
mkdir -p "$ROOT"
echo "== synthetic =="
$PY "$ROOT/gen_real_synth.py"
echo "== train (background) =="
cd "$ROOT/Reinforcement_Trading_Part_2"
nohup $PY "$ROOT/run_phase2.py" > "$ROOT/phase2.log" 2>&1 &
echo "pid=$!"; sleep 5; tail -3 "$ROOT/phase2.log"
