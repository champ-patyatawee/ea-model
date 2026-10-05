#!/usr/bin/env bash
# Control the RunPod training pod for rl-gold v7.
#   ./pod.sh status|start|stop|ssh|balance
# Override the pod with POD_ID=xxxx ./pod.sh ...
set -euo pipefail

POD_ID="${POD_ID:-rtmzjhhf3p3ua6}"
CFG="$HOME/.config/opencode/opencode.json"
SSHKEY="/Users/champp/Desktop/ea/id_ed25519"
API="https://api.runpod.io/graphql"
REST="https://rest.runpod.io/v1"

KEY=$(python3 -c "import json;print(json.load(open('$CFG'))['mcp']['runpod']['headers']['Authorization'].split()[-1])")

q() { curl -s -m 30 "$API?api_key=$KEY" -H "Content-Type: application/json" -d "{\"query\":\"$1\"}"; }

runtime_ports() {
  q "{ myself { pods { id desiredStatus runtime { uptimeInSeconds ports { ip isIpPublic privatePort publicPort } } } } }" \
  | python3 -c "
import sys,json
d=json.load(sys.stdin)
for p in (d['data']['myself']['pods'] or []):
    if p['id']!='$POD_ID': continue
    rt=p.get('runtime') or {}
    ssh=next((x for x in (rt.get('ports') or []) if x['privatePort']==22), None)
    print(p['desiredStatus'], rt.get('uptimeInSeconds') or 0, ssh['ip'] if ssh else '', ssh['publicPort'] if ssh else '')
"
}

case "${1:-status}" in
  status)
    q "{ myself { clientBalance currentSpendPerHr pods { id name desiredStatus machine { gpuDisplayName location secureCloud } } } }" \
    | python3 -c "
import sys,json
m=json.load(sys.stdin)['data']['myself']
print('balance \$%.2f  spend/h \$%s' % (m['clientBalance'], m['currentSpendPerHr']))
for p in m['pods'] or []:
    g=p.get('machine') or {}
    print(' ', p['id'], p['desiredStatus'], g.get('gpuDisplayName'), g.get('location'), 'secure' if g.get('secureCloud') else 'community')
"
    ;;
  start)
    curl -s -m 60 -X POST "$REST/pods/$POD_ID/start" -H "Authorization: Bearer $KEY" -w "HTTP %{http_code}\n" | tail -1
    echo "waiting for ssh..."; for i in $(seq 1 20); do read -r st up ip port < <(runtime_ports); [ "$st" = "RUNNING" ] && [ -n "$ip" ] && { echo "ssh -i $SSHKEY -p $port root@$ip"; break; }; sleep 10; done
    ;;
  stop)
    curl -s -m 60 -X POST "$REST/pods/$POD_ID/stop" -H "Authorization: Bearer $KEY" -w "HTTP %{http_code}\n" | tail -1
    ;;
  ssh)
    read -r st up ip port < <(runtime_ports)
    [ -n "$ip" ] || { echo "no ssh (status=$st)"; exit 1; }
    exec ssh -o StrictHostKeyChecking=accept-new -i "$SSHKEY" -p "$port" root@"$ip"
    ;;
  balance)
    q "{ myself { clientBalance currentSpendPerHr } }" | python3 -c "import sys,json;m=json.load(sys.stdin)['data']['myself'];print('balance \$%.2f spend/h \$%s'%(m['clientBalance'],m['currentSpendPerHr']))"
    ;;
  *) echo "usage: $0 status|start|stop|ssh|balance"; exit 1;;
esac
