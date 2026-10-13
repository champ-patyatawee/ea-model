# Risk of ruin vs a $100 gold account — what the numbers say

BrowserOS neo research, 2026-10-13. Primary source: **Forex Trade Tool, "Risk of Ruin
Calculator — Trading Account Survival Probability"**
([forextradetool.com/tools/risk-of-ruin-calculator](https://www.forextradetool.com/tools/risk-of-ruin-calculator)),
which publishes the full tables below. Model behind them: 50 % win rate, 1:2 reward:risk,
200 trades, ruin defined as a 20 % drawdown.

## 1. Risk per trade decides survival

| risk per trade | approx. ruin probability | assessment |
|---|---:|---|
| 0.5 % | ~1 % | very safe |
| 1 % | ~4 % | safe (standard for professionals) |
| 2 % | ~15 % | moderate |
| 3 % | ~30 % | high risk |
| 5 % | ~55 % | dangerous — "likely to fail over 200 trades" |
| 10 % | **~85 %+** | near-certain ruin |

A second source sharpens the same curve: *"a strategy with a modest edge might have a
near-zero chance of a 50 % drawdown risking 1 % per trade, a few percent chance at 3 %, and
a coin-flip chance at 8–10 %"*
([probabilitycalculator.pro/risk-of-ruin.html](https://probabilitycalculator.pro/risk-of-ruin.html)).

## 2. Where this EA actually sits on that curve

The EA trades `InpFixedLot=0.02` on XAUUSDm with a 1.75–2.0 × ATR(14) stop. Measured from
the tester log, the risk distance is typically **$12–25 per trade at 0.02 lots** — i.e.
**12–25 % of a $100 account per trade**. Even dropping to the broker minimum of 0.01 lots
still risks **6–12 % per trade**.

Read against the table above, **a $100 XAUUSD account at the minimum lot is already past
the 10 % "near-certain ruin" row**. That is the cleanest explanation of this project's
central measured fact: across 12 independent months the EA compounds in 8 and destroys the
account in 4–5, *and no exit-ladder or filter change moved that number*.

## 3. The loss-streak table — our cluster days are normal, not unlucky

| consecutive losses | at 40 % win rate | at 50 % win rate | at 60 % win rate |
|---|---:|---:|---:|
| 3 in a row | 21.6 % | 12.5 % | 6.4 % |
| 5 in a row | 7.8 % | 3.1 % | 1.0 % |
| 7 in a row | 2.8 % | 0.78 % | 0.16 % |
| 10 in a row | 0.60 % | 0.098 % | 0.01 % |

A 5–7 loss streak is an **expected** event at a 50 % win rate (3–8 % chance per block of
trades). The EA opens up to 3 entries per direction per day, so a single one-sided day can
produce 5–6 consecutive losses and, at 12–25 % risk each, that day alone ends the account.
The cluster days are not a bug in the entry logic; they are the risk of ruin being realised.

## 4. The expected-value table (why the payoff fix mattered)

| win rate | R:R 1:1 | R:R 1:1.5 | R:R 1:2 | R:R 1:3 |
|---|---:|---:|---:|---:|
| 30 % | −0.40R | −0.15R | +0.10R | +0.60R |
| 40 % | −0.20R | +0.10R | +0.40R | +1.00R |
| 50 % | 0.00R | +0.25R | +0.50R | +1.25R |
| 55 % | +0.10R | +0.33R | +0.55R | +1.20R |
| 60 % | +0.20R | +0.40R | +0.60R | +1.40R |

This is why widening the target from 1.5R to 2.5R and removing the 1R partial/break-even
flipped August 2026: at the measured win rate the 1.5R structure sat near zero EV and the
2.5R structure is comfortably positive. It is also why the same change did not stop the
wipe-outs — EV governs the *average*, not the *survival*; survival is governed by risk per
trade.

## 5. What this means for this EA (ranked)

1. **The account is too small for the instrument, not the strategy too weak.** At
   0.01–0.02 lots on XAUUSD, one losing day can be 100 % of equity. The honest fix is a
   bigger account: at **$1,000** the same 0.02 lot risks 1.2–2.5 % per trade, which the
   table rates as ~4–15 % ruin probability over 200 trades instead of ~85 %+. The EA's
   *parameters* do not need to change at all — this is a capital question.
2. **If the account must stay at $100, the only lever left is instrument/lot granularity**
   (a cent account, a lower-value symbol, or a broker with 0.001 gold lots). No parameter
   search can beat the min-lot floor.
3. **A month-level circuit breaker is worth having anyway** (v7.8 `InpMonthStopPct`): it
   converts a −100 wipe into a bounded loss. It cannot raise the average, but it truncates
   the left tail, which is what "แพ้น้อยที่สุด" asks for.
4. **Do not chase a better exit ladder.** The EV table says the existing 2.5R/1.5R choices
   are defensible; the ruin table says the sizing is what kills the account.

## 6. Caveats

- The ruin tables come from a commercial calculator page, not a peer-reviewed paper, and
  the page does not state its simulation seed/count. Treat the shape of the curve (ruin
  rises roughly exponentially with risk per trade) as the reliable part, and the individual
  percentages as indicative.
- The 20 % drawdown definition of "ruin" is much softer than our reality (a $100 account
  cannot survive a 20 % drawdown and keep trading at the minimum lot; the minimum lot
  forces us to keep risking >6 % forever).
- This analysis is arithmetic + literature, not a backtest. The backtest evidence for the
  same conclusion is in `research/SUMMARY.md`: 4–5 wipe months out of 12 in every
  configuration tested.
