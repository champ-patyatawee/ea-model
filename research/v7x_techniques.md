# FiboAdaptiveEA v7.x — new-technique review

Setup: XAUUSDm M5, Model=4 real ticks, $100, FADE + TrueMirror, exits off (partial/BE/trail),
TP 2.5R unless noted. Months Jul/Aug/Sep 2026 and Oct 1–12. Final balance on $100.

## Methodology gotcha (important)

The MT5 tester **carries over the last-used value for any input not listed in
`[TesterInputs]`** (verified from the tester log: a run that omitted `InpTPMode` inherited
`InpTPMode=3` from the previous job). So every sweep job must list **all** varying inputs,
or variants silently contaminate each other. `tools/specs/v72_depth_ext.json` and the
rewritten `v71_techniques.json` now specify a complete input set.

## v7.1 as delivered — refactor OK, new techniques NOT wired

`FiboAdaptiveEA_v7.1.mq5` = v6.2/v7.0 behaviour with the payoff-fix defaults (TP 2.5R,
partial/BE/trail off) plus three declared techniques. Testing showed:

| v7.1 variant | Jul | Aug | Sep | Oct | Σ |
|---|---:|---:|---:|---:|---:|
| base (FADE, TP 2.5R) | 372.85 | 270.33 | −4.64 | 90.08 | **728.62** |
| `InpTPMode=3` "fibext" | 214.26 | −0.22 | 64.14 | 126.04 | 404.22 |
| `InpUseHTFFibo=true` | 372.85 | 270.33 | −4.64 | 90.08 | 728.62 |
| `InpDirByDepth=1` | 372.85 | 270.33 | −4.64 | 90.08 | 728.62 |
| `InpDirByDepth=2` | 372.85 | 270.33 | −4.64 | 90.08 | 728.62 |
| `InpFadeMode=false` (CONTINUE) | −5.40 | 272.83 | −0.58 | −0.91 | 265.94 |

Code review of v7.1:

- `InpUseHTFFibo` / `InpH1Fibo*` — **declared but never referenced** → dead inputs (results
  byte-identical to base).
- `InpDirByDepth` — **declared but never referenced** → dead input.
- `InpTPMode==TP_FIB_EXT` — **no branch exists**; value 3 falls through to the legacy `else`
  that sets `tp = impulse.high/low` (the impulse extreme), *not* a Fibonacci extension, and
  ignores `InpTPExtMult/MinR/MaxR`.
- Only the payoff-fix defaults and the CONTINUE mirror actually change behaviour. CONTINUE
  matches FADE in August but wipes Jul/Sep/Oct → worse overall.

## v7.2 — actually wires the two implementable techniques

`FiboAdaptiveEA_v7.2.mq5` (compiles 0 errors / 0 warnings):

1. `InpTPMode==TP_FIB_EXT` now computes a real extension target
   (`impulse extreme ± InpTPExtMult×range`), floored at `InpTPExtMinR` and capped at
   `InpTPExtMaxR` (if > 0).
2. `InpDirByDepth` now overrides FADE/CONTINUE by retracement depth (`prof==1` = deep zone):
   `1` = deep → CONTINUE, shallow → FADE; `2` = the inverse. This directly tests the user's
   hypothesis ("on days FADE loses, the mirrored direction wins").
3. `InpUseHTFFibo` is left as a declared no-op (documented as such); implementing H1
   confluence is a separate change if v7.2 shows the extension/depth ideas are worth it.

### v7.2 sweep results (`tools/specs/v72_depth_ext.json`)

