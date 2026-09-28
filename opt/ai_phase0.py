#!/usr/bin/env python3
"""Phase-0 AI: build a dataset from the EA tester log (setup features -> trade outcome),
then train an sklearn GBM to test whether features predict win/loss."""
import subprocess, re, os, csv, collections
import run_bt as R

DOCKER, C, M = R.DOCKER, R.CONTAINER, R.M
PARAMS = {"InpMinReactionScore": 2.5, "InpTP_R": 1.5, "InpFixedLot": 0.02,
          "InpUseRegimeFilter": "false", "InpUseATRAdaptiveZone": "false",
          "InpUseDualMode": "false", "InpUseHTFTrendFilter": "false",
          "InpUseDailyDirLock": "false", "InpRandomEntry": "false"}
PER = ("2025.01.01", "2026.09.24")


def grab():
    subprocess.run([DOCKER, "exec", C, "bash", "-c", f"rm -f '{M}/Tester/logs/'*.log"], check=False)
    R.run(R.build_ini(PER[0], PER[1], PARAMS, deposit=10000))
    return subprocess.run([DOCKER, "exec", C, "bash", "-c",
                           f"iconv -f UTF-16LE -t UTF-8 '{M}/Tester/logs/'*.log 2>/dev/null | "
                           f"grep -E 'STRUCTURE|FIBO setup|ORDER OPENED|MFELOG'"],
                          capture_output=True, text=True).stdout


TS = re.compile(r"(2026\.\d\d\.\d\d \d\d:\d\d:\d\d)|(2025\.\d\d\.\d\d \d\d:\d\d:\d\d)")
RS = re.compile(r"STRUCTURE (BUY|SELL): BOS=(\w+) (?:HL|LH)=(\w+) rangeATR=([\d.]+) efficiency=([\d.]+) age=(\d+) FibZone=([\d.]+)-([\d.]+)")
RO = re.compile(r"ORDER OPENED (BUY|SELL) lot=([\d.]+) .*?SL=([\d.]+) TP=([\d.]+) RR=([\d.]+) RiskDistance=([\d.]+)")
RF = re.compile(r"MFELOG PROF=(-?\d+) MFE_R=(-?[\d.]+) MAE_R=(-?[\d.]+) P/L=(-?[\d.]+)")


def parse(txt):
    rows = []
    feat = None          # last structure seen
    pending = None        # last order awaiting MFELOG
    for ln in txt.splitlines():
        if "\t" in ln:
            ln = ln.split("\t")[-1]
        m = TS.search(ln)
        t = m.group(0) if m else None
        if t is None:
            m2 = re.match(r"\s*(\d{4}\.\d\d\.\d\d \d\d:\d\d:\d\d)", ln)
            t = m2.group(1) if m2 else None
        s = RS.search(ln)
        if s:
            feat = dict(side=s.group(1), bos=s.group(2), hl=s.group(3),
                        rangeATR=float(s.group(4)), eff=float(s.group(5)),
                        age=int(s.group(6)), zlo=float(s.group(7)), zhi=float(s.group(8)))
            feat["time"] = t
            continue
        o = RO.search(ln)
        if o:
            pending = dict(otype=o.group(1), lot=float(o.group(2)), sl=float(o.group(3)),
                           tp=float(o.group(4)), rr=float(o.group(5)), risk=float(o.group(6)))
            if feat:
                pending.update(feat)
            pending["time"] = t or (feat.get("time") if feat else None)
            continue
        f = RF.search(ln)
        if f and pending:
            p = pending; pending = None
            # only keep rows that actually opened (have feat)
            if "eff" not in p:
                continue
            hr = int(p["time"][11:13]) if p.get("time") else -1
            rows.append(dict(
                time=p["time"], hour=hr, side=p["side"], eff=p["eff"],
                rangeATR=p["rangeATR"], age=p["age"],
                risk=p["risk"], rr=p["rr"],
                mfe=float(f.group(2)), mae=float(f.group(3)),
                pl=float(f.group(4)), win=1 if float(f.group(4)) > 0 else 0))
    return rows


def main():
    txt = grab()
    rows = parse(txt)
    print("rows:", len(rows))
    if not rows:
        return
    with open(os.path.join(R.HOST, "ai_dataset.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print("saved ai_dataset.csv")
    # quick label stats
    win = sum(r["win"] for r in rows)
    print(f"winrate {100*win/len(rows):.1f}%")

    # train HistGradientBoosting walk-forward (time-sorted)
    import numpy as np
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import roc_auc_score
    rows.sort(key=lambda r: r["time"] or "")
    X = np.array([[r["eff"], r["rangeATR"], r["age"], r["hour"],
                   1.0 if r["side"] == "BUY" else 0.0,
                   r["risk"], 1.0 if r["hour"] >= 12 else 0.0] for r in rows])
    y = np.array([r["win"] for r in rows])
    cut = int(len(rows) * 0.7)
    clf = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05,
                                         max_depth=3, l2_regularization=1.0,
                                         random_state=42)
    clf.fit(X[:cut], y[:cut])
    p = clf.predict_proba(X[cut:])[:, 1]
    try:
        auc = roc_auc_score(y[cut:], p)
    except Exception:
        auc = float("nan")
    print(f"OOS AUC (last 30%) = {auc:.3f}  (0.5 = no skill)")
    # decile: does higher P(win) -> higher realized winrate?
    order = np.argsort(p)
    q = len(p) // 5
    for i in range(5):
        idx = order[i*q:(i+1)*q]
        if len(idx):
            print(f"  quintile {i+1}: mean p={p[idx].mean():.2f}  realized winrate={y[cut:][idx].mean()*100:.1f}%")


if __name__ == "__main__":
    main()
