# FiboAdaptiveEA v6.1 — mode labels and 12-month results

## Setup that produced these numbers

| item | value |
|---|---|
| Expert | `FiboAdaptiveEA_v6.1` (compiled in container `mt5`, 0 errors) |
| Symbol / TF | `XAUUSDm` M5 |
| Server / account | Exness-MT5Trial7, account 434226308 |
| Period | 2025.10.01 – 2026.10.01, one optimization per calendar month |
| Model | `Model=0` (every tick) |
| Deposit | 100 USD per month (each month is an independent $100 account) |
| Leverage | 1:2000 |
| Grid | 48 optimizer passes per month × 12 months = 576 runs |

Grid runs reproduce the standalone runs exactly — e.g. the grid's 2026-08 FADE/deep/–/R1.5 = **−98.16** and 2026-09 = **+150.93**, identical to the separate single-config runs.

## How to read a mode label

`direction / profile / atr-band / TP-mode`

| token | parameter | meaning |
|---|---|---|
| `FADE` | `InpFadeMode=true`, `InpUseDualMode=false` | trade against the pullback |
| `CONT` | `InpFadeMode=false` | trade with the pullback (`dual` is inert here) |
| `DUAL` | `InpFadeMode=true`, `InpUseDualMode=true` | fade, but continue when H1 EMA trend agrees |
| `deep` | `InpUseDeepProfile=true` | deep zone 0.66–0.786 auto-trigger is allowed |
| `norm` | `InpUseDeepProfile=false` | always the standard 0.382–0.727 zone |
| `-` / `atr` | `InpUseATRAdaptiveZone` false / true | static band vs volatility-shifted band |
| `XTREME` | `InpTPMode=TP_AT_EXTREME` | TP at the impulse origin (distance varies with impulse size) |
| `MID` | `InpTPMode=TP_AT_MID` | **dead — never trades** |
| `R1.5` | `InpTPMode=TP_R_MULT` | TP = 1.5 × stop distance |

`norm` and `deep` are the two values of one boolean — they can never be combined.

## Month × direction, at default non-mode settings (deep, atr off, TP 1.5R)

| month | FADE | CONT | DUAL |
|---|---|---|---|
| 2025-10 | −100.84 | −102.11 | −105.07 |
| 2025-11 | **+453.59** | −103.37 | −104.45 |
| 2025-12 | **+245.60** | −98.51 | −104.46 |
| 2026-01 | −99.08 | **+107.81** | −103.83 |
| 2026-02 | −99.45 | −105.24 | **+164.03** |
| 2026-03 | −113.91 | −101.10 | −101.12 |
| 2026-04 | +23.63 | −5.95 | −100.84 |
| 2026-05 | **+406.37** | −109.43 | −100.01 |
| 2026-06 | +107.97 | −115.25 | −100.58 |
| 2026-07 | **+287.44** | −108.71 | −102.60 |
| 2026-08 | −98.16 | −74.01 | −13.11 |
| 2026-09 | **+150.93** | −102.06 | −102.97 |

12-month totals: FADE **+1164.09** (7/12 profitable) · CONT −917.93 (1/12) · DUAL −875.01 (1/12).
Losing cells are usually a wiped account, not a mild loss — across the whole grid 217 of the 259 negative cells are below −90 (the mildest are −4.84 to −5.95).

## Best combo of all 36 distinct combos, per month

