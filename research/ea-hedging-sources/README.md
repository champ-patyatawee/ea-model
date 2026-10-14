# Hedging-school EAs — what is actually out there, copied into this repo

Research run on 2026-10-14 with BrowserOS neo (the user's own browser, so the
GitHub session and download folder are theirs). Question asked: find
**hedging-school EAs that win**, and copy the source in.

Everything below is source that is now in this folder. All five files were
copied into the MT5 container `mt5` and **compiled with MetaEditor64**: four
compile 0 errors / 0 warnings, one has a single warning. Line counts and input
lists are read from the actual code, not from the marketing text.

| file | origin (public repo) | licence | lines | compiles |
|---|---|---|---:|---|
| `BiDirectionalHedgingGrid-2.2.0/BiDirectionalHedgingGrid.mq5` | `Yoshinarium/BiDirectionalHedgingGrid` v2.2.0 | not stated | 1384 | 0 errors, 1 warning |
| `XAUUSD_Advanced_Grid_EA.mq5` | `BlamzKunG/XAUUSD-Grid-EA` | MIT | 1088 | 0 / 0 |
| `XAUUSD_Adaptive_MeanReversion_EA.mq5` | `BlamzKunG/XAUUSD-Grid-EA` | MIT | 1129 | 0 / 0 |
| `Grid_Hedge_Combine.mq5` | `Far-1d/grid-hedge-combination-EA` | not stated | 1069 | 0 / 0 |
| `EaHed.mq5` | `evertongoncalo/hedgingEA` | not stated | 511 | 0 / 0 |

## What each one actually does

### 1. `BiDirectionalHedgingGrid` v2.2.0 (the closest to our own build)

Two **separate baskets**, one per direction (`MagicNumberBuy=1000`,
`MagicNumberSell=2000`), each with its own target — this is the important
design difference from our `ImpulseBasketEA` v1.x, which put both directions in
ONE group and therefore froze (see `research/impulse-basket.md` §3).

```
GridMode = FIXED_POINTS | ATR_MODE       FixedGridPoints = 100   (or ATR(14) x 1.5)
LotMultiplier = 1.3                      // "Soft Martingale: lot = last lot * multiplier"
BaseTakeProfitPoints = 200               // base leg TP
BasketProfitTarget_USD = 0.5             // basket target counted FROM THE 2ND LEG
UseDailyDrawdown = true, MaxDailyDrawdownPercent = 4.5   // from 00:00 server equity
MaxSpreadPoints = 30, UseMidnightPause = true (23:55-00:15)
CloseBeforeWeekend = true, FridayCloseTime = "22:00"
```

The whole prop-firm risk layer (daily DD stop, rollover pause, weekend flat,
spread gate) is exactly the layer our clean experiment deliberately omitted —
and the author's own README documents it as the thing that keeps the basket
alive. The "basket target from the 2nd leg at $0.50" is the small-target idea
the brief asked for, implemented per direction.

### 2/3. `XAUUSD_Advanced_Grid_EA` and `XAUUSD_Adaptive_MeanReversion_EA` (MIT)

The most professional free sources found. Four layers each: market filter →
grid engine → basket exit → risk guard, with a hedge-recovery mode.

`Advanced_Grid`: spread ≤ 45 pts, ATR(H1) cap, EMA200 sideway filter, ADX ≤ 32,
session 07–21, Friday stop 18:00; lot × 1.20 per level, base step 250 pts
expanding ×1.10 (or 0.5 × ATR), **max 8 levels**; basket TP $15 / 100 pts /
% balance, basket trailing from $12 step $4; hard floating-DD stop 20 %, freeze
at 12 %, margin guards 200 %/130 %, daily loss $100 / target $150; recovery =
hedge lock or stale-grid target reduction (48 h → 50 %).

`Adaptive_MeanReversion`: entries on M15 RSI(14) 35/65 + Bollinger(20, 2.0),
regime filter on H1 EMA50/200 + ADX ≤ 28; ATR(M15) × 1.4 grid step clamped to
$3.50–$12.00, **max 5 levels**, lot × 1.15, exposure cap 0.25 lots; hybrid
basket TP (%0.5 / $15 / 0.30 × ATR), trailing from $10 step $3; equity stop
8 %, emergency SL 3.5 × ATR(H1), trend-escape cut at −$60, daily loss 3 %,
cooldown 15 min after a basket close.

