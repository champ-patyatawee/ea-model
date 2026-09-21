#!/usr/bin/env python3
"""Compare v4.6 (B: >=3/2.0) vs v5.0 (A: >=3/1.5) monthly at $100."""
import re, html, collections, os
import run_bt as R

D1, D2 = "2025.01.01", "2026.09.18"
DEP = 100

COMMON = {"InpMinReactionScore": 2.5, "InpUseHTFTrendFilter": "false",
          "InpUseDailyDirLock": "false", "InpRandomEntry": "false",
          "InpFixedLot": 0.01,
          # v5.0-only keys are ignored by v4.6? MT5 passes them; unknown names
          # are harmless for the tester only if present in EA. Keep separate.
          }
V4 = dict(COMMON); V4["InpTP_R"] = 2.0
V5 = dict(COMMON); V5["InpTP_R"] = 1.5
V5.update({"InpUseRegimeFilter": "false", "InpUseATRAdaptiveZone": "false",
           "InpUseDualMode": "false"})


def monthly():
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
    mon = collections.defaultdict(float); n = collections.Counter()
    for t in pos:
        p = sum(f(o["Profit"]) for o in t["outs"])
        m = t["in"]["Time"][:7]; mon[m] += p; n[m] += 1
    return mon, n


res = {}
for name, exp, params in [("v4.6_B", "FiboAdaptiveEA_v4.6", V4),
                          ("v5.0_A", "FiboAdaptiveEA_v5.0", V5)]:
    os.environ["MT5_EXPERT"] = exp
    R.run(R.build_ini(D1, D2, params, deposit=DEP))
    m = R.parse()
    mon, n = monthly()
    res[name] = (mon, n)
    print(f"{name} total={m.get('net'):.2f} trades={m.get('trades')} "
          f"pf={m.get('pf')} dd%={m.get('dd_pct')}", flush=True)

months = sorted(set(list(res["v4.6_B"][0]) + list(res["v5.0_A"][0])))
print(f"\n{'month':9}{'v4.6_B':>10}{'B_#':>5}{'v5.0_A':>10}{'A_#':>5}{'winner':>10}")
for m in months:
    b = res["v4.6_B"][0].get(m, 0.0); bn = res["v4.6_B"][1].get(m, 0)
    a = res["v5.0_A"][0].get(m, 0.0); an = res["v5.0_A"][1].get(m, 0)
    w = "A" if a > b else ("B" if b > a else "-")
    print(f"{m:9}{b:>10.1f}{bn:>5}{a:>10.1f}{an:>5}{w:>10}")
