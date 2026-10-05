#!/usr/bin/env bash
# Quick v6c live status: account, open position, closed-trade tally, last decisions.
set -e
D=/Applications/Docker.app/Contents/Resources/bin/docker
H=root@157.157.221.29
echo "==== v6c LIVE status  $(date '+%Y-%m-%d %H:%M:%S') ===="
$D exec rl bash -lc 'MT5_HOST=172.22.0.2 python3 - <<PY
import os,sys
sys.path.insert(0,"/work/rl_gold/live")
from mt5_bridge import MT5
b=MT5(os.environ["MT5_HOST"],8001)
a=b.account()
print("equity",a["equity"]," balance",a["balance"])
ps=b.positions("XAUUSDm",860001)
if ps:
    p=ps[0]
    print("OPEN",("LONG" if p["dir"]==1 else "SHORT"),p["volume"],"@",p["price_open"],
          "SL",p["sl"],"TP",p["tp"],"profit",p["profit"])
else:
    print("OPEN none")
# tally entries and closes from the log
import json
ent=cl=0; last=[]
for l in open("/work/rl_gold/live/live_decisions.jsonl"):
    try: r=json.loads(l)
    except: continue
    if r.get("action") in ("entry","close","flip_close","model_close","manual_close"):
        last.append((r.get("ts"),r.get("action"),r.get("desired")))
        if r["action"]=="entry": ent+=1
        else: cl+=1
print("entries",ent,"closes",cl)
for x in last[-6:]: print(" ",x[0],x[1],"desired",x[2])
PY' 2>&1 | tail -14