| month | best combo | profit | PF | trades | equity DD |
|---|---|---|---|---|---|
| 2025-10 | CONT / norm / – / XTREME | +213.78 | 1.43 | 102 | 62.3% |
| 2025-11 | FADE / deep / – / R1.5 | +453.59 | 1.90 | 149 | 77.7% |
| 2025-12 | FADE / deep / – / R1.5 | +245.60 | 1.41 | 163 | 82.3% |
| 2026-01 | CONT / deep / atr / R1.5 | +338.87 | 1.61 | 127 | 51.3% |
| 2026-02 | DUAL / norm / atr / R1.5 | +238.86 | 1.32 | 109 | 36.4% |
| 2026-03 | DUAL / deep / – / XTREME | +234.87 | 1.54 | 72 | 24.9% |
| 2026-04 | FADE / norm / – / R1.5 | +136.37 | 1.16 | 147 | 51.3% |
| 2026-05 | FADE / deep / – / R1.5 | +406.37 | 1.66 | 145 | 21.5% |
| 2026-06 | CONT / norm / – / XTREME | +143.15 | 1.45 | 68 | 53.5% |
| 2026-07 | FADE / norm / – / R1.5 | +308.80 | 1.43 | 164 | 31.0% |
| 2026-08 | DUAL / norm / – / R1.5 | +120.08 | 1.17 | 142 | 58.5% |
| 2026-09 | FADE / deep / – / R1.5 | +150.93 | 1.22 | 132 | 76.3% |

The winner changes almost every month. Oracle (best combo per month, hindsight) = **+2991.27** vs **+1164.09** for the best fixed combo. The gap is the whole problem: the month-best mode is real but not knowable in advance.

## All combos that are net-positive over 12 months

| combo | 12-month total |
|---|---|
| FADE / deep / – / R1.5 (EA default) | **+1164.09** |
| FADE / deep / atr / R1.5 | +758.74 |
| FADE / norm / – / XTREME | +265.39 |
| FADE / norm / atr / XTREME | +217.70 |
| FADE / deep / – / XTREME | +198.17 |
| FADE / norm / – / R1.5 | +174.49 |
| FADE / norm / atr / R1.5 | +39.93 |
| FADE / deep / atr / XTREME | +35.95 |

8 of 36 — all FADE. No CONTINUE or DUAL variant is positive over the year.

## TP geometry statistics (over all 576 grid passes)

| TP mode | passes | passes with 0 trades | mean trades |
|---|---|---|---|
| `TP_AT_EXTREME` | 192 | 0 | 55 |
| `TP_AT_MID` | 192 | **192** | 0 |
| `TP_R_MULT` | 192 | 0 | 83 |

`TP_AT_MID` places the target at the impulse midpoint, which sits behind the entry, so every setup is rejected. Treat the TP axis as binary.

## Why the losing months wipe the account (payoff, not win rate)

From the standalone Model=0 runs of Aug/Sep 2026:

| run | trades | wins | avg win | avg loss | win rate | win rate needed | PF |
|---|---|---|---|---|---|---|---|
| 2026-08 FADE | 59 | 35 | +7.94 | −15.67 | 59.3% | 66.4% | 0.74 |
| 2026-08 CONT | 131 | 84 | +8.56 | −16.87 | 64.1% | 66.3% | 0.91 |
| 2026-09 FADE | 132 | 88 | +9.36 | −15.29 | 66.7% | 62.0% | 1.22 |
| 2026-09 CONT | 99 | 60 | +8.82 | −16.19 | 60.6% | 64.7% | 0.84 |

`avg loss` equals `RiskDistance × lot` exactly — losses are a clean −1.00R. But `avg win` is only ≈ **0.51R** even though TP sits at 1.5R, because `InpUsePartial` (50% at 1R), `InpUseBreakEven` and `InpUseTrailing` truncate winners while losers stay full size. Break-even therefore needs ~62–66% wins, and the EA lands within ±5% of that line every month — which is why the outcome flips month to month.

Compounding that, `InpFixedLot=0.02` on a $100 account risks roughly 10–25% per trade and does not scale down as equity falls, so a 3-loss streak ends the account (2026-08-14: three consecutive short stop-outs took the balance from 45.47 to 1.84 in one morning).

## Practical conclusions

- FADE is the only direction with a positive year; the EA defaults (`InpFadeMode=true`, `InpUseDeepProfile=true`, `InpTPMode=TP_R_MULT`) are already the best fixed combo measured.
- Chasing the per-month winning mode is overfitting — the winner rotates, and the EA header's own walk-forward test already found prior-month selection worse than a fixed set.
- The binding constraint is the ~0.5R payoff plus fixed-lot sizing, not the choice of fibo variant. Fix the exits (partial/BE/trailing) or the sizing before adding new modes.
