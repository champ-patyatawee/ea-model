#!/usr/bin/env python3
"""Daily-budget simulation: run fixed-lot backtests, extract daily P/L,
report distribution stats for the '$100/day budget' model."""
import statistics as st
import run_bt as R

# lots ~ per-trade $ risk at SL 1.75 ATR on XAUUSDm (0.01 lot ~ $6-10 risk)
LOTS = [0.01, 0.02, 0.03, 0.04]
PERIODS = [
    ("train", "2025.01.01", "2026.07.01"),
    ("oos", "2026.07.01", "2026.09.18"),
]


def stats(daily):
    vals = sorted(daily.values())
    n = len(vals)
    if n == 0:
        return None
    wins10 = sum(1 for v in vals if v >= 10)
    wins20 = sum(1 for v in vals if v >= 20)
    hit100 = sum(1 for v in vals if v <= -100)
    neg50 = sum(1 for v in vals if v <= -50)
    # longest losing streak (days with negative)
    streak = best = 0
    for k in sorted(daily):
        if daily[k] < 0:
            streak += 1; best = max(best, streak)
        else:
            streak = 0
    return dict(days=n, mean=round(st.mean(vals), 2),
                median=round(st.median(vals), 2),
                total=round(sum(vals), 2),
                pos_days=sum(1 for v in vals if v > 0),
                ge10=wins10, ge20=wins20,
                le_m100=hit100, le_m50=neg50,
                worst=round(min(vals), 2), best=round(max(vals), 2),
                loss_streak=best)


print("lot | period | days | mean$ | median$ | total$ | pos% | >=$10 | >=$20 | <=-$50 | <=-$100 | worst | best | streak")
for lot in LOTS:
    for name, d1, d2 in PERIODS:
        ini = R.build_ini(d1, d2, {"InpFixedLot": lot}, deposit=10000)
        try:
            R.run(ini)
            daily = R.daily_pnl()
            s = stats(daily)
        except Exception as e:
            print("ERR", lot, name, repr(e), flush=True)
            continue
        if not s:
            print(lot, name, "no days"); continue
        print(f"{lot:.2f} | {name} | {s['days']} | {s['mean']} | {s['median']} | "
              f"{s['total']} | {100*s['pos_days']//s['days']}% | {s['ge10']} | "
              f"{s['ge20']} | {s['le_m50']} | {s['le_m100']} | {s['worst']} | "
              f"{s['best']} | {s['loss_streak']}", flush=True)
