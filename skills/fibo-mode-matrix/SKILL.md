---
name: fibo-mode-matrix
description: FiboAdaptiveEA (XAUUSDm M5) mode inventory — fade/continue/dual direction, deep profile, ATR adaptive band, TP geometry — with the 12-month month-by-month backtest matrix and the exact MT5 optimizer config used to produce it
license: MIT
compatibility: opencode
metadata:
  audience: developers
---

## What I do

- Enumerate every "fibo mode" switch in `FiboAdaptiveEA_v6.*` and what each one actually changes in the trade decision
- Report the month-by-month backtest matrix (2025.10 – 2026.09, $100 per month, XAUUSDm M5, Exness-MT5Trial7, every tick) across all mode combinations
- Record the exact optimizer `.ini` config, the MT5 optimizer semantics that silently corrupt a grid, and the run procedure, so the matrix can be reproduced or extended

## When to use me

- Asked "which fibo mode wins month X", or choosing/defending a mode variant
- About to propose a *new* fibo mode — check here first for what already exists and what was already measured
- Re-running or extending the mode matrix, or writing a similar parameter grid for this EA

## Mode inventory (v6.1 — same 5 switches in v4.90, v5.0, v6.0)

| axis | input | default | values |
|---|---|---|---|
| direction | `InpFadeMode` | `true` | `true` = FADE (trade against the pullback) · `false` = CONTINUE |
| dual | `InpUseDualMode` | `false` | when on: fade by default, but switch to continuation if the H1 EMA trend agrees with the setup |
| profile | `InpUseDeepProfile` | `true` | on = auto-switch to the deep zone 0.66–0.786 (SL 2.0 ATR) when efficiency < 0.50, atrRatio > 1.50, or the zone was touched ≥ 3×; off = always 0.382–0.727 (SL 1.75 ATR) |
| ATR band | `InpUseATRAdaptiveZone` | `false` | shift the retracement band by `(atrRatio − 1) × 0.10` |
| TP geometry | `InpTPMode` | `TP_R_MULT` | `TP_AT_EXTREME` (0) impulse origin · `TP_AT_MID` (1) — **never trades, dead** · `TP_R_MULT` (2) = `InpTP_R` × stop distance |

Sweep size: 2 × 2 × 2 × 2 × 3 = **48 cells**, but only **36 distinct** — `InpUseDualMode` is inert when `InpFadeMode=false`, so those rows duplicate.

Not modes, but they reshape the fibo or gate which setups trade: geometry (`InpEntryFibMin/Max`, `InpDeepFibMin/Max`, `InpDeepEffBelow`, `InpDeepVolAbove`, `InpDeepTouchMin`, `InpMaxTouches`, `InpATRZoneShift`, `InpSL_ATR`, `InpDeepSL_ATR`, `InpTP_R`) and filters (`InpUseFadeRegimeGate`, `InpUseVolGate`, `InpRequireBOS`, `InpRequireStructure`, `InpRequireReactionClose`, `InpUseHTFTrendFilter`, `InpUseRegimeFilter`, `InpUseDailyDirLock`).

## Headline results (12 months, each month starts from $100)

At default non-mode settings (deep profile on, ATR band off, TP = 1.5R):

| direction | 12-month total | profitable months |
|---|---|---|
| **FADE** (default) | **+1164.09** | 7 / 12 |
| CONTINUE | −917.93 | 1 / 12 |
| DUAL | −875.01 | 1 / 12 |

**8 of the 36 distinct combos are net-positive over the year, and all 8 are FADE.** No CONTINUE or DUAL combination survives the year.

Losing runs are usually catastrophic, not mild: 217 of the 259 negative grid cells land below −90, i.e. the $100 account is wiped (the mildest losers are −4.84 to −5.95). The best fixed combo still averages ~78% equity drawdown.

The monthly winner keeps rotating (CONT in 2025-10, FADE through 2025-11/12, CONT in 2026-01, DUAL in 2026-02/03, CONT in 2026-06, DUAL in 2026-08 …). An oracle that picks the best combo each month would have made +2991.27 versus +1164.09 for the best fixed combo — the month-best mode is real but not predictable, matching the EA header's own walk-forward finding.

## References

- `references/modes-and-results.md` — the full month × mode tables, the best combo per month, TP-mode statistics, and the payoff/sizing analysis that explains the wipeouts
- `references/optimizer-config.md` — the complete `[TesterInputs]` template and the MT5 optimizer rules that matter (range syntax, parameter persistence, run procedure, failure modes)
- `references/fibo_mode_matrix.csv` — raw 576-row grid: `month,direction,dual,profile,atr_band,tp_mode,profit,profit_factor,trades,equity_dd_pct`

## Gotchas that silently break a grid

- **The optimizer persists parameters per expert.** A parameter not mentioned in `[TesterInputs]` keeps the range from a previous optimization run, and even writing `InpTP_R=1.50` does *not* clear it. Pin every input as `Name=value||value||0||value||N`; the sweep axes use `base||start||step||stop||Y`.
- **Boolean and enum ranges work numerically**: `InpFadeMode=true||0||1||1||Y` yields false/true; `InpTPMode=2||0||1||2||Y` yields 0/1/2.
- **`ToDate` is exclusive at 00:00** — for a full month set `ToDate` to the first day of the *next* month.
- **`TP_AT_MID` never opens a trade** (0 trades in all 192 passes); treat the TP axis as 2 values.
- **Stop the running terminal before a headless run** and never let the kill pattern match your own shell — `pkill -f 'terminal6[4]\.exe'` is safe, `pkill -f 'terminal64.exe'` kills the shell running it.
- **Background jobs die with `docker exec`**, and `docker exec -d` breaks MT5 startup. Run the sweep in the foreground inside one `docker exec` (≈2 min per month at Model=0), and `docker restart mt5` afterwards to bring the VNC terminal back.
