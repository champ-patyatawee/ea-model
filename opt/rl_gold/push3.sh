#!/usr/bin/env bash
set -e
K=/Users/champp/Desktop/ea/id_ed25519
H=root@157.157.221.177
P=29949
SCP=(scp -o StrictHostKeyChecking=accept-new -i "$K" -P "$P")
SSH=(ssh -T -o StrictHostKeyChecking=accept-new -i "$K" -p "$P" "$H")

echo "== resend real M1 (34MB, previous copy was truncated) =="
"${SCP[@]}" /Users/champp/Desktop/ea/opt/rl_gold/xauusdm_m1.csv "$H:/root/rl_gold/xauusdm_m1_full.csv"

echo "== scripts =="
"${SCP[@]}" /Users/champp/Desktop/ea/opt/rl_gold/gen_real_synth.py \
               /Users/champp/Desktop/ea/opt/rl_gold/run_phase2.py \
               "$H:/root/rl_gold/"

echo "== sizes =="
"${SSH[@]}" 'ls -lh /root/rl_gold/'
