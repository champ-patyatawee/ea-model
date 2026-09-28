#!/usr/bin/env bash
# Push repo + data + scripts to the RunPod host.
set -e
KEY=${KEY:-/Users/champp/Desktop/ea/id_ed25519}
HOST=${HOST:-root@157.157.221.30}
PORT=${PORT:-17534}
SSH="ssh -T -o StrictHostKeyChecking=accept-new -i $KEY -p $PORT $HOST"
SCP="scp -o StrictHostKeyChecking=accept-new -i $KEY -P $PORT"

LOCAL=/Users/champp/Desktop/ea/opt/rl_gold
$SSH 'mkdir -p /work/vendor /work/rl_gold'
$SCP -r /Users/champp/Desktop/ea/opt/vendor/Reinforcement_Trading_Part_2 "$HOST:/work/vendor/"
$SCP "$LOCAL"/xauusdm_m1.csv "$LOCAL"/synth_real_m1.csv "$HOST:/work/rl_gold/"
$SCP "$LOCAL"/run_phase2.py "$LOCAL"/gen_real_synth.py "$LOCAL"/fetch_m1.py "$HOST:/work/rl_gold/"
$SSH 'ls -lh /work/rl_gold/ /work/vendor/'
