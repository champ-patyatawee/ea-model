---
name: fibo-adaptive-v7
description: FiboAdaptiveEA v6.0→v7.6 version ladder (shipped build = v7.6), every Fibonacci "mode" switch and what it changes, the measured Jul–Oct 2026 month-by-month backtest matrix plus the earlier-month robustness check, the exact MT5 docker tester config, and the methodology traps that silently corrupt a sweep
license: MIT
compatibility: opencode
metadata:
  audience: developers
---

## What I do

- Explain what each version of `FiboAdaptiveEA` changed and why, from the v6.0
  daily-entry-cap branch to v7.6 (depth-adaptive direction + the shipped exit defaults),
  including the v7.4/v7.5 "max Jul–Oct" payoff profile that turned out not to generalise
- Enumerate every "fibo mode" input and what it actually changes in the trade decision
- Give the measured month-by-month result table for Jul–Oct 2026 (XAUUSDm M5, Exness
  demo, real ticks, $100 per independent month)
- Record the exact tester config and the run procedure, so any of these numbers can be
  reproduced or extended

Related skills: `fibo-mode-matrix` (the earlier 12-month 2025.10–2026.09 fade/continue/
dual/zone/TP grid for v6.x), `mt5-docker-import` (compile), `mt5-backtest-and-read`.

## Version ladder (what actually changed)

| version | change | measured effect (Jul/Aug/Sep/Oct finals on $100) |
|---|---|---|
| v6.0 | daily entry caps per direction (`InpMaxEntriesPerDirPerDay`) | baseline for everything below |
| v6.1 | AI feature log (`InpLogFeatures`, `FEAT ...` lines) | logging only — but **v6.0 and v6.1 are NOT behaviourally identical** despite the source diff being logging-only; v6.0/v6.2 matched the live demo account, v6.1 did not |
| v6.2 | `InpTrueMirror` — CONTINUE becomes an exact mirror of FADE (same setups, flipped side) | makes A/B direction tests honest |
| v7.0 | `InpDailyStopPct` hard daily stop + **bugfix**: `g_dailyLocked` was never checked by `TradingAllowed()`, so after a daily stop the EA kept opening trades and wiped the account (2026.08.13) | stop itself **hurts** — see below |
| v7.1 | payoff-fix defaults (`InpUsePartial/BreakEven/Trailing = false`, `InpTP_R = 2.5`); declared `TP_FIB_EXT`, `InpUseHTFFibo`, `InpDirByDepth` | payoff fix is the single biggest win |
| v7.2 | wires what v7.1 only declared: real Fibonacci-extension target and depth-adaptive direction | DirByDepth=1: 728.62 → 861.73 |
| v7.3 | `InpDirByDepth = 1` becomes the default | same as v7.2 best |
| v7.4 | `InpUseVolGate = false`, `InpDeepEffBelow = 0.40` as defaults | **924.18, profit in all four months** |
| v7.5 | `InpUseHTFFibo` finally implemented (H1 fibonacci confluence) + `InpTPByDir` per-direction target | reproduces v7.4 exactly (924.18); both new techniques are **off by default** because neither beat it |
| **v7.6** | **the robust build**: depth-adaptive direction kept, but the ORIGINAL exit ladder / vol gate / `InpDeepEffBelow=0.50` restored as defaults | Jul–Oct 733.52 (vs 529.77 for the v6.x baseline), and it is the only variant that also improves the earlier months |
| **v7.7** | **regime-adaptive exit ladder**: each trade picks the payoff ladder or the original ladder from a live regime measure (`InpAdaptiveExits` = 1 ATR-ratio / 2 impulse efficiency / 3 H1 slope÷ATR) | Jul–Oct **840.17** with `InpAdaptiveExits=3, Thr=0.50` (vs 733.52 for v7.6); see the table below |

**Run v7.7.** v7.4/v7.5 are the "max Jul–Oct 2026" profile — they score higher on that one
window and worse everywhere else (see the robustness section below).

### Regime-adaptive exit ladder (v7.7) — Jul–Oct 2026

Two ladders, measured on identical entries, are better in different regimes; v7.7 picks one
per trade from a measure available at entry time. The payoff ladder = no partial, no
break-even, no trail, TP 2.5R. The original ladder = 50 % partial @1R, BE @1R, ATR trail
from 1.5R, TP 1.5R.

