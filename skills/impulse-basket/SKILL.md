---
name: impulse-basket
description: Impulse-candle basket EA on XAUUSDm M5 — the measured edge of "impulse candles", why the brief's literal two-sided basket freezes into a hedged grid, the EV/ruin frontier over 1,157 rolling runs, the shipped build, and the exact tester/reporting recipe used to get there
license: MIT
compatibility: opencode
metadata:
  audience: developers
---

## What I do

- Give the measured answer to "what is an impulse candle with a real edge on XAUUSDm M5",
  with the numbers that support it and the ones that undercut it
- Explain the structural trap of a two-sided grid that closes the whole group at a small
  target, and the switch that fixes it
- Record the EV/ruin frontier (target, position count, holding-time bound, lot, deposit)
  for the shipped build
- Provide the exact, reproducible run recipe: the tester invocation, the reporting
  methodology that turns one continuous run into ~1,157 independent runs, and the traps

Related: `mt5-docker-import` (compile), `fibo-adaptive-v7` (the sibling EA and the same
tester harness). Full write-up: `research/impulse-basket.md`.

## The shipped build

`ImpulseBasketEA_v2.0.mq5` (compiles 0 errors / 0 warnings). Defaults = the winner.

```ini
InpImpulseRangeATR = 1.5      ; impulse bar range >= 1.5 * ATR(14) M5
InpImpulseBodyRatio = 0.50    ; |close-open| >= 0.5 * range
InpUseClosePos = true
InpImpulseClosePos = 0.75     ; close in the top/bottom 25 % of the bar
InpDirMode = 0                ; CONTINUATION (fade is measurably wrong)
InpHTF = 2                    ; only buy while price is above the day's open
InpAllowLong = true
InpAllowShort = false
InpSameSideOnly = true        ; <-- the switch that stops the frozen hedged group
InpMaxPositions = 8
InpBasketTP = 20.0            ; close the whole group at +$20
InpLot = 0.02                 ; fixed, never a martingale
InpUseTimeExit = false        ; the brief's "no basket stop" — the account is the stop
```

Measured (XAUUSDm M5, $1,000, 2023.01-2026.10, Model=2, 1,157 rolling 21-trading-day runs):

| metric | value |
|---|---:|
| **EV per run** | **+$198** |
| **runs that blew up** | **38.5 %** |
| median window / best | +$26 / +$9,527 |
| calendar months (46): EV / ruined | +$314 / 39 % |
| tune 2023-2024 | +$184, ruin 25.0 % |
| validate 2025-2026 | +$211, ruin 53.7 % |

**Read the caveat before the number.** This is a leveraged long-gold grid: 16 oz of
notional (≈$66,000) on a $1,000 account, no stop, closed only at +$20. The identical
logic run short-only scores **−$281/run**; gold rose 1830 → 4160 over the sample. The
positive EV is a long-gold trend bet, not a market-neutral edge, and it is only as good
as the trend.

Survivor variant in the same file: `InpMaxPositions=2, InpUseTimeExit=true,
InpMaxHoldBars=12` → EV +$26/run with a **1.7 %** ruin rate over the full period, and
+$179/run with **0 %** ruin on the real-tick Jul–Oct 2026 window.

## What an impulse candle actually is (measured)

`ImpulseProbeEA.mq5` dumps per-bar geometry and forward excursions (entry = open of the
bar AFTER the signal) for 267,759 M5 bars, 2023.01.03 → 2026.10.13;
`tools/edge_probe.py` reports drift in $/oz, t-stat and drift÷spread.

| definition | n | h=2 | h=4 | h=8 | h=16 |
|---|---:|---:|---:|---:|---:|
| all bars (baseline) | 267759 | −0.001 | +0.007 | +0.025 | +0.033 |
| range ≥ 1.5×ATR | 29920 | +0.059 | +0.090 | +0.074 | +0.084 |
| range ≥ 1.5×ATR & body ≥ 0.4 | 23673 | +0.077 | **+0.122** (t 2.6) | +0.121 | +0.151 |
| range ≥ 1.5 & close in top/bottom 15 % & body ≥ 0.5 | 6088 | +0.100 | +0.114 | +0.164 | **+0.266** |

