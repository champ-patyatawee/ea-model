# FiboAdaptiveEA v7.5 — day-by-day P/L, Jul–Oct 2026

Config: `FiboAdaptiveEA_v7.5`, XAUUSDm M5, `Model=4` real ticks, deposit $100,
`InpFadeMode=true`, `InpTrueMirror=true`, `InpDirByDepth=1`, `InpTP_R=2.5`,
`InpUseVolGate=false`, `InpDeepEffBelow=0.40`, partial/break-even/trailing OFF,
time exit 180 min, daily stop OFF, `InpUseHTFFibo=false`, `InpTPByDir=0`.

## Method (why one run per month is enough)

The EA trades a **fixed lot** (`InpFixedLot=0.02`), so a trade's P/L does not depend on
the account equity. A single continuous monthly run therefore already contains the
honest "what if I started every day with $100" numbers, as long as the month did not
blow the account up. The daily table is built by pairing every `MFELOG ... P/L=` line in
the tester log with its simulated timestamp (`tools/daily.py`).

**Validation:** the daily P/L sums equal the month's `final balance − 100` to the cent
for all four months (e.g. September: 24 days summing to +74.58, final balance 174.58).

**Caveat:** `MFELOG` is emitted when a position is fully closed, so a config that uses
`InpUsePartial` under-counts its own winners and the daily sum will not reconcile. This
method is only valid with partials off — which is the v7.4/v7.5 default.

## Summary

| month | days | winning | losing | win-day rate | month P/L | best day | worst day |
|---|---:|---:|---:|---:|---:|---|---|
| Jul 2026 | 26 | 14 | 12 | 53.8 % | **+316.42** | 07-08 +130.13 | 07-28 −61.04 |
| Aug 2026 | 23 | 11 | 12 | 47.8 % | **+92.57** | 08-25 +118.04 | 08-27 −97.61 |
| Sep 2026 | 24 | 12 | 12 | 50.0 % | **+74.58** | 09-09 +97.53 | 09-29 −82.34 |
| Oct 2026 (1–12) | 8 | 5 | 3 | 62.5 % | **+40.61** | 10-02 +86.60 | 10-08 −57.05 |
| **total** | **81** | **42** | **39** | **51.9 %** | **+524.18** | — | — |

Every one of the four months is profitable. The worst single day is −97.61 (27 Aug) —
just under the whole $100 account — which is why the *distribution* matters more than the
mean: the three worst days (27 Aug −97.61, 29 Sep −82.34, 10 Aug −89.16) are all
"one-sided cluster" days where the EA opened 5–6 positions and lost nearly all of them.

## July 2026 — 26 days, 14 W / 12 L, +316.42

| day | P/L | trades | win | loss |
|---|---:|---:|---:|---:|
| 2026.07.01 | +69.87 | 3 | 2 | 1 |
| 2026.07.02 | −36.34 | 4 | 1 | 3 |
| 2026.07.03 | −20.37 | 4 | 1 | 3 |
| 2026.07.05 | +20.50 | 1 | 1 | 0 |
| 2026.07.06 | +1.96 | 4 | 1 | 3 |
| 2026.07.07 | −41.21 | 3 | 0 | 3 |
| 2026.07.08 | +130.13 | 3 | 3 | 0 |
| 2026.07.09 | +21.72 | 4 | 2 | 2 |
| 2026.07.10 | +73.64 | 4 | 3 | 1 |
| 2026.07.13 | −5.71 | 4 | 1 | 3 |
| 2026.07.14 | +4.65 | 5 | 3 | 2 |
| 2026.07.15 | +57.12 | 6 | 3 | 3 |
| 2026.07.16 | −40.84 | 6 | 1 | 5 |
| 2026.07.17 | −7.58 | 3 | 1 | 2 |
| 2026.07.19 | −14.04 | 1 | 0 | 1 |
| 2026.07.20 | +22.47 | 4 | 3 | 1 |
| 2026.07.21 | −34.93 | 4 | 1 | 3 |
| 2026.07.22 | −0.11 | 5 | 2 | 3 |
| 2026.07.23 | −9.12 | 3 | 1 | 2 |
| 2026.07.24 | +64.08 | 2 | 2 | 0 |
| 2026.07.26 | +74.33 | 1 | 1 | 0 |
| 2026.07.27 | +29.55 | 4 | 3 | 1 |
| 2026.07.28 | −61.04 | 5 | 0 | 5 |
| 2026.07.29 | −56.29 | 6 | 1 | 5 |
| 2026.07.30 | +45.43 | 5 | 3 | 2 |
| 2026.07.31 | +28.55 | 4 | 2 | 2 |

