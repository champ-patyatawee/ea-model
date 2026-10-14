# Impulse-basket EA — what the brief asked, what was measured, what won

Brief: on XAUUSDm M5 with a $1,000 deposit, open frequently in both directions on
"impulse candles", never use a per-trade SL and never use a basket stop (the account is
the stop), and close the whole group when its combined profit reaches a small target.
Score with `EV per run = (Σ profit − 1000 × runs that blew up) / runs`, where a run that
blows up counts as −$1,000.

Everything below is measured on the MT5 container `mt5` (Exness demo 434226308,
XAUUSDm, M5, hedging account, leverage 1:2000). Artifacts: `ImpulseProbeEA.mq5` (edge
study), `ImpulseBasketEA_v1.0.mq5` … `v2.0.mq5` (the ladder), `tools/edge_probe.py`,
`tools/ibe_run.py`, `tools/ibe_report.py`, `tools/ibe_batch.py`, `tools/mk_ibe_spec.py`,
`tools/specs/ibe_*.json`.

---

## 1. How to measure an EV whose tail event is "the account dies"

Twelve monthly runs are twelve samples; a 30 % blow-up rate cannot be separated from 10 %
or 50 % with twelve samples. The way out here comes from the EA's own design: **the lot
is fixed**, so the dollar P/L path does not depend on the balance (only the ruin *floor*
does). Therefore:

* one **continuous** run of the whole period at a large deposit ($100,000) gives the
  honest dollar path, and
* every start day of a 21-trading-day window becomes its own run.

That turns 12 samples into **1,157 overlapping runs** (`n=1157` in every table below).
A window is marked ruined when the equity falls $1,000 or more below that window's own
starting equity, and a ruined window is scored −$1,000. This is exactly "deposit $1,000,
run until the account dies or the window ends", measured on the real price path instead
of on twelve arbitrary month boundaries.

The report also shows the calendar-month version of the same accounting (46 months) and
the deposit sensitivity curve, so nothing here depends on one arbitrary window rule.

## 2. Question 1 — what an impulse candle *is*, and the proof

`ImpulseProbeEA.mq5` dumped 267,759 M5 bars (2023.01.03 → 2026.10.13) with bar geometry
and forward excursions measured from the **open of the bar after the signal** (no
look-ahead). `tools/edge_probe.py` then reports the conditional drift in dollars per
ounce, its t-statistic, and the drift divided by the real round-trip spread.

Cost model, measured not assumed: the tester's applied spread is **0.24 $/oz** for a run
starting 2026.07 (`IBE SPREAD mean=0.2489 min=0.1600 max=0.5800` from real ticks) and
0.836 $/oz for a run starting 2023.01 — i.e. the gold spread on this account is roughly
0.16–0.84 $/oz depending on the period, about **0.25** in the modern data. The tester's
`Spread=` ini key is ignored by this build (two runs at 30 and 300 points came out
byte-identical), so the cost is whatever the symbol's history says.

**The fade hypothesis is wrong.** At every horizon, on every impulse definition, the
drift *against* the impulse is negative and the drift *with* it is positive:

| definition | n | follow $/oz h=2 | h=4 | h=8 | h=16 |
|---|---:|---:|---:|---:|---:|
| all bars (baseline) | 267759 | −0.001 | +0.007 | +0.025 | +0.033 |
| range ≥ 1.2×ATR | 66297 | +0.016 | +0.026 | +0.029 | +0.045 |
| range ≥ 1.5×ATR | 29920 | +0.059 | +0.090 | +0.074 | +0.084 |
| range ≥ 1.5×ATR & body ≥ 0.5 | 20876 | +0.059 (t +1.7) | **+0.094 (t +1.9)** | +0.087 | +0.161 |
| range ≥ 1.5×ATR & body ≥ 0.4 | 23673 | +0.077 (t +2.3) | **+0.122 (t +2.6)** | +0.121 | +0.151 |
| range ≥ 1.5 & close in top/bottom 15 % & body ≥ 0.5 | 6088 | +0.100 | +0.114 | +0.164 | **+0.266** |
| range ≥ 1.2 & close in top/bottom 15 % & body ≥ 0.5 | 12619 | +0.040 | +0.018 | +0.066 | +0.184 (t +1.8) |

So the entry that has a real (if modest) edge is: **a bar whose range is ≥ 1.5 × ATR(14),
whose body is ≥ 0.5 × its range, and which closes in the top/bottom 15 % of that range,
traded in the CONTINUATION direction** — the "thrust bar". The block that decides the
whole project is the last column of the previous paragraph: at h=4 the best consistent
family earns **+0.09 to +0.12 $/oz against a 0.25 $/oz round trip**. A single impulse
trade therefore does **not** pay for its own spread. Whatever profit the basket makes has
to come from the group/exit structure, not from the entry.

