# Fibonacci trading — what the web actually says (sourced)

Research pass run with the BrowserOS neo browser on 2026-10-13. Every claim below is
attached to a URL that was actually loaded. Where a number came from a search-result
snippet rather than the page itself, it is marked **(snippet)**.

## 1. The evidence, sorted by how much it is worth

### (a) Peer-reviewed / large-sample

**Tsinaslanidis, Guijarro & Voukelatos (2022), "Automatic identification and evaluation of
Fibonacci retracements: Empirical evidence from three equity markets", *Expert Systems with
Applications* 187, DOI 10.1016/j.eswa.2021.115893.**
[sciencedirect.com/science/article/abs/pii/S0957417421012495](https://www.sciencedirect.com/science/article/abs/pii/S0957417421012495)
This is the only genuine academic study I could reach in full-abstract form. Its method is
exactly the question that matters: it automatically identifies retracements and compares
**bounces on Fibonacci zones against bounces on non-Fibonacci zones** across three equity
markets. It has 44 references and 8 citing papers, i.e. it cleared peer review.
Paywalled — the abstract page (highlights, results) is not readable without institutional
access, so I cannot quote its effect sizes. **Action: treat "does fibo beat non-fibo zones"
as an open question that a peer-reviewed study addressed but that we have not read.**

**Presto Research — "Technical Analysis in Statistical Arbitrage I: Fibonacci Retracement"**
[prestolabs.io/research/technical-analysis-in-statistical-arbitrage-i-fibonacci-retracement](https://www.prestolabs.io/research/technical-analysis-in-statistical-arbitrage-i-fibonacci-retracement)
Full methodology and results are on the page. Signal on **5-minute bars** on Binance
USDⓈ-M perpetuals:
`fibo = 0.618*(max(high,144) - min(low,144)) + min(low,144)`,
`alpha = (mean(close,72) - fibo) / fibo`, i.e. it **bets on continuation/momentum away from
the 61.8 % level**, not on a bounce. Results **before transaction costs**:

| universe | annualised return | Sharpe |
|---|---:|---:|
| BTC/USDT alone | 6.49 % | 0.04 |
| BTC + ETH | lower volatility, still subpar | — |
| top-50 most liquid assets | **77.83 %** | **3.2** |

The paper's own summary is the important part: *"broader asset universes lead to reduced
volatility and enhanced returns"*. On a single instrument the Fibonacci alpha was
**worthless** (Sharpe 0.04).

### (b) Vendor / independent validation studies (better than folklore, not peer reviewed)

**Kriterion Quant — "Fibonacci Retracement Validation Study"** (auto-generated dashboard)
[kriterionquant.com/.../fibonacci_dashboard_20251227_173044.html](https://kriterionquant.com/wp-content/uploads/2025/12/fibonacci_dashboard_20251227_173044.html)
Multi-asset study with 1,375–2,257 touches per level and a Monte-Carlo validation section.
The tables below are transcribed verbatim from the page.

By level:

| level | touches | hit rate | long HR | short HR | profit factor | vs random | significant |
|---|---:|---:|---:|---:|---:|---:|---|
| 23.6 % | 2,257 | 50.6 % | 51.4 % | 49.9 % | 0.49 | **−7.0 %** | NO |
| 38.2 % | 2,066 | 62.7 % | 63.6 % | 61.9 % | 0.89 | +5.1 % | YES |
| 50.0 % | 1,851 | 66.9 % | 71.2 % | 63.0 % | 1.10 | +9.2 % | YES |
| 61.8 % | 1,655 | 66.6 % | 70.7 % | 63.1 % | 1.15 | +9.0 % | YES |
| 78.6 % | 1,375 | 69.8 % | 74.5 % | 65.9 % | 1.31 | +12.1 % | YES |

By asset class:

| class | assets | touches | hit rate | profit factor | best level | effectiveness |
|---|---:|---:|---:|---:|---|---|
| Mega cap | 5 | 7,798 | 65.9 % | 0.96 | 78.6 % | HIGH |
| Energy | 2 | 3,539 | 65.3 % | 0.91 | 78.6 % | HIGH |
| Forex | 3 | 880 | 65.0 % | 0.71 | 78.6 % | HIGH |
| Equity index | 5 | 4,286 | 61.4 % | 0.97 | 78.6 % | MEDIUM |
| **Precious metal (gold)** | **1** | **765** | **56.8 %** | **0.86** | 61.8 % | **INEFFECTIVE** |
| Fixed income | 1 | 517 | 56.8 % | 1.00 | 78.6 % | INEFFECTIVE |

Two things jump out, and both match what this project measured independently:

1. **Deeper is better.** Hit rate rises monotonically from 50.6 % at 0.236 to 69.8 % at
   0.786, and the 0.236 level has a *negative* edge (−7.0 % vs random). Our "deep zone"
   0.66–0.786 and the decision to trade deep retracements as CONTINUE sit exactly on the
   high end of that curve.
2. **Gold is the worst instrument in the study.** 56.8 % hit rate, profit factor 0.86 over
   765 touches. Single-instrument Fibonacci on gold is where the level works least.

Caveats: the parameter table on that page renders unsubstituted template placeholders
(`{config['zigzag_threshold']...}`), so the exact ZigZag threshold, touch tolerance and
sample window are not visible; and the level-vs-random comparison is stated as a simple
difference rather than a tested statistic on the page itself.

### (c) Folklore / marketing (do not act on these)

- `pro-scalper.com` — "The 61.8 % retracement level has a documented edge on gold".
  No data, no sample, no method. Marketing for a FibCalculator.
- `scribd.com/document/1018649172` — claims 835.3 % over five years with a 66.8 % win rate
  from EMA + Fibonacci + volume **(snippet)**. Unverifiable, no audit trail.
- `forexgdp.com`, `onlinegold.org`, `forextradelab.com` — descriptive guides, no testing.
- `youtube.com/watch?v=woxQ7A55a3M` — "backtested" video, no reproducible parameters.

### (d) Gold-specific research leads worth following up

- A paper **citing** the peer-reviewed study above is titled *"Integrating Fibonacci
  retracement to improve accuracy of time series prediction of gold prices"*
  (linked from the ScienceDirect "Cited by" list). This is the closest thing to an
  academic answer for XAUUSD specifically — worth reading next.
- `github.com/MouadZaki/Fibonacci-Backtesting-XAUUSD` — an open-source Fibonacci
  retracement backtest on XAUUSD with trade journaling and performance analytics. Code is
  auditable; README numbers could not be read through the accessibility tree, so treat as
  a code lead, not a result.
- `github.com/Sanchitranakoti/XAUUSD-Algorithmic-Trading-Strategy` — multi-timeframe
  XAUUSD system (broader than Fibonacci).

## 2. What the evidence means for THIS EA

Combining (a) and (b):

- The **level alone is not the edge**. Presto's single-asset alpha had Sharpe 0.04; the
  money appeared only when the same signal was spread over 50 assets, which is the
  classic signature of a small per-trade edge that only survives diversification. A
  single-symbol EA gets one draw of that lottery, so its outcome is dominated by
  *execution and risk management*, not by the ratio it picks.
- That is exactly what this project measured: the same entries produced 529.77, 733.52 or
  924.18 depending only on the exit ladder, and the biggest single lever was the target
  and the partial/break-even/trail decision.
- **Depth is the one thing the level data does support**: 0.5–0.786 had hit rates of
  66.9 %–69.8 % against 50.6 % for 0.236. Our existing deep-profile rule
  (`InpDeepFibMin/Max` = 0.66/0.786) is on the right side of that, but our *shallow* zone
  starts at 0.382 — which the study rates as only +5.1 % over random, the weakest of the
  "significant" levels.
- **Gold is the hardest instrument in the study**, so any single-instrument fibo result on
  XAUUSD should be treated as fragile by default. Our own Dec-2025 / Feb-2026 wipe-outs
  are consistent with that.

## 3. Ranked top 5 additions for this EA

1. **Raise the shallow-zone floor from 0.382 to 0.5.** The only level-by-level dataset
   available rates 0.5 (66.9 % / PF 1.10) far above 0.382 (62.7 % / PF 0.89), and 0.236
   is outright negative. Codeable as `InpEntryFibMin = 0.50` — a one-line change, already
   an input. Falsifiable: run Jul–Oct 2026 and Dec-2025/Feb-2026 with 0.382 vs 0.50 and
   compare. (Kriterion)
2. **Bias the target geometry to the deep side.** 78.6 % has the best hit rate *and* the
   best profit factor of any level, so a position entered in the deep zone should be
   allowed to run further than one entered shallow. Codeable with the `InpTPByDir` /
   `InpAdaptiveExits` machinery already in v7.7: deep ⇒ bigger R multiple. (Kriterion)
3. **Continuation, not reversal, at the level.** Presto's profitable construction *buys
   above* the 61.8 % level and sells below it — a momentum bet away from the level, the
   opposite of a mean-reversion fade at the zone. We already have this as CONTINUE and as
   the depth-adaptive rule; the evidence supports keeping the deep-zone CONTINUE
   behaviour rather than fading it. (Presto)
4. **Diversify across symbols, or accept single-symbol fragility.** The only configuration
   in the literature with a convincing Sharpe ran the identical fibonacci signal across
   50 liquid assets. For this repo the cheap version is: run the same EA on 3–5 other
   symbols with the same settings and treat the portfolio result as the real strategy.
   (Presto)
5. **Get the peer-reviewed paper.** Its whole point is a Fibonacci-zone vs non-Fibonacci
   control group. Reading it would either validate or kill the premise of the whole
   project, and it is the only way to distinguish "fibo works" from "any level works".
   (ScienceDirect)

## 4. Parameter guidance from the sources

- Retracement depths that matter on the evidence available: **0.5, 0.618, 0.786**
  (all "significant", hit rate 66–70 %); avoid relying on 0.236 (negative edge).
- Extension targets: no quantitative hit-rate data found in this pass. Every extension
  figure I saw on gold pages (1.272 at $5,237, etc.) was an unattributed chart-reading.
  Our own measurement stands: the extension target underperformed a fixed 2.5R.
- Stop placement: no source gave a tested ATR multiple. Our own 1.75 / 2.0 ATR remains
  the only measured value in this project.

## 5. Ideas not yet tried (codeable)

1. Shallow-zone floor 0.382 → 0.50 (see top-5 #1).
2. Zone width narrowing: require the close to be within ±0.05 of the zone rather than
   anywhere inside it.
3. Fibonacci **time** filter: only take setups whose impulse age is ±1 bar of 3/5/8/13/21.
4. Displacement/FVG requirement on the impulse leg (body ≥ 1.2 ATR + gap).
5. Multi-symbol portfolio run (top-5 #4).
6. Liquidity sweep requirement: the impulse must have taken out the prior swing's
   extreme.
7. Scale-out *upward* (add at 0.5 and 0.618 on continuation) instead of the partial
   take-profit we tested and rejected — not covered by the EA today.
8. Re-read the Kriterion Monte-Carlo section for the significance of the level effect
   before trusting the +5–12 % "vs random" numbers.