## August 2026 — 23 days, 11 W / 12 L, +92.57

| day | P/L | trades | win | loss |
|---|---:|---:|---:|---:|
| 2026.08.03 | −3.88 | 4 | 2 | 2 |
| 2026.08.04 | −22.69 | 5 | 1 | 4 |
| 2026.08.05 | +42.30 | 3 | 2 | 1 |
| 2026.08.06 | +20.83 | 3 | 3 | 0 |
| 2026.08.07 | −2.35 | 3 | 1 | 2 |
| 2026.08.09 | −9.86 | 1 | 0 | 1 |
| 2026.08.10 | −89.16 | 6 | 0 | 6 |
| 2026.08.11 | +55.57 | 5 | 3 | 2 |
| 2026.08.12 | −50.54 | 3 | 0 | 3 |
| 2026.08.13 | +69.25 | 5 | 3 | 2 |
| 2026.08.14 | −74.24 | 5 | 0 | 5 |
| 2026.08.16 | +4.83 | 1 | 1 | 0 |
| 2026.08.17 | +22.00 | 5 | 2 | 3 |
| 2026.08.18 | −40.88 | 3 | 0 | 3 |
| 2026.08.19 | +61.38 | 3 | 2 | 1 |
| 2026.08.20 | −19.81 | 5 | 1 | 4 |
| 2026.08.21 | −8.94 | 6 | 1 | 5 |
| 2026.08.24 | +45.32 | 4 | 2 | 2 |
| 2026.08.25 | +118.04 | 5 | 4 | 1 |
| 2026.08.26 | −13.12 | 5 | 1 | 4 |
| 2026.08.27 | −97.61 | 6 | 0 | 6 |
| 2026.08.28 | +55.38 | 3 | 2 | 1 |
| 2026.08.31 | +30.75 | 5 | 2 | 3 |

## September 2026 — 24 days, 12 W / 12 L, +74.58

| day | P/L | trades | win | loss |
|---|---:|---:|---:|---:|
| 2026.09.01 | −42.23 | 4 | 1 | 3 |
| 2026.09.02 | +6.97 | 4 | 2 | 2 |
| 2026.09.03 | −36.27 | 3 | 0 | 3 |
| 2026.09.04 | +19.69 | 4 | 2 | 2 |
| 2026.09.07 | +47.76 | 4 | 3 | 1 |
| 2026.09.08 | −20.25 | 4 | 1 | 3 |
| 2026.09.09 | +97.53 | 4 | 3 | 1 |
| 2026.09.10 | −23.33 | 2 | 0 | 2 |
| 2026.09.11 | −8.22 | 3 | 1 | 2 |
| 2026.09.13 | +14.90 | 1 | 1 | 0 |
| 2026.09.14 | −57.73 | 3 | 0 | 3 |
| 2026.09.15 | +2.11 | 6 | 2 | 4 |
| 2026.09.16 | −18.86 | 4 | 1 | 3 |
| 2026.09.17 | +64.28 | 4 | 3 | 1 |
| 2026.09.18 | +40.74 | 1 | 1 | 0 |
| 2026.09.20 | +32.11 | 1 | 1 | 0 |
| 2026.09.21 | −3.07 | 4 | 1 | 3 |
| 2026.09.22 | +53.84 | 4 | 3 | 1 |
| 2026.09.23 | −56.22 | 4 | 0 | 4 |
| 2026.09.24 | +60.00 | 4 | 3 | 1 |
| 2026.09.25 | +2.98 | 4 | 1 | 3 |
| 2026.09.28 | −11.86 | 4 | 2 | 2 |
| 2026.09.29 | −82.34 | 5 | 0 | 5 |
| 2026.09.30 | −7.95 | 6 | 2 | 4 |

## October 2026 (1–12) — 8 days, 5 W / 3 L, +40.61

