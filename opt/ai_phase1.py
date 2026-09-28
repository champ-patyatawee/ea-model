#!/usr/bin/env python3
"""Phase-1 AI: parse the v6.1 FEAT log lines -> dataset -> GBM, walk-forward AUC."""
import subprocess, re, os, csv
import run_bt as R

DOCKER, C, M = R.DOCKER, R.CONTAINER, R.M
PARAMS = {"InpMinReactionScore": 2.5, "InpTP_R": 1.5, "InpFixedLot": 0.02,
          "InpMaxEntriesPerDirPerDay": 3, "InpLogFeatures": "true",
          "InpUseRegimeFilter": "false", "InpUseATRAdaptiveZone": "false",
          "InpUseDualMode": "false", "InpUseHTFTrendFilter": "false",
          "InpUseDailyDirLock": "false", "InpRandomEntry": "false"}
PER = ("2025.01.01", "2026.09.24")

RF = re.compile(r"FEAT long=(\d) eff=([\d.\-]+) atrRatio=([\d.\-]+) rsi=([\d.\-]+) "
                r"h1slope=([\d.\-]+) d1dist=([\d.\-]+) m5dist=([\d.\-]+) mom=([\d.\-]+) "
                r"hour=(\d+) dow=(\d+) consecLoss=(\d+) dLong=(\d+) dShort=(\d+) spread=([\d.\-]+)")
RM = re.compile(r"MFELOG PROF=(-?\d+) MFE_R=([\d.\-]+) MAE_R=([\d.\-]+) P/L=([\d.\-]+)")


def grab():
    subprocess.run([DOCKER, "exec", C, "bash", "-c", f"rm -f '{M}/Tester/logs/'*.log"], check=False)
    R.run(R.build_ini(PER[0], PER[1], PARAMS, deposit=10000))
    return subprocess.run([DOCKER, "exec", C, "bash", "-c",
                           f"iconv -f UTF-16LE -t UTF-8 '{M}/Tester/logs/'*.log 2>/dev/null | "
                           f"grep -E 'FEAT |MFELOG'"], capture_output=True, text=True).stdout


def main():
    txt = grab()
    rows = []; pend = None
    for ln in txt.splitlines():
        f = RF.search(ln)
        if f:
            pend = dict(long=int(f.group(1)), eff=float(f.group(2)), atrRatio=float(f.group(3)),
                        rsi=float(f.group(4)), h1slope=float(f.group(5)), d1dist=float(f.group(6)),
                        m5dist=float(f.group(7)), mom=float(f.group(8)), hour=int(f.group(9)),
                        dow=int(f.group(10)), consecLoss=int(f.group(11)), dLong=int(f.group(12)),
                        dShort=int(f.group(13)), spread=float(f.group(14)))
            continue
        m = RM.search(ln)
        if m and pend:
            pend.update(mfe=float(m.group(2)), mae=float(m.group(3)), pl=float(m.group(4)),
                        win=1 if float(m.group(4)) > 0 else 0)
            rows.append(pend); pend = None
    print("rows:", len(rows))
    if len(rows) < 200:
        print("too few rows"); return
    with open(os.path.join(R.HOST, "ai_feat.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print("winrate %.1f%%" % (100*sum(r["win"] for r in rows)/len(rows)))

    import numpy as np
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import roc_auc_score
    feats = ["eff", "atrRatio", "rsi", "h1slope", "d1dist", "m5dist", "mom",
             "hour", "dow", "consecLoss", "dLong", "dShort", "spread", "long"]
    X = np.array([[r[k] for k in feats] for r in rows], dtype=float)
    y = np.array([r["win"] for r in rows])
    cut = int(len(rows)*0.7)
    clf = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_depth=3,
                                         l2_regularization=1.0, random_state=42)
    clf.fit(X[:cut], y[:cut])
    p = clf.predict_proba(X[cut:])[:, 1]
    print("OOS AUC = %.3f" % roc_auc_score(y[cut:], p))
    order = np.argsort(p); q = len(p)//5
    for i in range(5):
        idx = order[i*q:(i+1)*q]
        if len(idx):
            print("  quintile %d: mean p=%.2f realized winrate=%.1f%%" %
                  (i+1, p[idx].mean(), y[cut:][idx].mean()*100))
    # permutation importance (rough)
    base = roc_auc_score(y[cut:], p)
    rng = np.random.default_rng(0)
    print("feature importance (AUC drop):")
    imps = []
    for j, k in enumerate(feats):
        Xp = X[cut:].copy(); rng.shuffle(Xp[:, j])
        imps.append((roc_auc_score(y[cut:], clf.predict_proba(Xp)[:, 1]), k))
    for v, k in sorted(imps):
        print(f"  {k:12s} auc_with_shuffle={v:.3f} (drop={base-v:+.3f})")


if __name__ == "__main__":
    main()
