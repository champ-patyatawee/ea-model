#!/usr/bin/env python3
"""Phase 0: per-month P/L for a small param grid, then compare
fixed-best vs oracle vs walk-forward."""
import re, html, collections, json, os
import run_bt as R

OFF = {"InpUseRegimeFilter": "false", "InpUseATRAdaptiveZone": "false",
       "InpUseDualMode": "false", "InpUseHTFTrendFilter": "false",
       "InpUseDailyDirLock": "false", "InpRandomEntry": "false",
       "InpFixedLot": 0.02}

D1, D2 = "2025.01.01", "2026.09.18"
REACT = [2.5, 3.5]          # >=3  and  >=4
TPS = [1.0, 1.5, 2.0]


def monthly_net():
    s = open(R.HOST + "/report.htm", encoding="utf-16").read()
    rows = []; h = None
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>", s, flags=re.S | re.I):
        c = [html.unescape(re.sub(r"<[^>]+>", "", x)).strip()
             for x in re.findall(r"<td[^>]*>(.*?)</td>", r, flags=re.S | re.I)]
        if c and c[0] == "Time" and "Deal" in c:
            h = c; continue
        if h and c and c[0][:2] == "20" and len(c) >= len(h):
            rows.append(dict(zip(h, c)))
    pos = []; cur = None
    for d in rows:
        if d.get("Direction") == "in":
            cur = {"in": d, "outs": []}; pos.append(cur)
        elif d.get("Direction") == "out" and cur is not None:
            cur["outs"].append(d)
    def f(x):
        try: return float(x.replace(" ", "").replace("\u00a0", "").replace("\u202f", ""))
        except Exception: return 0.0
    mon = collections.defaultdict(float)
    for t in pos:
        p = sum(f(o["Profit"]) for o in t["outs"])
        mon[t["in"]["Time"][:7]] += p
    return mon


data = {}
for rc in REACT:
    for tp in TPS:
        p = dict(OFF); p.update({"InpMinReactionScore": rc, "InpTP_R": tp})
        R.run(R.build_ini(D1, D2, p, deposit=10000))
        m = R.parse()
        key = f"r{rc}_tp{tp}"
        data[key] = monthly_net()
        print(key, "total", round(m.get("net", 0), 1), flush=True)

json.dump(data, open("oracle_monthly.json", "w"))
print("saved oracle_monthly.json")
