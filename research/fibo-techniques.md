# Fibonacci trading techniques — catalogue, and what we tested

> **Provenance warning.** Everything in this file is practitioner/domain knowledge written
> from inside this offline workspace. The web-research pass that was supposed to produce
> cited sources did not complete (the sub-agent never received its task), and this machine
> has no outbound network from the shell. **No claim below is backed by an external study.**
> Treat the "evidence" column as an internal read, and the "verify" column as the exact
> search you should run to check it against public sources.

## The techniques, and their status in this EA

| technique | mechanical definition | regime it needs | status here | measured effect |
|---|---|---|---|---|
| **Retracement zone entry** | after an impulse low→high, enter when price pulls back into 0.382–0.727 of the range | trend with pullbacks | **implemented, default** (`InpEntryFibMin/Max`) | the core of the EA |
| **Optimised trade entry (OTE)** | narrow the zone to 0.618–0.79 and require a reaction candle | strong trend | partly — this is our "deep zone" 0.66–0.786 when auto-selected | deep-zone trades are the ones that should CONTINUE (see below) |
| **FADE (mean reversion at the zone)** | short the retracement of a bullish leg (bet the pullback continues down) | ranges / late-stage trends | **implemented, default** | best 12-month result of the direction family |
| **CONTINUE (trend entry at the zone)** | buy the 0.382–0.727 pullback (bet the leg resumes) | strong one-way trends | implemented (`InpFadeMode=false`, `InpTrueMirror`) | −917.93 over 12 months as a *global* setting |
| **Depth-adaptive direction** | shallow retracement ⇒ fade; deep 0.66–0.786 retracement ⇒ continue | mixed | **implemented (`InpDirByDepth=1`) — our best new edge** | Jul–Oct +204 (734 vs 530); Nov/Feb +68/+55 |
| **Fibonacci extension target** | TP at 1.272 / 1.618 × impulse range beyond the origin (measured move) | trending legs | **implemented (`InpTPMode=3`)** | 389–492 on Jul–Oct vs 729 for a fixed 2.5R — worse |
| **Fixed R-multiple target** | TP = k × stop distance | any | **implemented, default** | 2.5R best on Jul–Oct, 1.5R best on the earlier months |
| **Multi-timeframe fibo confluence** | the M5 zone must overlap the H1 retracement zone of the newest H1 impulse | trend, higher quality | **implemented (`InpUseHTFFibo`, off)** | 602 on Jul–Oct with 77 % fewer trades; keeps every month green but cuts profit |
| **Fibo + break of structure** | require the impulse to break the previous swing extreme | trend | implemented, on by default (`InpRequireBOS`) | mandatory for the setup to exist |
| **Fibo + reaction candle / displacement** | entry candle must close inside the zone with a body ≥ k × ATR | any | implemented (`InpMinReactionScore`, `InpMinBodyATR`) | a quality gate |
| **Fibo + volatility regime (ATR ratio)** | only trade when ATR fast/slow is inside a band | any | implemented (`InpUseVolGate` — **off** in the v7.5 profile, on in v7.6) | off raised Jul–Oct but lost Nov/Feb |
| **Fibo fan / arcs** | diagonal fibo ratios projected from a pivot vs circles around a pivot | trend | **not implemented** | needs a different structure model (price×time geometry) — high effort, unclear payoff for M5 |
| **Fibo time zones** | vertical lines at 1, 2, 3, 5, 8, 13 bars after a pivot; expect a turn | any | **not implemented** | cheap to add as a *filter*: only take setups whose age in bars is near a fibo time zone. Cheap A/B test |
| **Fibonacci pivot points** | classic floor-trader pivots (P, R1–R3) blended with fibo retracement of yesterday's range | intraday | **not implemented** | an alternative anchor; would need a second zone definition |
| **Fibo + order block / fair-value gap** | the zone must contain a displacement candle's imbalance | trend | **not implemented** | the most-cited "missing piece" in the retail literature; medium effort, plausible gain |
| **Liquidity sweep then retrace** | require the impulse to sweep a prior swing's stop cluster before the BOS | any | **not implemented** | plausible, medium effort |
| **Fibo trailing stop** | trail the stop to the 0.382 / 0.5 retracement of the *last* leg rather than by ATR | trend | **not implemented** | the ATR trail we do use was measurably harmful |
| **Fibo pyramiding** | add at 0.5 and 0.618 on the way back, same direction | strong trend | **not implemented** | conflicts with `InpMaxPositions=1` |

## The evidence question

Fibonacci retracement levels are not a physical law, and the honest summary of the public
literature is: **the levels work as self-fulfilling reference points in markets with enough
retail participation, and the measured edge comes mostly from the risk placement (stop
beyond the zone) rather than the level itself.** On gold specifically, the highest-quality
public work is on price-action effects around round numbers and prior-day extremes, not on
fibonacci ratios.

Our own four months of data say the same thing indirectly: the EA's profitability moved
with (a) how far the stop sat beyond the zone, (b) how much of the move the target gave
back, and (c) how many times the same idea was re-entered in one day — **not** with which
particular retracement depth (0.382 vs 0.5 vs 0.618) was used.

**Verify with:** `"fibonacci retracement" statistical significance study`,
`gold XAUUSD fibonacci levels backtest`, `OTE optimal trade entry win rate data`,
`measured move extension target hit rate intraday`, `fibonacci time zones study`.

## The five things I would try next, in order

1. **Cap entries per day (3 → 2 per direction, or 4 total).** Measured: every day with ≥6
   entries was either a huge win or a disaster (worst days: −97.61 with 6, −89.16 with 6,
   −82.34 with 5). This is a config-only change (`InpMaxEntriesPerDirPerDay`,
   `InpMaxTradesPerDay`) and directly targets "fewest losing days".
2. **Regime-switched exit ladder.** v7.5's no-partial/TP-2.5R ladder wins chop months and
   wipes trend months; v7.6's original ladder does the opposite. Switch between the two on a
   measurable volatility/trend descriptor (e.g. ATR ratio or 3-day efficiency) rather than
   picking one globally.
3. **H1 fibonacci confluence as a *size* filter, not a veto.** Vetoing 77 % of trades cut
   profit; using the confluence to double the lot on qualifying setups keeps the edge and
   improves the payoff ratio.
4. **Fibo time-zone filter.** Only accept setups whose impulse age in bars is within ±1 bar
   of a Fibonacci number (3/5/8/13/21). Cheap to code from `impulseAge`, which the EA
   already computes.
5. **Fair-value-gap / displacement requirement on the impulse.** The strongest public
   argument for fibo confluence is that the zone overlaps an imbalance; add a check that the
   impulse leg contains a bar with body ≥ 1.2 × ATR and a gap in the low/high sequence.

## What the EA already rules out

- **Hard daily stops** (12/20/30 %): measurably worse, every setting.
- **Widening the take profit alone** (2.5R / 3R) without changing anything else: wins one
  month, wipes the next.
- **Pure fibre-extension targets (1.272/1.618/1.786)** instead of an R multiple: worse on
  every month tested.
- **Global CONTINUE instead of FADE**: −917.93 vs +1164.09 over the 12-month grid.
- **H1 EMA trend filters / regime filters / daily direction locks**: neutral-to-harmful in
  the 12-month grid (documented in `skills/fibo-mode-matrix`).
