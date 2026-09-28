#!/usr/bin/env bash
set -e
K=/Users/champp/Desktop/ea/id_ed25519
H=root@157.157.221.177
P=29949
SCP=(scp -q -o StrictHostKeyChecking=accept-new -i "$K" -P "$P")
SSH=(ssh -T -o StrictHostKeyChecking=accept-new -i "$K" -p "$P" "$H")

"${SSH[@]}" 'mkdir -p /root/rl_gold /root/vendor'
echo "== repo =="
"${SCP[@]}" -r /Users/champp/Desktop/ea/opt/vendor/Reinforcement_Trading_Part_2 "$H:/root/vendor/"
echo "== data =="
"${SCP[@]}" /Users/champp/Desktop/ea/opt/rl_gold/xauusdm_m1.csv "$H:/root/rl_gold/"
"${SCP[@]}" /Users/champp/Desktop/ea/opt/rl_gold/synth_real_m1.csv "$H:/root/rl_gold/"
echo "== scripts =="
"${SCP[@]}" /Users/champp/Desktop/ea/opt/rl_gold/run_phase2.py \
               /Users/champp/Desktop/ea/opt/rl_gold/gen_real_synth.py \
               /Users/champp/Desktop/ea/opt/rl_gold/fetch_m1.py \
               "$H:/root/rl_gold/"
"${SSH[@]}" 'ls -lh /root/rl_gold/ /root/vendor/'
