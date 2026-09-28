#!/usr/bin/env bash
# One-shot setup on a fresh RunPod container (Ubuntu, >=8 vCPU).
# Assumes this whole deploy_pod/ folder is at /root/deploy_pod
set -e
ROOT=/root/rl_gold
mkdir -p "$ROOT"

echo "[1/5] python venv"
python3.11 -m venv /root/rl/venv
PY=/root/rl/venv/bin/python
$PY -m pip install --quiet --upgrade pip

echo "[2/5] core deps"
$PY -m pip install --quiet pandas numpy gymnasium scikit-learn plotly tqdm

echo "[3/5] torch (CPU) + stable-baselines3"
$PY -m pip install --quiet torch --index-url https://download.pytorch.org/whl/cpu
$PY -m pip install --quiet "stable-baselines3>=2.3"

echo "[4/5] verify"
$PY -c "import pandas,numpy,gymnasium,sklearn,torch,stable_baselines3 as s;print('ok',pandas.__version__,numpy.__version__,'torch',torch.__version__,'sb3',s.__version__)"

echo "[5/5] place files"
rm -rf "$ROOT/Reinforcement_Trading_Part_2"
cp -r /root/deploy_pod/vendor "$ROOT/Reinforcement_Trading_Part_2"
cp /root/deploy_pod/gen_real_synth.py /root/deploy_pod/run_phase2.py "$ROOT/"
cp /root/deploy_pod/data/xauusdm_m1.csv "$ROOT/"
ls -lh "$ROOT"
echo "SETUP DONE"