| v7.2 variant | Jul | Aug | Sep | Oct | Σ |
|---|---:|---:|---:|---:|---:|
| base (FADE) | 372.85 | 270.33 | −4.64 | 90.08 | 728.62 |
| **`InpDirByDepth=1` (deep→CONTINUE)** | **313.29** | **433.90** | **−0.27** | **114.81** | **861.73** |
| `InpDirByDepth=2` (deep→FADE) | −2.08 | 131.14 | 58.76 | −0.91 | 186.91 |
| `TPMode=3` ext 1.272 | 298.69 | −1.30 | −2.20 | 196.56 | 491.75 |
| `TPMode=3` ext 1.618 | 278.43 | −2.77 | 1.44 | 112.24 | 389.34 |
| `TPMode=3` ext 1.786 | −1.55 | −3.98 | −0.57 | 128.12 | 122.02 |

**Depth-adaptive direction is the first real gain beyond the payoff fix**: `InpDirByDepth=1`
raises the Jul–Oct aggregate from 728.62 to 861.73 and, crucially, turns September from a
wipe (−4.64) into break-even (−0.27) while lifting August 270→434. It directly supports the
user's hypothesis that the deep-zone trades should CONTINUE rather than FADE. The pure
Fibonacci-extension target does **not** beat a fixed 2.5R (best ext run ≈ 492). A follow-up
sweep (`tools/specs/v72_deepcont_tune.json`) tunes TP and time-exit on top of `deepcont`.

### deepcont tuning results

| variant | Jul | Aug | Sep | Oct | Σ |
|---|---:|---:|---:|---:|---:|
| **dc (TP 2.5, time-exit on)** | 313.29 | 433.90 | −0.27 | 114.81 | **861.73** |
| dc TP 2.25 | 294.61 | 422.87 | −0.02 | 116.64 | 834.10 |
| dc TP 2.75 | 347.96 | 412.65 | −1.05 | 89.36 | 848.92 |
| dc TP 2.0 | 321.23 | 395.19 | −1.52 | 78.23 | 793.13 |
| dc TP 3.0 | 395.15 | −0.53 | −0.55 | 78.28 | 472.35 |
| dc, time-exit off | 183.18 | 468.31 | −0.59 | 87.46 | 738.36 |

TP 2.5R and the 180-min time exit remain optimal on top of `deepcont`.

## v7.3 — deepcont becomes the default

`FiboAdaptiveEA_v7.3.mq5` = v7.2 with `InpDirByDepth` default = 1 (compiles 0 errors / 0
warnings). Best config measured over Jul–Oct 2026 ($100, real ticks): ≈ **+762 net profit**
(861.73 final across four independent $100 months) vs the pure-fade baseline ≈ +629. Set
`InpDirByDepth=0` to recover pure-fade behaviour.

## v7.4 — robustness tuning on top of v7.3

`tools/specs/v73_filters.json` and `tools/specs/v73_combo.json` swept the existing filters and
deep-zone width on the v7.3 config:

| variant | Jul | Aug | Sep | Oct | Σ |
|---|---:|---:|---:|---:|---:|
| v7.3 ctrl | 313.29 | 433.90 | −0.27 | 114.81 | 861.73 |
| vol gate off (`novol`) | 355.14 | 433.90 | −0.77 | 114.81 | 903.08 |
| `InpDeepEffBelow=0.40` | 416.42 | 192.57 | 174.58 | 140.61 | 924.18 |
| `InpDeepEffBelow=0.45` | 434.14 | 376.54 | −0.78 | 140.61 | 950.51 |
| `InpUseHTFTrendFilter=true` | 129.96 | 363.64 | −1.30 | 229.97 | 722.27 |
| `InpUseRegimeFilter=true` | 295.48 | 469.13 | −0.78 | 113.97 | 877.80 |

`FiboAdaptiveEA_v7.4.mq5` (compiles 0/0) sets `InpUseVolGate=false` and `InpDeepEffBelow=0.40`
as defaults — confirmed at 416.42 / 192.57 / 174.58 / 140.61 (Σ **924.18**), the only config
with a **profit in every one of the four months**. `InpDeepEffBelow=0.45` scores higher
(950.51) but wipes September, so it is left as an opt-in.
