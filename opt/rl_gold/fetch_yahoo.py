#!/usr/bin/env python3
"""Download XAUUSD (GC=F) history from Yahoo. H1 limited to ~2y; D1 to 20y."""
from __future__ import annotations
import json, time, sys, urllib.request
from datetime import datetime, timezone
import pandas as pd

BASE = "https://query1.finance.yahoo.com/v8/finance/chart/GC=F"
HEAD = {"User-Agent": "Mozilla/5.0"}
OUT = sys.argv[1] if len(sys.argv) > 1 else "/root/rl_gold"


def fetch(interval, p1, p2):
    url = f"{BASE}?interval={interval}&period1={p1}&period2={p2}&includePrePost=false"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=HEAD), timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:
        print("  err", interval, repr(e)); return None


def to_df(js):
    r = js["chart"]["result"][0]
    ts = r.get("timestamp") or []
    q = r["indicators"]["quote"][0]
    vol = q.get("volume") or [0]*len(ts)
    rows = []
    for i, t in enumerate(ts):
        o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        if None in (o, h, l, c): continue
        rows.append((datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                     round(o,3), round(h,3), round(l,3), round(c,3), int(vol[i] or 0)))
    return pd.DataFrame(rows, columns=["time_utc","open","high","low","close","volume"])


def collect(interval, y0, y1, step_days):
    out=[]; p1=int(datetime(y0,1,1,tzinfo=timezone.utc).timestamp())
    end=int(datetime(y1,12,31,tzinfo=timezone.utc).timestamp())
    while p1 < end:
        p2=min(p1+step_days*86400, end)
        js=fetch(interval,p1,p2)
        if js and js.get("chart",{}).get("result"):
            out.append(to_df(js))
        time.sleep(1.0); p1=p2
    if not out: return pd.DataFrame(columns=["time_utc","open","high","low","close","volume"])
    df=pd.concat(out,ignore_index=True).drop_duplicates("time_utc").sort_values("time_utc").reset_index(drop=True)
    return df


d1 = collect("1d", 2006, 2026, 3650)
d1.to_csv(f"{OUT}/gc_d1.csv", index=False)
print("D1", len(d1), d1.time_utc.iloc[0], "->", d1.time_utc.iloc[-1])

h1 = collect("1h", 2024, 2026, 350)
h1.to_csv(f"{OUT}/gc_h1.csv", index=False)
print("H1", len(h1), h1.time_utc.iloc[0], "->", h1.time_utc.iloc[-1])