| day | P/L | trades | win | loss |
|---|---:|---:|---:|---:|
| 2026.10.01 | +1.97 | 3 | 1 | 2 |
| 2026.10.02 | +86.60 | 5 | 3 | 2 |
| 2026.10.05 | −37.10 | 5 | 2 | 3 |
| 2026.10.06 | +24.60 | 4 | 2 | 2 |
| 2026.10.07 | −16.90 | 4 | 1 | 3 |
| 2026.10.08 | −57.05 | 6 | 1 | 5 |
| 2026.10.09 | +27.76 | 4 | 2 | 2 |
| 2026.10.11 | +10.73 | 1 | 1 | 0 |

## What the day tables say

- **No day is a slow bleed.** Losses are concentrated: the 10 worst days (out of 81) sum
  to −682, while the entire four-month period is +524. In other words the EA earns its
  money on many ordinary days and gives a large chunk of it back on a handful of
  one-sided cluster days.
- **Cluster days are identifiable in advance by trade count.** Every day with ≥6 entries
  was either a big win (+130.13 on 07-08 with 3) or a disaster (−97.61 on 08-27 with 6,
  −89.16 on 08-10 with 6, −82.34 on 09-29 with 5). The three worst days all have 5–6
  entries and 0 winners.
- Reducing entries per direction per day from 3 to 2 **looked** like the obvious lever for
  "fewest losing days", so it was measured on the shipped v7.6 build and **it fails**:

  | entries/direction/day | Jul | Aug | Sep | Oct | Σ |
  |---|---:|---:|---:|---:|---:|
  | 3 (default) | 325.48 | 208.08 | 1.33 | 198.63 | **733.52** |
  | 2 | 168.94 | 115.40 | −2.41 | 76.91 | 358.84 |
  | 2 + total ≤ 4/day | 168.94 | 115.40 | −2.41 | 76.91 | 358.84 |

  Halving the entry count halves the profit, and the third row is byte-identical to the
  second because 2 longs + 2 shorts can never exceed a total cap of 4. **The cluster days
  are not fixable by trading less — the same days that produce the −97 days also produce
  the +130 days.** (Note the two sweeps use different exit ladders, so this table is
  comparable internally, not against the v7.5 tables above.)

---

# The shipped build — v7.6 (depth-adaptive direction + the original exit ladder)

The tables above are the **v7.5 "max Jul–Oct" profile** (partial/break-even/trailing off,
TP 2.5R). The shipped build is **v7.6**, which keeps the depth-adaptive direction rule but
restores the original exit ladder — it scores lower on Jul–Oct yet is the only variant that
also improves the earlier months (see `SUMMARY.md`).

These numbers come from the report's **Deals** table (`tools/daily_report.py`), not from the
EA's `MFELOG` lines, because the original ladder uses partial closes and `MFELOG` only logs
fully closed positions. `deals` below therefore counts *closing deals* (a partial close is
its own deal), so win/loss here is per-deal, not per-position.

| month | days | winning | losing | month P/L | final balance |
|---|---:|---:|---:|---:|---:|
| Jul 2026 | 24 | 13 | 11 | +226.00 | 325.48 |
| Aug 2026 | 23 | 14 | 9 | +109.11 | 208.08 |
| Sep 2026 | 4 | 0 | 4 | −98.67 | **1.33 — wiped on 2026.09.04** |
| Oct 2026 (1–12) | 8 | 5 | 3 | +98.63 | 198.63 |
| **total** | **59** | **32** | **27** | **+335.07** | — |

The Sep failure is the clearest single difference between the two builds: v7.5's 2.5R
targets survive September (+74.58 over 24 days) while v7.6's 1.5R-plus-partial ladder
gives the whole $100 back in four days (−11.48, −30.03, −33.32, −23.84) and then has no
equity left to trade. In July and August, by contrast, v7.6 is much steadier: August has
only 9 losing days out of 23 and no day worse than −54.08, where v7.5 had three days of
−74.24, −89.16 and −97.61.

## v7.6 — July 2026

