# Running the fibo mode grid in the mt5 container

## Command form

```bash
D=/Applications/Docker.app/Contents/Resources/bin/docker
R="/config/.wine/drive_c/Program Files/MetaTrader 5"

# 1. copy the template in, 2. stop the running terminal, 3. run one month
$D cp test_grid_template.ini "mt5:$R/test_grid_template.ini"
$D exec mt5 bash -c "pgrep -f 'terminal6[4]\.exe' >/dev/null && { pkill -f 'terminal6[4]\.exe'; sleep 7; }; echo clean"

$D exec -u abc -w "$R" mt5 bash -c '
RUNROOT="/config/.wine/drive_c/Program Files/MetaTrader 5"; cd "$RUNROOT"
for m in 2025-10 2025-11 2025-12; do
  y=${m%-*}; mm=${m#*-}
  if [ "$mm" = "12" ]; then y2=$((y+1)); mm2=01; else y2=$y; mm2=$(printf "%02d" $((10#$mm+1))); fi
  from="$y.$mm.01"; to="$y2.$mm2.01"; rep="OptM$y$mm"
  sed -e "s/@FROM@/$from/" -e "s/@TO@/$to/" -e "s/@REPORT@/$rep/" "$RUNROOT/test_grid_template.ini" > "$RUNROOT/$rep.ini"
  echo "START $rep $from -> $to $(date +%H:%M:%S)"
  wine terminal64.exe /config:$rep.ini >/dev/null 2>&1
  echo "DONE $rep rows=$(grep -c "<Row>" "$RUNROOT/$rep.xml" 2>/dev/null || echo 0) $(date +%H:%M:%S)"
done'

# 4. afterwards restore the VNC terminal
$D restart mt5
```

Each month takes ≈2 min at `Model=0` (48 passes, 12 local agents, plus ~40 s broker login). A 49-row XML (1 header + 48 passes) is the success signal. The optimization report lands at `<MT5 root>/<Report>.xml` as SpreadsheetML.

## The template

`@FROM@`, `@TO@`, `@REPORT@` are substituted per month. Every input is pinned except the five sweep axes.

```ini
[Tester]
Expert=FiboAdaptiveEA_v6.1
Symbol=XAUUSDm
Period=M5
Optimization=1
OptimizationCriterion=0
Model=0
FromDate=@FROM@
ToDate=@TO@
ForwardMode=0
Deposit=100
Currency=USD
Leverage=2000
ExecutionMode=0
Visual=0
Report=@REPORT@
ReplaceReport=1
ShutdownTerminal=1
[TesterInputs]
InpMagic=20260916||20260916||0||20260916||N
InpTF=PERIOD_M5||PERIOD_M5||0||PERIOD_M5||N
InpRiskPercent=0.50||0.50||0||0.50||N
InpMinRR=1.00||1.00||0||1.00||N
InpMaxPositions=1||1||0||1||N
InpDebug=true||true||0||true||N
InpForceMinLot=true||true||0||true||N
InpMaxLotRiskPercent=10.0||10.0||0||10.0||N
InpMaxRiskMoneyPerTrade=30.0||30.0||0||30.0||N
InpFixedLot=0.02||0.02||0||0.02||N
InpUseMfeLog=true||true||0||true||N
InpRandomEntry=false||false||0||false||N
InpRandomEntryBars=12||12||0||12||N
InpUseTokyo=false||false||0||false||N
InpTokyoStartUTC=0||0||0||0||N
InpTokyoEndUTC=8||8||0||8||N
InpUseLondon=true||true||0||true||N
InpLondonStartUTC=7||7||0||7||N
InpLondonEndUTC=16||16||0||16||N
InpUseNewYork=true||true||0||true||N
InpNewYorkStartUTC=12||12||0||12||N
InpNewYorkEndUTC=21||21||0||21||N
InpATRPeriod=14||14||0||14||N
InpLookbackBars=150||150||0||150||N
InpSwingLeft=2||2||0||2||N
InpSwingRight=2||2||0||2||N
InpMinImpulseATR=0.80||0.80||0||0.80||N
InpMaxImpulseATR=5.00||5.00||0||5.00||N
InpTrendEfficiencyMin=0.40||0.40||0||0.40||N
InpMaxImpulseAgeBars=30||30||0||30||N
InpRequireBOS=true||true||0||true||N
InpRequireStructure=true||true||0||true||N
InpUseFadeRegimeGate=true||true||0||true||N
InpFadeMinEfficiency=0.40||0.40||0||0.40||N
InpUseHTFTrendFilter=false||false||0||false||N
InpHTF_TF=PERIOD_H1||PERIOD_H1||0||PERIOD_H1||N
InpHTFEMA_Period=50||50||0||50||N
InpHTFSlopeBars=6||6||0||6||N
InpUseDailyDirLock=false||false||0||false||N
InpMaxDirLossesPerDay=3||3||0||3||N
InpATRZoneShift=0.10||0.10||0||0.10||N
InpUseRegimeFilter=false||false||0||false||N
InpRegimeSlopeBars=6||6||0||6||N
InpRegimeStrengthMin=0.50||0.50||0||0.50||N
InpMaxEntriesPerDirPerDay=3||3||0||3||N
InpMaxTradesPerDay=0||0||0||0||N
InpLogFeatures=true||true||0||true||N
InpUseVolGate=true||true||0||true||N
InpATRSlowPeriod=50||50||0||50||N
InpMaxVolRatio=2.00||2.00||0||2.00||N
InpMinVolRatio=0.50||0.50||0||0.50||N
InpEntryFibMin=0.382||0.382||0||0.382||N
InpEntryFibMax=0.727||0.727||0||0.727||N
InpDeepFibMin=0.66||0.66||0||0.66||N
InpDeepFibMax=0.786||0.786||0||0.786||N
InpDeepEffBelow=0.50||0.50||0||0.50||N
InpDeepVolAbove=1.50||1.50||0||1.50||N
InpDeepTouchMin=3||3||0||3||N
InpMaxTouches=5||5||0||5||N
InpDeepSL_ATR=2.00||2.00||0||2.00||N
InpSL_ATR=1.75||1.75||0||1.75||N
InpTP_R=1.50||1.50||0||1.50||N
InpMinReactionScore=2.5||2.5||0||2.5||N
InpMinBodyATR=0.25||0.25||0||0.25||N
InpMaxSpreadATR=0.15||0.15||0||0.15||N
InpRequireReactionClose=true||true||0||true||N
InpUseBreakEven=true||true||0||true||N
InpBreakEvenR=1.00||1.00||0||1.00||N
InpBreakEvenOffsetR=0.25||0.25||0||0.25||N
InpUseTrailing=true||true||0||true||N
InpTrailStartR=1.50||1.50||0||1.50||N
InpTrailATR=1.50||1.50||0||1.50||N
InpUsePartial=true||true||0||true||N
InpPartialR=1.00||1.00||0||1.00||N
InpPartialPct=50.0||50.0||0||50.0||N
InpUseTimeExit=true||true||0||true||N
InpMaxHoldMinutes=180||180||0||180||N
InpDailyLossPercent=15.0||15.0||0||15.0||N
InpDailyLossMoney=100.0||100.0||0||100.0||N
InpMaxConsecutiveLosses=10||10||0||10||N
InpFadeMode=true||0||1||1||Y
InpUseDualMode=false||0||1||1||Y
InpUseDeepProfile=true||0||1||1||Y
InpUseATRAdaptiveZone=false||0||1||1||Y
InpTPMode=2||0||1||2||Y
```