Both are worth reading as a checklist of the guards a live grid EA needs; both
still carry the family's core risk (a trend that outruns the grid).

### 4. `Grid_Hedge_Combine` (the honest data point)

A grid + hedge EA where the **latest commit message is literally "works fine in
backtest but not in live"**. Grid step 10 pips with a 10 % lot increase, hedge
step 10 pips with a 20 % increase, hedge profit $5, group close at $5 total.
It re-modifies the TPs of the remaining legs to a retrace fraction (40 %) of
the entry range, i.e. it averages the whole basket towards break-even. This is
the canonical shape of the family — and its author's conclusion is the one our
own measurement reached from the other side: the backtest is not the problem,
the live path is.

### 5. `EaHed.mq5` (manual hedging panel)

A chart-panel EA, not a strategy: four buttons that open a hedge on the current
symbol, across 26 FX pairs, or a pair of XAUUSD stop orders ±$1.00 with a $4
SL / $3 TP. Useful as a *tool* for hands-on hedging experiments, and as a
reminder that "hedging EA" often means "manual panel", not a system.

## What "winning" actually looks like in this family

The brief asked for hedging EAs that win. The honest answer from this sweep:

* **In the free-source pool, none of them publishes a verified track record.**
  The closest things to evidence are (a) the two MIT XAUUSD EAs, which are
  technically the most complete and ship preset folders, and (b) the Polish
  `BiDirectionalHedgingGrid`, which documents a prop-firm DD layer instead of
  promising returns.
* **The family's commercial stars are binaries, not source.** `EA Budak Ubat`
  (the reference hedging-martingale in SE Asia, 10★ repo) ships only
  `.ex4` trial builds, an authorised-account list and broker affiliate links —
  nothing to copy and nothing independently verified.
  `ferhc0722/Siam-Hedge-Lane-Seeker` (the Thai “hedge” hit) is a README-only
  product page with download buttons and no code in the repository.
* **That matches our own measurement.** In `research/impulse-basket.md` the
  two-sided group basket froze (267,180 / 267,899 samples at 8 positions and
  net lot 0.00) and every martingale-ish variant raised ruin faster than
  profit: `InpLotMode=2` (step-up) and lot 0.05 both moved EV the wrong way
  (−404 EV/run at 82 % ruin). The winning configuration in that study was the
  *boring* one: one-sided groups, fixed lot, and a bounded holding time.

So if the goal is “a hedging EA that wins”, the copied sources are best used
for their **guard layers** (independent per-direction baskets with their own
targets, ATR-scaled grid steps, level caps, daily DD stop, rollover/wednesday
swap hygiene, spread gate), not for their profit engines.

## Candidates found but not copied (for a later pass)

| repo | why it was not copied |
|---|---|
| `syarief02/EA_Budak_Ubat` | binaries only (`.ex4` trials) + affiliate model |
| `ferhc0722/Siam-Hedge-Lane-Seeker` | README-only, no code in repo |
| `SokolovVasiliy/HedgeTerminal` | 30+ file Russian framework/library, not an EA |
| `fsabiu/Trading-ForexRecoveryZone`, `duyng219/movingaverage-hedgingea`, `ahmedabdurahim/Mt5-ExpertAdvisor` | not yet fetched (no releases/tags, so each file must be pulled one by one); single-file MQL5 EAs, small |

## Working notes for anyone repeating this

* BrowserOS neo downloads land in `/Users/champp/Downloads`; GitHub repos
  **without tags** have no one-click ZIP, so each `.mq5` has to be fetched from
  its blob page via the "Download raw file" button (`download` on that ref).
  Repos *with* tags can be taken as a ZIP from `/<repo>/tags` → `zip`.
* A plain navigation to `codeload.github.com/...zip` does **not** download in
  this browser; it renders an empty page.
* `download` on a README link that points at a blob page **times out** — it is
  a navigation, not a download. Always drive `download` from the file view's
  "Download raw file" button.
