#!/usr/bin/env python3
"""Find the EA weakness: performance on one-directional (trend) days vs range days."""
import re, html, collections, os
import run_bt as R

D1_CSV = os.path.join(R.HOST, "d1_xau.csv")
PER = ("2025.01.01", "2026.09.24")


def load_d1():
    rows = {}
    with open(D1_CSV) as f:
        for ln in f:
            p = ln.split()
            if len(p) != 5:
                continue
            d = p[0].replace("-", ".")
            o, h, l, c = map(float, p[1:])
            rows[d] = dict(o=o, h=h, l=l, c=c)
    return rows


def atr14(d1, dates):
    # simple ATR14 of daily range
    out = {}
    trs = []
    for i, d in enumerate(dates):
        r = d1[d]
        tr = r["h"] - r["l"]
        trs.append(tr)
        if i >= 13:
            out[d] = sum(trs[i - 13:i + 1]) / 14.0
    return out


def daily_pos():
    """daily net P/L and per-direction from last report."""
    s = open(os.path.join(R.HOST, "report.htm"), encoding="utf-16").read()
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
    day = collections.defaultdict(lambda: {"net": 0.0, "n": 0, "w": 0,
                                           "L": 0.0, "S": 0.0, "nL": 0, "nS": 0})
    for t in pos:
        p = sum(f(o["Profit"]) for o in t["outs"])
        d = t["in"]["Time"][:10]
        side = t["in"].get("Type")
        dd = day[d]
        dd["net"] += p; dd["n"] += 1
        if p > 0: dd["w"] += 1
        if side == "buy":
            dd["L"] += p; dd["nL"] += 1
        else:
            dd["S"] += p; dd["nS"] += 1
    return day


def main():
    R.run(R.build_ini(PER[0], PER[1], {}, deposit=10000))
    day = daily_pos()
    d1 = load_d1()
    dates = sorted(d1)
    atr = atr14(d1, dates)

    # classify each trading day
    buckets = collections.defaultdict(lambda: {"net": 0.0, "n": 0, "w": 0,
                                               "days": 0, "L": 0.0, "S": 0.0,
                                               "losedays": 0})
    trend_days = []
    for d in sorted(day):
        if d not in d1 or d not in atr:
            continue
        r = d1[d]
        body = abs(r["c"] - r["o"])
        rng = r["h"] - r["l"]
        eff = body / rng if rng > 0 else 0
        rel = body / atr[d] if atr[d] > 0 else 0
        # trend day = directional AND big
        if eff >= 0.6 and rel >= 1.0:
            b = "TREND"
        elif eff <= 0.35:
            b = "RANGE"
        else:
            b = "MIXED"
        dd = day[d]
        bb = buckets[b]
        bb["net"] += dd["net"]; bb["n"] += dd["n"]; bb["w"] += dd["w"]
        bb["days"] += 1; bb["L"] += dd["L"]; bb["S"] += dd["S"]
        if dd["net"] < 0: bb["losedays"] += 1
        if b == "TREND":
            trend_days.append((d, round(dd["net"], 1), round(eff, 2),
                               "up" if r["c"] > r["o"] else "down", dd["n"],
                               round(dd["L"], 1), round(dd["S"], 1)))

    print(f"{'bucket':8}{'days':>5}{'trades':>7}{'win%':>6}{'net$':>10}"
          f"{'net/day':>9}{'loseD':>6}{'LongNet':>9}{'ShortNet':>9}")
    for b in ("TREND", "MIXED", "RANGE"):
        v = buckets[b]
        if not v["days"]:
            continue
        print(f"{b:8}{v['days']:>5}{v['n']:>7}{100*v['w']/max(v['n'],1):>6.0f}"
              f"{v['net']:>10.1f}{v['net']/v['days']:>9.1f}{v['losedays']:>6}"
              f"{v['L']:>9.1f}{v['S']:>9.1f}")

    print("\nworst TREND days:")
    for t in sorted(trend_days, key=lambda x: x[1])[:12]:
        print("  ", t)


if __name__ == "__main__":
    main()