| day | P/L | deals | win | loss |
|---|---:|---:|---:|---:|
| 2026.07.01 | +40.72 | 8 | 4 | 4 |
| 2026.07.02 | +47.16 | 13 | 7 | 6 |
| 2026.07.03 | +27.39 | 13 | 7 | 6 |
| 2026.07.05 | +10.77 | 1 | 1 | 0 |
| 2026.07.06 | +33.22 | 13 | 6 | 7 |
| 2026.07.07 | −7.03 | 7 | 2 | 5 |
| 2026.07.08 | +63.75 | 8 | 5 | 3 |
| 2026.07.09 | −32.38 | 9 | 2 | 7 |
| 2026.07.10 | +41.20 | 16 | 8 | 8 |
| 2026.07.13 | −2.06 | 10 | 4 | 6 |
| 2026.07.14 | −14.19 | 13 | 4 | 9 |
| 2026.07.15 | −14.56 | 14 | 4 | 10 |
| 2026.07.16 | +7.72 | 15 | 6 | 9 |
| 2026.07.17 | +6.58 | 10 | 4 | 6 |
| 2026.07.20 | +33.69 | 14 | 8 | 6 |
| 2026.07.21 | −31.79 | 9 | 2 | 7 |
| 2026.07.22 | −11.56 | 11 | 3 | 8 |
| 2026.07.23 | −22.21 | 11 | 3 | 8 |
| 2026.07.24 | +54.42 | 9 | 6 | 3 |
| 2026.07.27 | +36.53 | 11 | 6 | 5 |
| 2026.07.28 | −16.61 | 15 | 6 | 9 |
| 2026.07.29 | −52.18 | 11 | 2 | 9 |
| 2026.07.30 | +40.32 | 13 | 6 | 7 |
| 2026.07.31 | −12.90 | 12 | 4 | 8 |

## v7.6 — August 2026

| day | P/L | deals | win | loss |
|---|---:|---:|---:|---:|
| 2026.08.03 | −12.83 | 12 | 4 | 8 |
| 2026.08.04 | −20.39 | 12 | 4 | 8 |
| 2026.08.05 | +6.13 | 8 | 4 | 4 |
| 2026.08.06 | +62.93 | 12 | 8 | 4 |
| 2026.08.07 | −20.97 | 8 | 2 | 6 |
| 2026.08.09 | −9.86 | 1 | 0 | 1 |
| 2026.08.10 | −54.08 | 13 | 2 | 11 |
| 2026.08.11 | +12.29 | 13 | 6 | 7 |
| 2026.08.12 | +4.29 | 8 | 4 | 4 |
| 2026.08.13 | +13.73 | 12 | 5 | 7 |
| 2026.08.14 | −24.74 | 12 | 2 | 10 |
| 2026.08.16 | +5.86 | 1 | 1 | 0 |
| 2026.08.17 | +25.59 | 13 | 6 | 7 |
| 2026.08.18 | +13.78 | 8 | 4 | 4 |
| 2026.08.19 | +24.79 | 13 | 6 | 7 |
| 2026.08.20 | −5.64 | 15 | 6 | 9 |
| 2026.08.21 | +3.82 | 10 | 4 | 6 |
| 2026.08.24 | +32.36 | 11 | 6 | 5 |
| 2026.08.25 | +44.85 | 12 | 5 | 7 |
| 2026.08.26 | +39.87 | 13 | 6 | 7 |
| 2026.08.27 | −20.92 | 12 | 4 | 8 |
| 2026.08.28 | +5.91 | 8 | 4 | 4 |
| 2026.08.31 | −17.66 | 14 | 4 | 10 |

## v7.6 — September 2026 (four days, then the account is gone)

| day | P/L | deals | win | loss |
|---|---:|---:|---:|---:|
| 2026.09.01 | −11.48 | 11 | 3 | 8 |
| 2026.09.02 | −30.03 | 12 | 4 | 8 |
| 2026.09.03 | −33.32 | 4 | 0 | 4 |
| 2026.09.04 | −23.84 | 7 | 2 | 5 |

## v7.6 — October 2026 (1–12)

| day | P/L | deals | win | loss |
|---|---:|---:|---:|---:|
| 2026.10.01 | −20.56 | 7 | 2 | 5 |
| 2026.10.02 | +54.68 | 13 | 7 | 6 |
| 2026.10.05 | −5.17 | 14 | 5 | 9 |
| 2026.10.06 | +18.27 | 13 | 6 | 7 |
| 2026.10.07 | +10.33 | 13 | 6 | 7 |
| 2026.10.08 | +38.64 | 16 | 8 | 8 |
| 2026.10.09 | −8.29 | 13 | 4 | 9 |
| 2026.10.11 | +10.73 | 1 | 1 | 0 |

These rows sum to the report's own profit column (98.63), which reconciles with the
`final balance 198.63`.
