#!/usr/bin/env python3
"""Analyse oracle_monthly.json: fixed-best vs oracle vs walk-forward."""
import json, statistics as st

d = json.load(open("oracle_monthly.json"))
months = sorted({m for v in d.values() for m in v})
combos = list(d.keys())

# fixed best by grand total
tot = {c: sum(d[c].get(m, 0.0) for m in months) for c in combos}
best_fixed = max(tot, key=tot.get)

print("Totals per combo:")
for c in combos:
    print(f"  {c:12s} {tot[c]:8.1f}")
print(f"best fixed = {best_fixed} ({tot[best_fixed]:.1f})\n")

# oracle per month (hindsight)
oracle = {m: max(combos, key=lambda c: d[c].get(m, 0.0)) for m in months}
oracle_tot = sum(d[oracle[m]].get(m, 0.0) for m in months)
print(f"ORACLE (hindsight, best each month) = {oracle_tot:.1f}")

# walk-forward: use combo with best total over previous K months
for K in (2, 3, 6):
    wf_tot = 0.0
    picks = []
    for i, m in enumerate(months):
        prev = months[max(0, i - K):i]
        if not prev:
            c = best_fixed
        else:
            c = max(combos, key=lambda c: sum(d[c].get(p, 0.0) for p in prev))
        wf_tot += d[c].get(m, 0.0)
        picks.append((m, c))
    print(f"WALK-FORWARD K={K}: {wf_tot:.1f}")
    # how often did the picked combo change
    changes = sum(1 for i in range(1, len(picks)) if picks[i][1] != picks[i-1][1])
    print(f"   combo changes: {changes}/{len(picks)-1}")

print(f"\nFIXED best total = {tot[best_fixed]:.1f}")
print(f"ORACLE total     = {oracle_tot:.1f}  (upper bound)")
print("\nOracle pick per month:")
for m in months:
    vals = {c: round(d[c].get(m, 0.0), 1) for c in combos}
    print(f"  {m}: best={oracle[m]:12s} {vals}")