Two honest qualifications, both visible in the same output:

* the edge is **not stable across years** — for `range ≥ 1.5 & body ≥ 0.5` the h=4 drift
  is −0.000 in 2023, +0.080 in 2024, +0.193 in 2025 and +0.114 in 2026; and
* most of the positive drift is gold's own uptrend. The unconditional baseline (all bars)
  already earns +0.025 $/oz at h=8, and a down-thrust bar is followed *up* on average
  (fade-the-downbar earns +0.135 $/oz at h=16, t −3.4 on the other side). A symmetric
  "momentum" reading is not supported; a long-bias reading is.

## 3. Question 2/3 — sizing and exposure: the trap that decides this strategy

The first build (`v1.0`, defaults) opened on **both** directions as impulses arrived,
capped at 8 concurrent positions, and closed the group at +$20. Measured over
2023.01→2026.10 it produced **267,180 of 267,899 samples with exactly 8 positions open
and a net exposure of 0.00 lots**, and a group P/L that only ever decayed (~−$4.12/day,
which is exactly the swap on the 4 long legs). The group was **frozen**: once 4 buys and
4 sells are open at different prices, the combined P/L equals a constant offset between
the average long and average short entry, and it can never reach the +$20 target again.
The EA sat in that state for essentially the whole test.

That is the central design trap of "open both ways, close the group at a small target":
**the two directions do not diversify, they lock the group and cancel the drift.**

| build | EV/run ($1,000, 21d) | ruin | note |
|---|---:|---:|---|
| `v1.0` base (both directions, 8 pos) | −96.07 | 0.0 % | the frozen-hedge trap; bleeds forever but never dies |
| `v1.0` fade direction (`InpDirMode=1`) | −112 | 0 % | confirms the probe: fading the impulse is worse |
| one position per direction (`InpMaxPosPerDir=1`) | −24.15 | 0.0 % | least-bad of the no-exit two-sided builds |
| one-sided groups (`InpSameSideOnly=true`) | −202.46 | 60.8 % | group now moves — and now it can die |
| one-sided, LONG only | **+194.19** | 41.1 % | the money result; see §5 |
| one-sided, SHORT only | −281.00 | 65.4 % | the mirror image |
| lot 0.05 instead of 0.02 | −403.64 | 82.4 % | scaling the same bet up scales the ruin faster |

`InpSameSideOnly` is the switch that matters: it stops the group from freezing by only
adding on the side the group already holds. Adding a *recovery* ladder
(`InpLotMode=2`) or group trailing exits changed nothing measurable; a hard daily flat
(`InpFlatHour=21`) changed nothing (the group rarely lives past 21:00 in the two-sided
build); `InpBlockHourFrom/To` around the rollover did nothing.

## 4. Question 4 — target, position count, frequency: the frontier

The target does not create edge; it only reslices the same P/L path. Sweeping it on the
one-sided build moves EV/run between −208 (`TP=$40`) and −178 (`TP=$5`) — a spread, not a
signal. The **number of positions** and the **holding-time bound** matter much more:

| config (all 0.02 lots, 8 pos unless stated) | EV/run | ruin | median window |
|---|---:|---:|---:|
| hedged base (frozen) | −96.07 | 0.0 % | −94.76 |
| one-sided, no time exit | −202.46 | 60.8 % | −1000 |
| one-sided, force-close after 6 bars (30 min) | −117.71 | 38.5 % | −142.12 |
| one-sided, force-close after 12 bars (1 h) | −22.30 | 32.3 % | −64.57 |
| long-only, no time exit | +194.19 | 41.1 % | −230.80 |
| long-only, max 4 positions | +98.11 | 23.1 % | +16.64 |
| long-only, max 2 positions, force-close 12 bars | +25.90 | **1.7 %** | +9.56 |
| long-only, max 4 positions, force-close 12 bars | +3.61 | 5.1 % | +13.89 |
| long-only + "price above the day's open" filter | **+197.97** | 38.5 % | +25.92 |

The trade-off is explicit and monotone: **bounding the holding time or the position
count converts a blow-up factory into a survivable slow earner** (`max 2 + 12-bar exit`:
EV +25.9, ruin 1.7 %), while **removing the bound maximises EV and the ruin rate**
(+198, 38.5 %).

Deposit sensitivity of the winner (same path, different account size):

