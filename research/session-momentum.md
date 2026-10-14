# Session-anchored edges on XAUUSD: what survives contact with our own data

Challenged to stop tuning the impulse basket and go find out what actually has
an edge, I read the two documented intraday effects and tested both on the same
3.8-year M5 dump the impulse probe produced (267,759 bars, 2023.01.03 →
2026.10.13, 975 full days). Everything below is measured, not asserted, and all
of it costs nothing to reproduce:

```bash
python3 tools/session_probe.py /tmp/impulse_probe.csv 8 1     # anchor = 08:00, 1h window
```

Cost reference: 0.25 $/oz round trip (real-tick measurement, see
`research/impulse-basket.md`).

## The three candidates, head to head

| entry idea | per-trade edge | vs cost | verdict |
|---|---:|---:|---|
| bar-relative impulse, continuation, h=4 | +0.09…+0.12 $/oz | **0.3–0.7 ×** | dead — cannot pay for itself |
| ORB: break the 08:00–09:00 range, stop at the other end, exit at the close | +0.02 $/oz, +0.06 R (t 0.6) | 0.1 × | dead on gold |
| ORB anchored at 13:00 (US data) | +0.49 $/oz, +0.05 R (t 1.4) | 2.0 × | noise |
| **session momentum: direction of the first hour after 08:00, hold to the close** | **+2.78 $/oz (t 2.45)**, +2.53 net | **10 ×** | alive — but see below |

The literature behind that last row: Gao, Han, Li & Zhou, *Market intraday
momentum*, Journal of Financial Economics 130(2), 2018 (working paper: “Intraday
Momentum: The First Half-Hour Return Predicts the Last Half-Hour Return”, SSRN
2440866) — the first half-hour return of the session predicts the last
half-hour return across 15+ markets and is stronger on high-volume/high-vol
days. The ORB row is Zarattini & Aziz, *Can Day Trading Really Be Profitable?*
(SSRN 4416622) and its 2024 follow-up across ~7,000 US stocks: break the first
N-minute range, stop at the far side of the range, flat at the close.

## The session-momentum trade, in full

Rule measured: at 09:00 server (end of the 08:00–09:00 window) enter in the
direction of that window's return; exit at the day's last bar. One round trip
per day. n=973 days.

| | $/oz |
|---|---:|
| mean gross / net of 0.25 cost | +2.783 / **+2.533** |
| win rate / median | 52.1 % / +0.81 |
| p05 / p95 | −46.9 / +52.9 |
| worst day / best day | **−148.0 / +225.8** |
| median adverse excursion before the close | **−12.9** |
| p05 adverse excursion | −64.3 |
| worst adverse excursion | −190.0 |

Year by year it is **not stable**:

| year | n | mean $/oz | t | win % |
|---|---:|---:|---:|---:|
| 2023 | 255 | +0.75 | +0.83 | 54.1 |
| 2024 | 259 | **−1.75** | −1.50 | 45.2 |
| 2025 | 257 | +4.09 | +2.02 | 54.9 |
| 2026 | 202 | +9.49 | +2.15 | 55.0 |
| first half | 486 | −0.11 | −0.15 | 50.0 |
| second half | 487 | +5.67 | +2.65 | 54.2 |

## The result that decides the design: a stop kills it

Enter at 09:00 in the first hour's direction, exit at the close, stop at a
fixed distance below the entry:

| stop | mean net $/oz | t | win % | stopped out |
|---:|---:|---:|---:|---:|
| none | **+2.53** | +2.23 | 51.5 | 0 % |
| 20 $/oz | +0.96 | +1.15 | 44.2 | 64 % |
| 10 $/oz (≈ 1× H1 ATR now) | +0.36 | +0.53 | 32.9 | 79 % |
| 5 $/oz | +0.03 | +0.05 | 19.8 | 89 % |
| stop = 1.0 × the first-hour move | **−2.66** | **−6.3** | 6.2 | — |

The trade spends most of the day in drawdown (median adverse excursion is
−$12.9/oz against a +$0.8 median close) and is paid by the tail of the days
that never come back. **The edge exists only in the version that refuses a
stop — which is the same property that kills the account.** That is the same
conclusion the impulse-basket study reached from the other direction (there the
cost ate the edge; here the variance does).

## What this means for sizing, and what to build next

At 0.01 lots (1 oz, the broker minimum) on $1,000: expected +$2.53/day,
~250 trading days ≈ +$630/yr, worst single day −$148 (−15 %), 1-in-20 day
−$47 (−4.7 %), no swap (flat before the rollover), no grid, no martingale,
one round trip a day. At 0.02 lots the worst day is −30 % of the account.

That is a buildable, measurable candidate — and the honest caveats are the year
table above (2024 was a losing year) and the fact that a t of ~2.2 on 973 trades
concentrated in two of four years does not clear the bar for "proven".

Next steps, in the order I would do them:

1. Build `SessionMomentumEA` (1 trade/day, entry 09:00, exit on the close,
   optional signal-strength filter `|first hour| ≥ x × ATR`) and score it with
   the existing harness — 1,157 rolling 21-day runs at $1,000, EV/run and ruin %
   exactly like `research/impulse-basket.md`.
2. Test the **regime gate** implied by the year table (2024 absent, 2025-26
   strong): is the effect conditional on high gold volatility / a trending H1?
   If yes, the 2024 hole is a feature and the filter is legitimate.
3. Re-test both papers the way the papers do it — on a **universe**, not one
   symbol. The earlier Fibonacci research in this repo hit the same wall
   (`research/fibo-web-research.md`: the 61.8 % signal earned 6.5 %/yr on BTC
   alone and 77.8 %/yr across the top-50 assets). One instrument is the
   standing problem with every result in this repo.
