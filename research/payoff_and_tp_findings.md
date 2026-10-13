# FiboAdaptiveEA — Payoff & TP findings

Backtest setup: XAUUSDm, M5, Model=4 (real ticks), Exness-MT5Trial7, deposit $100,
`InpFadeMode=true`, `InpTrueMirror=true`. Windows = full months Jul/Aug/Sep 2026 and
Oct 1–12 2026. All numbers are **final balance** (start equity $100). "P/L" = final − 100.

## 1. The exit structure was leaking the edge

Realised payoff on the original config was avg win +0.51R vs avg loss −1.00R: the 50%
partial at 1R, break-even at 1R and the ATR trail from 1.5R were cutting winners before
the 1.5R target, and the 180-min time exit closed the rest flat.

| Month | baseline (partial/BE/trail ON, TP 1.5R) | E1 (all OFF, TP 2.5R) |
|---|---:|---:|
| Jul 2026 | 388.48 | 372.85 |
| Aug 2026 | **−0.50** (wipe) | **270.33** |
| Sep 2026 | 1.33 | −4.64 (wipe) |
| Oct 2026 (1–12) | 140.46 | 90.08 |
| **Σ P/L (wipe capped at −100)** | **≈ +129** | **≈ +333** |

Turning partial/BE/trail off and widening TP to 2.5R flipped August from a wipe-out to
+170 on the same $100. The payoff hypothesis is confirmed — but TP is **month-sensitive**.

## 2. TP sweep on the E1 base (partial/BE/trail OFF)

| TP_R | Jul | Aug | Sep | Oct | Σ P/L (cap −100) |
|---:|---:|---:|---:|---:|---:|
| 2.0 | 351.53 | −0.06 (wipe) | **250.03** | 53.50 | ≈ +255 |
| **2.5** | 372.85 | **270.33** | −4.64 (wipe) | 90.08 | **≈ +329** |
| 3.0 | **442.36** | −0.53 (wipe) | −0.28 (wipe) | 53.55 | ≈ +95 |

Every month has a different sweet-spot TP (Aug wants 2.5R, Sep wants 2.0R, Jul wants
3.0R), and each wrong choice wipes the month. **2.5R is the best single value**, but the
dispersion is the real signal: a fixed TP is fragile. Worth testing an adaptive /
Fibo-extension target instead of a pure R multiple (see v7.1 `InpTPMode=3`).

## 3. Daily stop (`InpDailyStopPct`, v7.0) — rejected

v7.0 added a percentage-of-equity hard daily stop and fixed a real bug
(`g_dailyLocked` was never checked in `TradingAllowed()`, so on 2026.08.13 the EA kept
opening after the 12:45 lock and blew the account at 20:02). The bugfix works — Aug/Sep
no longer wipe — but the stop itself **hurts**, because it cuts the recovery that the
E1 payoff fix now captures.

### 3a. Daily stop on the OLD base (partial/BE/trail ON, TP 1.5R, v7.0)

| InpDailyStopPct | Jul | Aug | Sep | Oct |
|---:|---:|---:|---:|---:|
| 0 (off, ≈v6.2 baseline) | 388.48 | −0.50 | 1.33 | 140.46 |
| 12 | 359.05 | 22.64 | 13.79 | 39.76 |
| 20 | 388.48 | 5.02 | 3.28 | 78.57 |

### 3b. Daily stop on the E1 base (partial/BE/trail OFF, TP 2.5R, v7.0) — the decisive run

| InpDailyStopPct | Jul | Aug | Sep | Oct | Σ finals |
|---:|---:|---:|---:|---:|---:|
| **0 (off)** | **372.85** | 270.33 | −4.64 | 90.08 | **728.62** |
| 12 | 4.53 | 412.53 | 80.36 | 39.76 | 537.18 |
| 20 | 2.61 | 390.16 | 3.74 | 26.24 | 422.75 |
| 30 | 1.56 | 359.62 | 2.19 | 107.90 | 471.27 |
| 20 (+ TP 2.0) | 2.25 | 288.97 | 3.13 | 23.81 | 318.16 |

Every daily-stop setting **destroys July** (372 → ~2–5): the stop locks the day before
July's winners can recover the intraday drawdown, then the EA bleeds. On the payoff-fixed
base a stop does lift August (270 → 390–412), but never enough to offset July. **Daily
stop stays OFF.**

## 4. Open questions / next

- Adaptive TP (per-month sweet spot differs) vs fixed 2.5R.
- FADE vs CONTINUE: the user's hypothesis is that on days FADE loses, the opposite
  direction (CONTINUE / mirrored) wins. v7.1 adds `InpDirByDepth` (depth-adaptive
  direction) and `InpUseHTFFibo` (H1 confluence) to test this directly.
- Compile + backtest v7.1 (`TP_FIB_EXT`, `HTFFibo`, `DirByDepth`) across Jul–Oct.