| deposit | EV/run | ruin |
|---:|---:|---:|
| 250 | +124 | 76.7 % |
| 500 | +162 | 59.9 % |
| **1,000** | **+198** | **38.5 %** |
| 2,000 | +155 | 20.6 % |
| 5,000 | +33 | 7.7 % |

## 5. The result, and why it has to be read with care

**Winner (highest EV/run, the brief's criterion):**

`ImpulseBasketEA_v2.0.mq5`, defaults:
`InpImpulseRangeATR=1.5, InpImpulseBodyRatio=0.5, InpUseClosePos=true,
InpImpulseClosePos=0.75, InpDirMode=0 (continuation), InpHTF=2 (only buy above the day's
open), InpAllowShort=false, InpSameSideOnly=true, InpMaxPositions=8, InpBasketTP=$20,
InpLot=0.02 fixed, no time exit, no basket stop.`

| metric | value |
|---|---:|
| EV per run, 21 trading days, $1,000 | **+$198** |
| runs that blew up | **38.5 %** |
| median window / best window | +$26 / +$9,527 |
| calendar-month framing (46 months) | EV +$314, ruined 18/46 = 39 % |
| tune 2023.01–2024.12 | EV +$184, ruin 25.0 % |
| validate 2025.01–2026.10 | EV +$211, ruin 53.7 % |

The winner survives the held-out split — in fact it is *better* out of sample — which is
the validation the brief demands. Real-tick (Model=4, Jul–Oct 2026) confirmation and the
literal $1,000 monthly runs are in §6.

**The caveat is not cosmetic.** This configuration is, mechanically, a **leveraged
long-gold grid**: 8 positions × 0.02 lots = 16 oz ≈ $66,000 of notional on a $1,000
account, held until the group is up $20, with no stop. Its measured positive EV rests on
one thing that the sample supplies and the future may not: gold rose 1830 → 4160
(+127 %) between January 2023 and October 2026. The evidence that this is beta and not
edge is in the table above — the exact mirror (`InpAllowLong=false`, short-only) scores
−281/run. Had the sample been a bear market, the two rows would swap.
Anyone who runs this should understand they are buying a long-gold trend bet with a 39 %
ruin rate at $1,000, not a market-neutral strategy.

If a smaller tail is more useful than the maximum EV, the same EA at
`InpMaxPositions=2, InpUseTimeExit=true, InpMaxHoldBars=12` gives EV +$26 with a
**1.7 %** ruin rate — the honest "prefer survival" point on the frontier.

## 6. Validation on data the tuning never saw

**A. Held-out time split (Model=2, the same 1,157-window accounting).** The winner is
better out of sample than in sample — tune 2023-2024 EV +$184 / 25.0 % ruin, validate
2025-2026 EV +$211 / 53.7 % ruin. Almost every other configuration in the sweep flips
sign between the halves (e.g. the two-sided one-sided-group build: +$21 → −$78; the H1
EMA filter: +$95 → −$256).

**B. Real ticks, literal $1,000 monthly runs (Model=4, the only real-tick window).**
Four independent runs, deposit $1,000 reset at each month start, real historical spreads
(mean 0.249 $/oz):

| month | final equity | net | max drawdown |
|---|---:|---:|---:|
| 2026-07 | 2,285.64 | **+1,285.64** | 579.95 |
| 2026-08 | 3,326.53 | **+2,326.53** | 46.82 |
| 2026-09 | 124.57 | **−875.43** | 966.55 |
| 2026-10 (1–13) | 1,785.85 | **+785.85** | 532.99 |
| **Σ** | | **+3,522.59** | |

EV per run = **+$881**, and no run was completely wiped — but September finished with
$124.57 left after a $966 drawdown, i.e. one bad day away from death.

**C. The same real-tick window scored on every start day** (70 rolling 21-day windows at
$1,000) gives EV **−$127** with **70 %** of windows ruined. That is not a contradiction,
it is the honest uncertainty: the real-tick window is 3.5 months long, so its four
calendar months are four lucky-or-unlucky entry points, while the all-starts measure
counts the windows that begin just before September's decline. With 3.5 months of real
ticks there is no way to settle the question; the 3.8-year Model=2 split is the
better-powered evidence, and it is positive in both halves.

**D. The survivor variant on the same real ticks.** `InpMaxPositions=2,
InpUseTimeExit=true, InpMaxHoldBars=12`, same four literal $1,000 months:
−288.93 / +527.22 / +63.14 / +46.07 → EV **+$87** per run, no wipe, worst drawdown
$507; and on the all-starts measure of the real-tick path EV **+$179** with **0 %**
ruin. If the goal is survival rather than the maximum EV, this is the build to run.

## 6b. Where this fails, honestly

* **No bear-market sample exists.** The data starts 2023.01; gold rose throughout. The
  winner's EV is a long-gold bet (mirror evidence: short-only = −$281/run). If gold
  ranges or falls, the expected sign flips and the 38.5 % ruin rate becomes the whole
  story. The measured ruin rate is *not* a worst case — it is the rate observed in a
  favourable regime.
* **Model=2 for most of the year.** Real ticks exist only from 2026.07.01. Model=2 vs
  Model=4 was cross-checked on this build (Jul–Oct 2026) and the ranking held, but the
  absolute numbers for 2023-2025 come from 1-minute OHLC.
* **Ruin is defined on the equity path**, not on the broker's stop-out. A window that
  dips $1,000 below its start and recovers is scored −$1,000 here, which is *stricter*
  than a real margin call would be (the broker closes at ~50 % margin, leaving some
  residual). The monthly tables also show the raw (unfloored) P/L next to the floored
  one so the effect is visible.
* **The winner is not deployable as-is on a real account** without accepting that a
  single $63 adverse gold move on a full 8-position group costs the whole $1,000.

## 6c. What to try next (ranked)

1. **Get a down-trending or ranging sample.** Any XAUUSD period that is not a bull
   market; or run the same EA on silver / an index to see whether the continuation edge
   survives without the gold drift.
2. **Turn the entry edge into a cost-beating one.** The only family with a drift above
   the spread (0.266 vs 0.249 $/oz) is the thrust bar at h=16 on 6,088 samples — a
   *lower-frequency, longer-hold* variant of the same idea. Test it as its own EA.
3. **Risk-normalise the group size** (exposure in ATR units instead of fixed lots) so a
   high-volatility month does not automatically mean ruin.
4. **Test the survivor point properly**: `max 2 positions + 12-bar exit` was positive in
   every window measured (+26 full period, +179 real ticks, 1.7 %/0 % ruin); it deserves
   the same tune/validate discipline the winner got.

## 7. What was tried and did not help

* Fading the impulse (`InpDirMode=1`): −112 to −281 EV/run everywhere.
* Hard daily stop, basket stop, group trailing: no measurable effect, or worse.
* Bigger targets (`TP=40/80`): strictly worse (−208, −258).
* Smaller targets (`TP=5/10`): worse (−178, −208) — the spread per cycle dominates.
* Step-up sizing (`InpLotMode=2`) and recovery sizing (`InpLotMode=3`): no improvement;
  they raise ruin for nothing.
* Raising the lot to 0.05: EV −404, ruin 82 %.
* Higher impulse thresholds (`range ≥ 2.0/2.5 × ATR`): fewer, better trades, but EV still
  negative (−125 to −145).
* A stricter body filter (`body ≥ 0.7`): no improvement.
* `InpMinATR ≥ 2.0` (dollar-volatility filter): no improvement.
* H1 EMA-side filter (`InpHTF=1`): −78 EV/run.
* Cooldown after close (`InpCooldownAfterClose=3`): no improvement.

## 8. Method traps hit in this project (so the next person does not repeat them)

1. **The tester wipes its agent sandbox between jobs.** Anything the EA writes must be
   rescued immediately after each job, and the tester rebuilds the sandbox from the
   terminal's `MQL5/Files`, so old files can reappear. `tools/ibe_run.py` now copies out
   after every job and purges before every job.
2. **The tester picks a different agent port per run** (`Agent-...-3002`, `-3003`, …).
   Hard-coding one agent directory silently loses a whole run's output.
3. **Paths contain spaces** (`Program Files`). Never build a find/ls command by string
   concatenation without quoting the base directory.
4. **Only one terminal at a time.** A second `wine terminal64.exe` exits silently with
   no output at all, which looks exactly like a configuration error.
5. **The tester sometimes finishes the test and never exits**, wedging a shell-driven
   batch. Run one job per `docker exec` under `timeout`, and `pkill -f 'terminal6[4]'`
   before each job.
6. **The applied spread depends on the test's start date** (0.836 $/oz for a 2023 start,
   0.240 for a 2026 start) and `Spread=` in the ini is ignored — so cross-period
   comparisons carry a cost difference, and a "fixed cost" experiment cannot be run
   through the ini.
7. **`wine` can be launched with a stale instance lock.** If a run returns in 0 s with no
   files and no log lines, check for a surviving `terminal64.exe` first.
