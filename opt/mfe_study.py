#!/usr/bin/env python3
"""Entry-quality study: parse MFELOG MFE_R/MAE_R from the tester log."""
import re, os, subprocess
import run_bt as R

DOCKER = R.DOCKER
M = R.M
CONTAINER = R.CONTAINER


def run_fresh(d1, d2, params):
    # clear tester log so we only read this run
    subprocess.run([DOCKER, "exec", CONTAINER, "bash", "-c",
                    f"rm -f '{M}/Tester/logs/'*.log"], check=False)
    R.run(R.build_ini(d1, d2, params, deposit=10000))
    out = subprocess.run([DOCKER, "exec", CONTAINER, "bash", "-c",
                          f"iconv -f UTF-16LE -t UTF-8 '{M}/Tester/logs/'*.log "
                          f"2>/dev/null | grep MFELOG"], capture_output=True, text=True)
    return out.stdout


def parse(lines):
    rows = []
    for ln in lines.splitlines():
        m = re.search(r"MFELOG PROF=(-?\d+) MFE_R=(-?[\d.]+) MAE_R=(-?[\d.]+) P/L=(-?[\d.]+)", ln)
        if m:
            rows.append((int(m.group(1)), float(m.group(2)),
                         float(m.group(3)), float(m.group(4))))
    return rows


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="d1", default="2025.01.01")
    ap.add_argument("--to", dest="d2", default="2026.07.01")
    a = ap.parse_args()

    txt = run_fresh(a.d1, a.d2, {})
    rows = parse(txt)
    n = len(rows)
    print(f"period {a.d1}..{a.d2}  positions with MFELOG: {n}")
    if not n:
        return
    mfe = [r[1] for r in rows]
    mae = [r[2] for r in rows]
    pl = [r[3] for r in rows]

    mean_mfe = sum(mfe) / n
    mean_mae = sum(mae) / n
    print(f"mean MFE_R = {mean_mfe:.3f}   mean MAE_R = {mean_mae:.3f}   "
          f"|MAE| = {abs(mean_mae):.3f}")
    print(f"entry edge (MFE - |MAE|) = {mean_mfe - abs(mean_mae):+.3f} R")
    print()

    # unambiguous reach-first buckets
    pos_clean = sum(1 for m, a in zip(mfe, mae) if m >= 1.0 and a > -1.0)
    neg_clean = sum(1 for m, a in zip(mfe, mae) if a <= -1.0 and m < 1.0)
    ambig = n - pos_clean - neg_clean
    print(f"reached +1R first (clean):   {pos_clean} ({100*pos_clean/n:.1f}%)")
    print(f"reached -1R first (clean):   {neg_clean} ({100*neg_clean/n:.1f}%)")
    print(f"touched both (ambiguous):    {ambig} ({100*ambig/n:.1f}%)")
    decided = pos_clean + neg_clean
    if decided:
        print(f"hit-rate among decided:      {100*pos_clean/decided:.1f}%")
    print()

    # did losers go favorable at all?
    losers = [(m, a, p) for m, a, p in rows if p < 0]
    winners = [(m, a, p) for m, a, p in rows if p > 0]
    print(f"winners {len(winners)}  losers {len(losers)}")
    if losers:
        lm = [x[0] for x in losers]
        print(f"  losers: mean MFE_R={sum(lm)/len(lm):.3f}  "
              f"(reached +1R before losing: {sum(1 for x in lm if x>=1.0)} / {len(lm)})")
    if winners:
        wm = [x[1] for x in winners]
        print(f"  winners: mean MAE_R={sum(wm)/len(wm):.3f}  "
              f"(dipped -1R before winning: {sum(1 for x in wm if x<=-1.0)} / {len(wm)})")


if __name__ == "__main__":
    main()