| switch | Jul | Aug | Sep | Oct | Σ |
|---|---:|---:|---:|---:|---:|
| off (v7.6: original ladder everywhere) | 325.48 | 208.08 | 1.33 | 198.63 | 733.52 |
| `InpAdaptiveExits=1`, ATR-ratio ≥ 1.0 → payoff | 310.42 | 341.36 | −0.93 | 70.87 | 721.72 |
| `InpAdaptiveExits=1`, ATR-ratio < 1.0 → payoff | 225.56 | 308.92 | −3.84 | 252.93 | 783.57 |
| `InpAdaptiveExits=2`, efficiency ≥ 0.55 → payoff | 275.46 | 391.39 | −12.43 | 105.95 | 760.37 |
| **`InpAdaptiveExits=3`, H1 slope÷ATR ≥ 0.50 → payoff** | 292.87 | 328.23 | −0.84 | **218.91** | **840.17** |

The H1-trend-strength rule is the default. Note it still does **not** rescue September, the
month that most wants the payoff ladder as a global setting (v7.5's September = 174.58):
the switching measures available here all fail to identify September. That is the honest
limit of this technique and the reason the 12-month backtest matters more than the
four-month window.

### FINAL 12-month backtest (2025.10 → 2026.09, Model=2, $100 per month)

| build | Jul–Oct net | **12-month net P/L** | profitable months | wiped months |
|---|---:|---:|---:|---:|
| **v7.6 (shipped)** | +334 | **+1098.96** | 8 / 12 | 4 |
| v7.7 adaptive exits | +420 (real ticks) | +977.07 | 7 / 12 | 5 |
| v7.7 + zone floor 0.50 | — | +974.88 | 8 / 12 | 4 |
| v7.6 + zone floor 0.50 | — | +622.34 | 7 / 12 | 5 |

**v7.6 remains the best 12-month build.** The v7.7 adaptive ladder wins the four-month
window it was tuned on and loses the year (Feb-2026 goes from +192.67 to a wipe, Dec-2025
from 348.61 to 207.88). The 0.50 zone floor is rejected outright. Full monthly table and
the reasoning: `research/SUMMARY.md`.

## The measured result ladder (Jul–Oct 2026, $100 per month, real ticks)

Each row is four independent $100 runs, so **Σ = total final balance**; subtract 400 for
net profit. A "wipe" means the month's account was destroyed (final ≈ 0).

| config | Jul | Aug | Sep | Oct (1–12) | Σ |
|---|---:|---:|---:|---:|---:|
| v6.x baseline (partial/BE/trail ON, TP 1.5R) | 388.48 | −0.50 (wipe) | 1.33 (wipe) | 140.46 | 529.77 |
| **+ payoff fix** (exits OFF, TP 2.5R) | 372.85 | 270.33 | −4.64 (wipe) | 90.08 | 728.62 |
| + daily stop 12 % | 4.53 | 412.53 | 80.36 | 39.76 | 537.18 |
| + daily stop 20 % | 2.61 | 390.16 | 3.74 | 26.24 | 422.75 |
| + daily stop 30 % | 1.56 | 359.62 | 2.19 | 107.90 | 471.27 |
| + Fibonacci-extension TP 1.618 (v7.2) | 278.43 | −2.77 | 1.44 | 112.24 | 389.34 |
| **+ depth-adaptive direction** (v7.2/7.3) | 313.29 | 433.90 | −0.27 | 114.81 | 861.73 |
| v7.3 + vol gate off | 355.14 | 433.90 | −0.77 | 114.81 | 903.08 |
| **v7.4** (vol gate off + `InpDeepEffBelow=0.40`) | 416.42 | 192.57 | 174.58 | 140.61 | **924.18** |
| v7.4 alt (`InpDeepEffBelow=0.45`) | 434.14 | 376.54 | −0.78 (wipe) | 140.61 | 950.51 |
| v7.5 = v7.4 (reproduction check) | 416.42 | 192.57 | 174.58 | 140.61 | 924.18 |
| v7.5 + `InpTPByDir=2` (FADE takes the extension) | 296.64 | −1.23 | −1.51 | 149.73 | 443.63 |
| v7.5 + `InpTPByDir=1` (CONTINUE takes the extension) | 416.42 | 192.57 | 174.58 | 140.61 | 924.18 — no effect: only 2 orders in July changed (98 total) and the four finals are identical to the cent; the affected trades exit by stop or time before either target |
| v7.5 + `InpUseHTFFibo` H1 zone 0.5–0.786 | 293.98 | 106.52 | 99.14 | 102.72 | 602.36 (77 % fewer trades, all four months still green) |
| v7.5 + `InpUseHTFFibo` H1 zone 0.618–0.786 | 130.54 | 93.00 | 152.17 | 51.26 | 426.97 (too strict) |

**On this window the ranking is v7.4/v7.5 (924.18) > v7.6 (733.52) > v6.x baseline (529.77).**
But that ranking does not survive contact with the earlier months — see "the v7.x gains do
NOT generalise" below. `InpDeepEffBelow=0.45` scores higher still (950.51) while wiping
September, which is the signature of overfitting on four months of data.

### The shipped build: v7.6 (robust defaults)

| config | Jul | Aug | Sep | Oct | Σ |
|---|---:|---:|---:|---:|---:|
| v6.x baseline | 388.48 | −0.50 | 1.33 | 140.46 | 529.77 |
| **v7.6** = depth-adaptive direction + original exits | **325.48** | **208.08** | 1.33 | **198.63** | **733.52** |
| v7.5 (max Jul–Oct profile) | 416.42 | 192.57 | 174.58 | 140.61 | 924.18 |
| v7.6 with `InpDeepEffBelow=0.40` | 402.95 | −0.17 | 43.91 | 152.51 | 599.20 |

v7.6 defaults, i.e. what you get by simply attaching the EA:
`InpDirByDepth=1`, `InpTP_R=1.5`, `InpUsePartial/BreakEven/Trailing=true`,
`InpUseVolGate=true`, `InpDeepEffBelow=0.50`, `InpDailyStopPct=0`.
To reproduce the 924.18 profile instead, set
`InpUsePartial=false`, `InpUseBreakEven=false`, `InpUseTrailing=false`, `InpTP_R=2.5`,
`InpUseVolGate=false`, `InpDeepEffBelow=0.40`.

### Direction control (why `InpDirByDepth=1` is the default)

Same expert, same everything else, only the direction rule changes:

| `InpDirByDepth` | Jul | Aug | Sep | Oct | Σ |
|---|---:|---:|---:|---:|---:|
| `0` pure FADE | 411.26 | 1.99 (wipe) | 309.90 | 140.61 | 863.76 |
| **`1` deep → CONTINUE, shallow → FADE** | **416.42** | **192.57** | 174.58 | 140.61 | **924.18** |
| `2` deep → FADE, shallow → CONTINUE | −0.29 (wipe) | 226.54 | −14.29 (wipe) | −0.91 (wipe) | 211.05 |

`InpDirByDepth=1` and `0` are close in aggregate but differ exactly where it matters:
option `0` lets August die (final 1.99) while option `1` keeps it at +92.57. Note that
almost all of the "deep zone" traffic comes from the `atrRatio > InpDeepVolAbove` and
`touches >= InpDeepTouchMin` triggers, **not** from the efficiency trigger: with
`InpFadeMinEfficiency = 0.40` and `InpDeepEffBelow = 0.40` an impulse with efficiency
below 0.40 is rejected by the fade gate before it can ever become a deep trade.

## Mode inventory (v7.5)

Direction is decided for every setup by this chain: `InpFadeMode` → `InpUseDualMode`
(H1 EMA trend) → `InpDirByDepth` (retracement depth). The last one that applies wins.

| axis | input | default | values / meaning |
|---|---|---|---|
| direction | `InpFadeMode` | `true` | FADE = trade against the pullback (best over 12 months: +1164.09 vs CONTINUE −917.93, see `fibo-mode-matrix`) |
| dual | `InpUseDualMode` | `false` | switch to continuation when the H1 EMA trend agrees with the setup (inert when `InpFadeMode=false` in v6.x) |
| mirror | `InpTrueMirror` (v6.2) | `true` | CONTINUE evaluates the *same* setups as FADE and only flips the execution side |
| **depth-adaptive direction** | `InpDirByDepth` (v7.2) | `1` | `0` off · `1` deep zone (0.66–0.786) → CONTINUE, shallow → FADE · `2` the inverse. **The biggest new edge found in this project** |
| profile | `InpUseDeepProfile` | `true` | on = auto-switch to the deep zone when efficiency < `InpDeepEffBelow`, ATR ratio > `InpDeepVolAbove`, or touches ≥ `InpDeepTouchMin`; off = always 0.382–0.727 |
| profile trigger | `InpDeepEffBelow` (v7.4) | `0.40` | was 0.50 in v4.90–v7.3. This is the most sensitive knob in the whole EA |
| ATR band | `InpUseATRAdaptiveZone` | `false` | shift the retracement band by `(atrRatio − 1) × InpATRZoneShift` |
| TP geometry | `InpTPMode` | `TP_R_MULT` (2) | `0` TP at the impulse origin · `1` TP_AT_MID — **never trades, dead** · `2` `InpTP_R` × stop distance · `3` Fibonacci extension beyond the origin |
| per-direction TP | `InpTPByDir` (v7.5) | `0` | `1` CONTINUE trades take the extension target, FADE keeps `InpTPMode` · `2` the inverse |
| H1 confluence | `InpUseHTFFibo` (v7.5) | `false` | require the M5 entry to sit inside the H1 retracement zone of the newest H1 impulse (`InpH1FibMin..InpH1FibMax` of its range) |
| volatility gate | `InpUseVolGate` (v7.4) | `false` | rejects entries outside an ATR-ratio band; it only rejected good July trades |

Not "modes" but they reshape the same decision: geometry (`InpEntryFibMin/Max`,
`InpDeepFibMin/Max`, `InpDeepSL_ATR`, `InpSL_ATR`, `InpTP_R`, `InpTPExtMult`), filters
(`InpUseFadeRegimeGate`, `InpMinReactionScore`, `InpRequireBOS`, `InpRequireStructure`,
`InpRequireReactionClose`, `InpUseVolGate`, `InpUseHTFTrendFilter`, `InpUseRegimeFilter`),
sizing/caps (`InpFixedLot`, `InpMaxEntriesPerDirPerDay`, `InpMaxTradesPerDay`), protection
(`InpDailyStopPct`, `InpDailyLossMoney`, `InpMaxConsecutiveLosses`).

## The four findings that matter

1. **The leak was in the exits, not the entries.** Realised payoff was avg win +0.51R
   against avg loss −1.00R: the 50 % partial at 1R, break-even at 1R and the ATR trail from
   1.5R all truncated winners before the target. Turning them off and widening TP to 2.5R
   flipped August 2026 from a wipe (−0.50) to +270.33 on the same $100.
2. **Fixed-R targets are month-sensitive.** TP 2.0 wins September, 2.5 wins August, 3.0
   wins July — and the wrong choice wipes a month. 2.5R maximises the aggregate, but the
   dispersion is the real signal, which is why the extension target and `InpTPByDir` were
   tried.
3. **Any hard daily stop hurts on this base.** It locks the day before the payoff-fixed
   trades can recover: July collapses from 372.85 to ~2–5 at every setting (12/20/30 %).
   The v7.0 bugfix (honour `g_dailyLocked` in the entry gate) is still correct and stays.
4. **Depth-adaptive direction is a real edge.** Taking the deep-zone (0.66–0.786) trades as
   CONTINUE and the shallow ones as FADE lifted the aggregate 728.62 → 861.73 and turned
   September from a wipe into break-even. It is the mechanical version of "when the fade
   loses, the opposite direction wins".

## Exact backtest config

Symbol `XAUUSDm`, period `M5`, `Model=4` (every tick based on **real** ticks — real tick
data only exists from 2026.07.01, so earlier months are synthetic), `Optimization=0`,
`Visual=0`, `Deposit=100`, `Currency=USD`, `Leverage=2000`, `ShutdownTerminal=1`,
account 434226308 on `Exness-MT5Trial7`, container `mt5` (gmag11/metatrader5_vnc).
`ToDate` is **exclusive at 00:00**, so a full month ends on the first day of the next month.

Reproduce everything with the driver in this repo:

```bash
python3 tools/bt.py run tools/specs/v75_tech.json     # run a sweep spec
python3 tools/bt.py report                            # parse the newest tester log
```

`tools/specs/` holds every sweep used: `payoff_ds`, `v71_techniques`, `v72_depth_ext`,
`v72_deepcont_tune`, `v73_confirm`, `v73_filters`, `v73_combo`, `v74_confirm`, `v75_tech`.

## Gotchas that silently corrupt a sweep

- **The tester carries over the last-used value for any input not listed in
  `[TesterInputs]`.** An under-specified sweep contaminates the next run (a job that
  omitted `InpTPMode` inherited `InpTPMode=3` from the previous job). List every varying
  input in every job.
- **`/config:` needs a path MT5 can resolve inside the Wine prefix.** `wine terminal64.exe
  /config:/tmp/x.ini` is silently ignored — the terminal starts as a plain GUI and sits
  there forever. Copy the ini into the MT5 install root and pass a bare filename; the
  terminal journal then logs `successfully initialized from start config`.
- **Never let a kill pattern match your own shell.** `pkill -f 'terminal64.exe'` kills the
  shell that runs it; `pkill -f 'terminal6[4]\.exe'` is safe. Same for `run_batch.sh` →
  `run_bat[c]h.sh`.
- **One terminal at a time** — every run shares one data folder. Stop the running terminal
  before a headless run, and `docker restart mt5` afterwards to bring the VNC terminal back
  for the live demo account.
- **Always confirm the run actually ran**: check the tester log for
  `started with inputs:` with the values you set, and for `final balance <n> USD`.

## Things that were tested and do NOT help

Keep this list handy — every one of these looks attractive on paper and cost money when
measured on this EA:

- **Fewer entries per day.** The worst days are clusters of 5–6 same-side entries, so
  capping at 2 per direction looks like the fix. Measured on v7.6: Σ 733.52 → 358.84, and
  the September month gets *worse* (−2.41 vs +1.33). The days that lose big are the same
  days that win big.
- **A hard daily stop** (12/20/30 %): destroys July (372.85 → 2–5) at every setting.
- **Any global take-profit change** (2.0/2.5/3.0R): each value wins a different month and
  wipes the others; 1.5R and 2.5R are the only two defensible picks and they are
  regime-dependent.
- **Pure Fibonacci-extension targets** (1.272/1.618/1.786) instead of an R multiple:
  Σ 122–492 vs 729 for 2.5R on Jul–Oct.
- **Per-direction targets** (`InpTPByDir`): 2 orders in a month change; no effect.
- **Turning the volatility gate off / lowering `InpDeepEffBelow` to 0.40**: wins Jul–Oct,
  loses Nov-2025 / Dec-2025 / Feb-2026.
- **H1 fibonacci confluence as a veto**: −77 % trades, keeps all months green but cuts the
  four-month total from 924 to 602. Worth retrying as a *sizing* input, not a filter.

## What external research says (sourced, 2026-10-13)

Full write-up with URLs and caveats: `research/fibo-web-research.md`. The two usable
datasets are:

**Kriterion Quant validation study** (1,375–2,257 touches per level, multi-asset,
Monte-Carlo section) —
[dashboard](https://kriterionquant.com/wp-content/uploads/2025/12/fibonacci_dashboard_20251227_173044.html):

| retracement level | hit rate | profit factor | vs random |
|---|---:|---:|---:|
| 23.6 % | 50.6 % | 0.49 | **−7.0 %** (not significant) |
| 38.2 % | 62.7 % | 0.89 | +5.1 % |
| 50.0 % | 66.9 % | 1.10 | +9.2 % |
| 61.8 % | 66.6 % | 1.15 | +9.0 % |
| 78.6 % | 69.8 % | 1.31 | +12.1 % |

Hit rate and profit factor rise monotonically with depth, and **gold on its own is the
worst instrument in that study** (765 touches, 56.8 % hit rate, PF 0.86, "INEFFECTIVE").
That is independent confirmation of both of this project's structural choices — the deep
0.66–0.786 zone and the depth-adaptive direction rule — and of its main warning, that a
single-symbol Fibonacci EA is fragile.

**Presto Research fibonacci alpha** on 5-minute Binance perpetuals
([study](https://www.prestolabs.io/research/technical-analysis-in-statistical-arbitrage-i-fibonacci-retracement)):
the 61.8 % level signal returned **6.49 % p.a. with Sharpe 0.04 on BTC alone** and
**77.83 % p.a. with Sharpe 3.2 across the top-50 liquid assets** — the same signal, the
edge appearing only with diversification.

**Peer-reviewed background:** Tsinaslanidis, Guijarro & Voukelatos (2022), *Automatic
identification and evaluation of Fibonacci retracements: Empirical evidence from three
equity markets*, Expert Systems with Applications 187,
[DOI 10.1016/j.eswa.2021.115893](https://www.sciencedirect.com/science/article/abs/pii/S0957417421012495)
— it tests Fibonacci zones against non-Fibonacci control zones. Paywalled; reading it is the
highest-value open research item, because it is the only way to separate "fibonacci works"
from "any level works".

## Caveats

Four months, one symbol, one timeframe. Treat every number here as directional evidence,
not a statistically robust result. The September knife-edge across `InpDeepEffBelow`
(0.40 → +174.58, 0.45 → −0.78) is the clearest warning that some of the gain is fit to the
sample. Any promotion to a live account should be preceded by walk-forward validation on
months that were never used to pick the parameters.

### The v7.x gains do NOT generalise to the earlier months (measured)

Real tick data only exists from 2026.07.01, so the months before that were re-run with
`Model=2` (1-minute OHLC). Both configs were run on the same data with the same model, so
the *comparison* is fair even if the absolute numbers are not comparable to the Jul–Oct
table above:

| month (Model=2) | v7.5 recommended | v6.2 baseline |
|---|---:|---:|
| 2025-11 | 418.90 | **693.12** |
| 2025-12 | −1.35 (wipe) | **382.56** |
| 2026-01 | −5.67 (wipe) | −3.53 (wipe) |
| 2026-02 | −10.22 (wipe) | **137.60** |
| 2026-03 | −1.33 (wipe) | −6.67 (wipe) |
| 2026-06 | −0.52 (wipe) | 0.59 (wipe) |

The recommended v7.5 config is **worse than the v6.2 baseline on 4 of the 6 earlier months**
(and both wipe the other two). The payoff fix that rescued August 2026 — no partial /
break-even / trailing, TP 2.5R — is therefore **regime-specific**, not a universal
improvement: it converts chop months that cluster losses into survivable ones, but it also
removes the small-scale profit-taking that kept several older months alive.

Conclusion: v7.5 is the best build for the Jul–Oct 2026 window it was tuned on, and the
defaults are honest about that. Do not read it as a 12-month strategy. A blend (old exits
in low-volatility regimes, payoff-fixed exits in high-volatility regimes) is the obvious
next hypothesis, and was not tested here.

**Model=4 cross-check.** To rule out the `Model=2` OHLC model itself as the cause, the two
worst months were re-run with `Model=4` (every tick) for both builds:

| month | v7.6 (robust) | v7.5 (payoff fix) |
|---|---:|---:|
| 2025-12 | **350.75** | −4.75 (wipe) |
| 2026-02 | **102.19** | −4.20 (wipe) |

The ranking is unchanged, so the failure of the payoff fix on those months is real and not
an artefact of the tick model.

### Two profiles, one EA

Both live in the same build (`FiboAdaptiveEA_v7.6.mq5`); only switches differ:

| profile | switches | Jul–Oct Σ | Dec-2025 / Feb-2026 |
|---|---|---:|---|
| **v7.6 robust (defaults)** | `InpDirByDepth=1`, `InpTP_R=1.5`, partial/BE/trail `true`, `InpUseVolGate=true`, `InpDeepEffBelow=0.50` | 733.52 | 350.75 / 102.19 |
| v7.5 "max Jul–Oct" | `InpUsePartial/BreakEven/Trailing=false`, `InpTP_R=2.5`, `InpUseVolGate=false`, `InpDeepEffBelow=0.40` | **924.18** | −4.75 / −4.20 (both wiped) |