## Rules the MT5 optimizer does not tell you

1. **Parameters persist per expert name.** The stored optimization set survives runs. A parameter absent from `[TesterInputs]` keeps the previous run's range; a parameter written as a plain `Name=value` also keeps it. Always pin with the `...||N` form. This is why a probe with two ranged parameters produced 12 passes instead of 6 — the earlier run's `InpTP_R` range was still active.
2. **Range syntax:** `base||start||step||stop||Y|N`. Bools accept numeric ranges (`true||0||1||1||Y` → false,true). Enums accept numeric ranges (`2||0||1||2||Y` → 0,1,2) and are reported numerically.
3. **`Optimization=1`** = full grid (slow complete), `OptimizationCriterion=0` = maximise balance. Local agents parallelise automatically — 12 cores in this container, roughly `passes × ~22 core-seconds / 12` per month.
4. **`ToDate` is exclusive at 00:00.** A month runs `first-of-month 00:00` → `first-of-next-month 00:00`. Using the last day of the month silently drops the final trading day (this cost 16.34 in the 2026-09 spot check).
5. **The report is SpreadsheetML**, not plain XML: `<Worksheet ss:Name="Tester Optimizator Results">` with one `<Row>` per pass and columns `Pass, Result, Profit, Expected Payoff, Profit Factor, Recovery Factor, Sharpe Ratio, Custom, Equity DD %, Trades, <each swept input>`. Parse with an XML parser — shell splitting mangles it.

## Failure modes seen for real

| symptom | cause | fix |
|---|---|---|
| XML missing, run finishes in ~17 s, no new terminal log lines | MT5 never started — a previous instance still held the data folder, or the job was backgrounded | confirm the terminal is gone; run in the foreground |
| `total passes 96` instead of 48 | a stale range on a pinned parameter | add the `||N` pin form |
| Optimization stops right after launch | launched with `&` or `docker exec -d` — the process is killed with the exec session | run in the foreground inside one long-lived `docker exec` |
| the shell running the kill dies with exit 143 | `pkill -f` matched its own command line because the literal executable name appeared in it | use the bracket pattern `terminal6[4]\.exe` and avoid the literal name elsewhere in the same command |
| `not enough money` (retcode 10019) floods the log | account already depleted; 0.02 lot needs ~$4.30 margin at 1:2000 | expected behaviour on a blown account, not a config error |

## Verifying a run is trustworthy

- Row count is `passes + 1` (49 for the 48-cell grid).
- The header lists exactly the intended sweep axes — an extra `Inp*` column means a stale range leaked in.
- Behaviour spot check: with `InpFadeMode=true` a `FIBO setup: BUY` must open a **SELL**; with `false`, a **BUY**. The tester log line `started with inputs:` echoes the effective values.
- Cross-check one cell against a standalone single-config run (see `modes-and-results.md`).
