#!/usr/bin/env python3
"""Worst days with full per-trade detail and loss reasoning (v4.82)."""
import re, html, os, argparse
import run_bt as R


def get_deals():
    s = open(os.path.join(R.HOST, "report.htm"), encoding="utf-16").read()
    out, h = [], None
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>", s, flags=re.S | re.I):
        c = [html.unescape(re.sub(r"<[^>]+>", "", x)).strip()
             for x in re.findall(r"<td[^>]*>(.*?)</td>", r, flags=re.S | re.I)]
        if c and c[0] == "Time" and "Deal" in c:
            h = c; continue
        if h and c and c[0][:2] == "20" and len(c) >= len(h):
            out.append(dict(zip(h, c)))
    return out


def f(x):
    try:
        return float(x.replace(" ", "").replace("\u00a0", "").replace("\u202f", ""))
    except Exception:
        return 0.0


def reason(in_cm, outs):
    if in_cm.startswith("F-SELL"):
        d = "SHORT fade (bullish pullback)"
    elif in_cm.startswith("F-BUY"):
        d = "LONG fade (bearish pullback)"
    elif in_cm.startswith("SELL"):
        d = "SHORT continuation"
    elif in_cm.startswith("BUY"):
        d = "LONG continuation"
    else:
        d = "?"
    ends = []
    for o in outs:
        cm = o.get("Comment", "")
        if cm.startswith("sl"):
            ends.append("SL")
        elif cm.startswith("tp"):
            ends.append("TP")
        else:
            ends.append("partial/time")
    return d + " | exit: " + ",".join(ends)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="d1", default="2025.01.01")
    ap.add_argument("--to", dest="d2", default="2026.07.01")
    ap.add_argument("--lot", default="0.02")
    ap.add_argument("--top", type=int, default=3)
    a = ap.parse_args()

    R.run(R.build_ini(a.d1, a.d2, {"InpFixedLot": a.lot}, deposit=10000))
    deals = get_deals()

    trades, cur = [], None
    for d in deals:
        dr = d.get("Direction")
        if dr == "in":
            cur = {"in": d, "outs": []}
            trades.append(cur)
        elif dr == "out" and cur is not None:
            cur["outs"].append(d)

    day = {}
    for t in trades:
        p = sum(f(o["Profit"]) for o in t["outs"])
        day[t["in"]["Time"][:10]] = day.get(t["in"]["Time"][:10], 0.0) + p

    worst = sorted(day.items(), key=lambda kv: kv[1])[:a.top]
    print(f"period {a.d1}..{a.d2} lot={a.lot} days={len(day)}")
    print("heaviest loss days:", [(d, round(p, 2)) for d, p in worst])
    for dayd, dayp in worst:
        ts = [t for t in trades if t["in"]["Time"][:10] == dayd]
        w = sum(1 for t in ts if sum(f(o["Profit"]) for o in t["outs"]) > 0)
        l = len(ts) - w
        print("\n" + "=" * 108)
        print(f"DAY {dayd}  net={dayp:+.2f}  trades={len(ts)} (win {w}/loss {l})")
        for t in ts:
            i = t["in"]; outs = t["outs"]
            prof = sum(f(o["Profit"]) for o in outs)
            vol = i["Volume"]; entry = i["Price"]
            cm = i.get("Comment", "")
            m = re.search(r"RISK=([\d.]+)", cm)
            riskp = float(m.group(1)) if m else 0.0
            risk_money = riskp * f(vol) * 100.0
            ex = "->".join(o["Price"] for o in outs)
            print(f"  {i['Time'][11:]} {i['Type']:4s} {vol} entry={entry} exits={ex} "
                  f"P/L={prof:+7.2f} risk$={risk_money:5.2f} | {reason(cm, outs)}")

    # summary of trade counts on the bad days
    print("\n--- lot note: fixed 0.02 but partial(50%) closes 0.01 first ---")


if __name__ == "__main__":
    main()