(dollars per ounce, in the impulse's own direction)

Three facts decide the design:

1. **Fading is wrong.** Every fade column is negative at every horizon on every
   definition. Continuation is the positive side, at about t = +2 to +3.
2. **One impulse trade does not pay for its own spread.** Best consistent family: +0.09
   to +0.12 $/oz at h=4 against a measured 0.249 $/oz round trip (real ticks) — i.e.
   0.3–0.7 × cost. The profit has to come from the exit structure, not from the entry.
3. **Most of the drift is gold beta.** The unconditional baseline already earns +0.03 $/oz
   at h=8, a down-thrust bar is followed *up* (fade-the-downbar +0.135 $/oz at h=16), and
   the family's drift is −0.000 (2023) / +0.080 (2024) / +0.193 (2025) / +0.114 (2026).
   Treat any impulse rule here as "a way to be long gold more often", not as alpha.

## The trap that decides the strategy

Opening on both directions as impulses arrive is exactly what the brief asks for, and it
destroys the strategy:

> Over 2023.01-2026.10 the two-sided build spent **267,180 of 267,899 samples with
> exactly 8 positions open and a net exposure of 0.00 lots**. Once 4 buys and 4 sells are
> open at different prices the group's P/L is frozen at a fixed entry-price offset, so it
> can never reach the +$20 target; the only thing that moves afterwards is the swap
> (−$4.12/day = the carry on the 4 long legs).

`InpSameSideOnly=true` fixes the mechanics (only add on the side the group already holds);
`InpMaxPosPerDir=1` is a weaker version of the same idea. Without one of them, every
target, filter and sizing experiment is measuring a frozen group.

## EV / ruin frontier (all 0.02 lots, $1,000, 1,157 rolling runs)

| config | EV/run | ruin |
|---|---:|---:|
| two-sided, 8 pos, no exit (frozen) | −96 | 0.0 % |
| one-sided, 8 pos, no exit | −202 | 60.8 % |
| one-sided, 8 pos, force-close 12 bars | −22 | 32.3 % |
| **long-only, 8 pos, no exit (shipped)** | **+198** | **38.5 %** |
| long-only, 4 pos, no exit | +98 | 23.1 % |
| long-only, 2 pos, force-close 12 bars | +26 | 1.7 % |
| long-only, 8 pos, short-only mirror | −281 | 65.4 % |
| long-only, 8 pos, lot 0.05 | −404 | 82.4 % |

Target size is *not* a lever: sweeping `InpBasketTP` over 5…80 moves EV between −178 and
−258 with no trend. Position count and holding-time bound move EV and ruin together,
opposite ways. Deposit: 250 → +124 (77 % ruin), 1,000 → +198 (38.5 %), 2,000 → +155
(20.6 %), 5,000 → +33 (7.7 %).

## Exact run recipe

```bash
# compile
docker cp ImpulseBasketEA_v2.0.mq5 "mt5:/config/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Experts/"
docker exec -w "/config/.wine/drive_c/Program Files/MetaTrader 5" mt5 \
  wine MetaEditor64.exe /compile:"MQL5/Experts/ImpulseBasketEA_v2.0.mq5" /log

# one job per docker exec, full period, huge deposit, equity log on
python3 tools/ibe_run.py tools/specs/ibe_s2.json /tmp/ibe_s2

# score it: EV per run with a $1,000 ruin floor, ~1,157 rolling windows
python3 tools/ibe_report.py /tmp/ibe_s2/s2_same_long.csv 1000 21
python3 tools/ibe_batch.py '/tmp/ibe_s2/s2_*.csv' 1000 21     # ranking + tune/validate
```

Tester settings: `XAUUSDm`, `M5`, `Model=2` (Model=4 for real-tick confirmation on
2026.07.01+), `Optimization=0`, `Visual=0`, `Leverage=2000`, `ShutdownTerminal=1`,
deposit **100,000** for research paths and **1,000** for literal runs. A full 3.8-year
Model=2 run costs ~70 s wall, of which ~65 s is terminal start-up — so always run the
whole period; a one-month run costs the same.

Build specs with `python3 tools/mk_ibe_spec.py <prefix> <variants.json> ImpulseBasketEA_v1.1
> tools/specs/<name>.json`; every job lists every input (the tester carries over the
last-used value of any input you omit).

## Methodology traps (this is the expensive part)

1. **12 months is 12 samples.** With a fixed lot the dollar path is deposit-independent,
   so one continuous $100,000 run gives every start day its own run: 1,157 overlapping
   21-trading-day runs, a ruin floor at −$1,000 per window. Report EV, ruin %, median,
   p05 and the worst window together — never a profit without the ruin rate.
2. **The tester wipes the agent sandbox between jobs** and rebuilds it from the
   terminal's `MQL5/Files`, so rescue the EA's CSV immediately after each job
   (`tools/ibe_run.py`) and purge before each job.
3. **The tester changes agent port per run** (`Agent-...-3002`, `-3003`): glob the agent
   directories, never hard-code one. And never split a Wine path on its spaces.
4. **One terminal at a time.** A second `wine terminal64.exe` exits in 0 s with no output
   and no log lines — that looks like a config error but is just a lost instance.
5. **`Spread=` in the tester ini is ignored** by this build (30 and 300 points gave
   byte-identical results). The applied spread is date-dependent: 0.836 $/oz for a run
   starting 2023.01, 0.249 $/oz measured on real 2026 ticks. Cross-era comparisons
   therefore carry a cost difference.
6. **`docker restart mt5` when finished**, and confirm the demo account reconnects.

## Files

- `ImpulseProbeEA.mq5`, `tools/edge_probe.py` — the edge study
- `ImpulseBasketEA_v1.0/v1.1/v2.0.mq5` — the ladder (v2.0 = shipped)
- `tools/ibe_run.py` (robust sequential runner), `ibe_report.py` (one path → EV/ruin),
  `ibe_batch.py` (ranking + tune/validate), `mk_ibe_spec.py`, `specs/ibe_*.json`
