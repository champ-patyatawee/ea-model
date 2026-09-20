#!/usr/bin/env python3
"""Phase 1: month-by-month anatomy of the strategy (position level)."""
import re, html, collections, statistics as st
import run_bt as R


def get_positions():
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
    out = []
    for t in pos:
        p = sum(f(o["Profit"]) for o in t["outs"])
        side = "L" if t["in"].get("Type") == "buy" else "S"
        out.append((t["in"]["Time"][:10], side, p))
    return out


def main():
    R.run(R.build_ini("2025.01.01", "2026.07.01", {}, deposit=10000))
    tr = get_positions()

    mon = collections.OrderedDict()
    for date, side, p in tr:
        mon.setdefault(date[:7], []).append((date, side, p))

    print(f"{'month':8}{'pos':>5}{'days':>5}{'tr/d':>6}{'win%':>6}{'net$':>10}"
          f"{'avgW':>7}{'avgL':>7}{'payf':>6} | {'L_n':>4}{'L_win%':>7}{'L_net':>9}"
          f" | {'S_n':>4}{'S_win%':>7}{'S_net':>9} | {'loseD':>5}{'maxStreak':>9}{'maxDirLoss':>10}")
    for m in sorted(mon):
        rows = mon[m]
        days = sorted(set(r[0] for r in rows))
        n = len(rows)
        w = [p for _, _, p in rows if p > 0]
        l = [p for _, _, p in rows if p < 0]
        long = [(s, p) for _, s, p in rows if s == "L"]
        short = [(s, p) for _, s, p in rows if s == "S"]
        lw = [p for _, p in long if p > 0]; ln = [p for _, p in long if p < 0]
        sw = [p for _, p in short if p > 0]; sn = [p for _, p in short if p < 0]
        # losing days
        lday = collections.Counter()
        for d, _, p in rows: lday[d] += p
        loseD = sum(1 for d in lday if lday[d] < 0)
        # max consecutive losing positions
        streak = best = 0
        for _, _, p in rows:
            if p < 0: streak += 1; best = max(best, streak)
            else: streak = 0
        # max same-direction consecutive losses
        dirbest = cur = 0; lastside = None
        for _, s, p in rows:
            if p < 0:
                if s == lastside: cur += 1
                else: cur = 1
                dirbest = max(dirbest, cur); lastside = s
            else:
                cur = 0; lastside = None
        def wpct(ws, ns):
            tot = len(ws) + len(ns)
            return (100*len(ws)/tot) if tot else 0
        print(f"{m:8}{n:>5}{len(days):>5}{n/len(days):>6.1f}"
              f"{100*len(w)/n:>6.1f}{sum(p for _,_,p in rows):>10.1f}"
              f"{st.mean(w) if w else 0:>7.1f}{st.mean(l) if l else 0:>7.1f}"
              f"{st.mean(w)/-st.mean(l) if w and l else 0:>6.2f} | "
              f"{len(long):>4}{wpct(lw,ln):>7.1f}{sum(p for _,p in long):>9.1f} | "
              f"{len(short):>4}{wpct(sw,sn):>7.1f}{sum(p for _,p in short):>9.1f} | "
              f"{loseD:>5}{best:>9}{dirbest:>10}")


if __name__ == "__main__":
    main()
