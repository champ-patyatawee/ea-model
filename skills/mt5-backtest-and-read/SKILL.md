---
name: mt5-backtest-and-read
description: Run Strategy Tester backtests in the mt5 Docker container and read UTF-16LE tester logs and HTML/XLSX reports
license: MIT
compatibility: opencode
metadata:
  audience: developers
---

## What I do

- Launch a Strategy Tester backtest inside the `gmag11/metatrader5_vnc` container `mt5` — either headless via `terminal64.exe /config:test.ini` or interactively via VNC at `http://localhost:3000`
- Locate tester logs at `/config/.wine/drive_c/Program Files/MetaTrader 5/Tester/logs/YYYYMMDD.log` (UTF-16LE) and `Tester/Agent-*/logs/*.log`
- Decode logs with `iconv` and grep for `phoenix`, `final balance`, `STATS`, and `testing of` to extract results without opening the GUI
- Find report outputs at `/config/ReportTester-*.html`, `*.xlsx`, and `Tester/cache/*.tst`
- Provide equivalent paths and commands for Mac native MT5 at `~/Library/Application Support/net.metaquotes.wine.metatrader5/`

## When to use me

- After importing and compiling an EA with `mt5-docker-import` and needing to validate it via a backtest
- When you need to run a quick headless backtest without clicking through the VNC GUI
- When the VNC Strategy Tester visual mode chart is flooded or you want `visual mode OFF` for speed
- To extract `Final Balance`, `Profit`, `Drawdown`, `STATS`, or custom `Print()` / `Phoenix` log lines from tester logs
- To diagnose why a backtest did not produce a report (missing `.ex5`, wrong symbol, date range, or account `2101202007` not connected)

## Usage

### Prerequisites

- Docker container `mt5` running: `/Applications/Docker.app/Contents/Resources/bin/docker ps | grep mt5`
- MT5 logged into account `2101202007` (IUX Demo) — verify via VNC at `http://localhost:3000` (port 3000 = VNC/noVNC, port 8001 = Python bridge); check bottom status bar shows `2101202007: IUX Demo - Connected`
- EA already imported and compiled: `/config/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Experts/<EA>.ex5` exists (see `mt5-docker-import`)
- Tester config file prepared at `/config/test.ini` or `/config/.wine/.../config/test.ini` (if using headless mode)
- Absolute Docker binary: `/Applications/Docker.app/Contents/Resources/bin/docker`

### Step 1 — Choose execution mode

#### Option A — Headless via terminal64.exe (fast, no GUI)

Prepare `/Users/champp/Champ/PhoenixEA/test.ini` on host, then copy and run:

```ini
; /Users/champp/Champ/PhoenixEA/test.ini — example Strategy Tester config
[Tester]
Expert=PhoenixEA
Symbol=XAUUSD
Period=M15
FromDate=2024.01.01
ToDate=2024.12.31
Model=1
Deposit=10000
Leverage=100
Currency=USD
ForwardMode=0
Report=ReportTester
ReplaceReport=1
ShutdownTerminal=1
Visual=0
```

```bash
# Copy ini into container
/Applications/Docker.app/Contents/Resources/bin/docker cp /Users/champp/Champ/PhoenixEA/test.ini "mt5:/config/test.ini"

# Run headlessly — terminal will shut down when done if ShutdownTerminal=1
/Applications/Docker.app/Contents/Resources/bin/docker exec -w "/config/.wine/drive_c/Program Files/MetaTrader 5" mt5 wine terminal64.exe /config:test.ini

# Wait for completion — poll for report or log (backtests take 30s to 10+ min)
/Applications/Docker.app/Contents/Resources/bin/docker exec mt5 bash -c 'ls -lth "/config/.wine/drive_c/Program Files/MetaTrader 5/Tester/logs/" | head -10'
```

#### Option B — Interactive via VNC (visual inspection)

1. Open `http://localhost:3000` in browser (use `browseros-neo` skill if automating — `browser.pages.newPage("http://localhost:3000")`)
2. In MT5: `View` → `Strategy Tester` (or `Ctrl+R`), select EA from dropdown (e.g. `PhoenixEA`), set `Symbol: XAUUSD`, `Period: M15`, date range, `Model: Every tick`
3. **Uncheck "visual mode with the display"** for speed (prevents chart flood — see `mt5-chart-close`), or leave checked only if you need to watch trades
4. Click `Start` and wait for green progress bar to reach 100%
5. Results tabs: `Journal`, `Results`, `Graph`, `Report` — but prefer log reading below for automation

### Step 2 — Locate tester logs (UTF-16LE)

```bash
# Main tester logs — one file per day YYYYMMDD.log
/Applications/Docker.app/Contents/Resources/bin/docker exec mt5 bash -c 'ls -lth "/config/.wine/drive_c/Program Files/MetaTrader 5/Tester/logs/" | head -20'

# Agent logs — one per core, useful for multi-threaded optimization
/Applications/Docker.app/Contents/Resources/bin/docker exec mt5 bash -c 'find "/config/.wine/drive_c/Program Files/MetaTrader 5/Tester" -name "*.log" -path "*/Agent-*/logs/*" | head -20'

# Find the newest log.
/Applications/Docker.app/Contents/Resources/bin/docker exec mt5 bash -c 'ls -t "/config/.wine/drive_c/Program Files/MetaTrader 5/Tester/logs/"*.log | head -1'

# Mac native equivalent
ls -lth "$HOME/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/Tester/logs/" | head -20
```

### Step 3 — Decode and grep results (core workflow)

All MT5 logs are **UTF-16LE** (or UTF-16). Always pipe through `iconv` before `grep`.

```bash
# 1) Find today's log and grep core result lines
/Applications/Docker.app/Contents/Resources/bin/docker exec mt5 bash -c '
  LOG=$(ls -t "/config/.wine/drive_c/Program Files/MetaTrader 5/Tester/logs/"*.log | head -1)
  echo "=== $LOG ==="
  iconv -f UTF-16 -t UTF-8 "$LOG" 2>/dev/null | grep -iE "phoenix|final balance|STATS|testing of|profit|drawdown|pass" | tail -40
'

# 2) Example: extract final balance specifically
/Applications/Docker.app/Contents/Resources/bin/docker exec mt5 bash -c '
  LOG=$(ls -t "/config/.wine/drive_c/Program Files/MetaTrader 5/Tester/logs/"*.log | head -1)
  iconv -f UTF-16 -t UTF-8 "$LOG" | grep -i "final balance"
'

# 3) Example: STATS line (custom Print from PhoenixEA)
/Applications/Docker.app/Contents/Resources/bin/docker exec mt5 bash -c '
  LOG=$(ls -t "/config/.wine/drive_c/Program Files/MetaTrader 5/Tester/logs/"*.log | head -1)
  iconv -f UTF-16LE -t UTF-8 "$LOG" | grep -i "STATS"
'

# 4) Broaden across all Agent logs
/Applications/Docker.app/Contents/Resources/bin/docker exec mt5 bash -c '
  find "/config/.wine/drive_c/Program Files/MetaTrader 5/Tester" -name "*.log" | while read f; do
    echo "--- $f ---"
    iconv -f UTF-16 -t UTF-8 "$f" 2>/dev/null | grep -iE "phoenix|final balance|STATS" | tail -5
  done
'

# 5) Mac native — same iconv pattern
LOG=$(ls -t "$HOME/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/Tester/logs/"*.log | head -1)
iconv -f UTF-16 -t UTF-8 "$LOG" 2>/dev/null | grep -iE "phoenix|final balance|STATS|testing of" | tail -40
```

**Typical grep output to look for:**

```
2024.12.31 15:00:00   testing of PhoenixEA (XAUUSD,M15) from 2024.01.01 to 2024.12.31
STATS: Trades=142 Profit=1234.56 PF=1.82 DD=4.3%
final balance 11234.56
phoenix: signal buy XAUUSD ...
```

### Step 4 — Read report files

```bash
# Reports are written to /config inside container (mapped host volume) and MT5 root
/Applications/Docker.app/Contents/Resources/bin/docker exec mt5 bash -c 'ls -lth "/config/ReportTester"* 2>/dev/null; ls -lth "/config/.wine/drive_c/Program Files/MetaTrader 5/ReportTester"* 2>/dev/null; ls -lth "/config/.wine/drive_c/Program Files/MetaTrader 5/Tester/cache/"*.tst 2>/dev/null | head -10'

# Copy report back to host for inspection
/Applications/Docker.app/Contents/Resources/bin/docker cp "mt5:/config/ReportTester.html" /Users/champp/Champ/PhoenixEA/ReportTester.html 2>/dev/null
/Applications/Docker.app/Contents/Resources/bin/docker cp "mt5:/config/.wine/drive_c/Program Files/MetaTrader 5/ReportTester.html" /Users/champp/Champ/PhoenixEA/ReportTester.html 2>/dev/null

# Mac native reports
ls -lth "$HOME/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/ReportTester"* 2>/dev/null
```

### Step 5 — Live tail during a running backtest

```bash
# Poll every 3 seconds — useful while visual mode is OFF and you have no GUI feedback
/Applications/Docker.app/Contents/Resources/bin/docker exec mt5 bash -c '
  LOG=$(ls -t "/config/.wine/drive_c/Program Files/MetaTrader 5/Tester/logs/"*.log | head -1)
  iconv -f UTF-16 -t UTF-8 "$LOG" 2>/dev/null | tail -30
'
```

## Format / Templates

### Headless backtest template

```
/Applications/Docker.app/Contents/Resources/bin/docker cp /Users/champp/Champ/PhoenixEA/test.ini "mt5:/config/test.ini"
/Applications/Docker.app/Contents/Resources/bin/docker exec -w "/config/.wine/drive_c/Program Files/MetaTrader 5" mt5 wine terminal64.exe /config:test.ini
```

### Log read template (Docker)

```
/Applications/Docker.app/Contents/Resources/bin/docker exec mt5 bash -c 'LOG=$(ls -t "/config/.wine/drive_c/Program Files/MetaTrader 5/Tester/logs/"*.log | head -1); iconv -f UTF-16 -t UTF-8 "$LOG" | grep -iE "phoenix|final balance|STATS|testing of" | tail -40'
```

### Log read template (Mac)

```
iconv -f UTF-16 -t UTF-8 "$HOME/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/Tester/logs/YYYYMMDD.log" | grep -iE "phoenix|final balance|STATS|testing of"
```

### Report retrieval template

```
/Applications/Docker.app/Contents/Resources/bin/docker exec mt5 bash -c 'ls -lth "/config/ReportTester"* "/config/.wine/drive_c/Program Files/MetaTrader 5/Tester/cache/"*.tst 2>/dev/null | head -10'
```

## Workflow

1. **Pre-check** — Verify `mt5` container up, account `2101202007` connected at `http://localhost:3000`, EA `.ex5` exists (from `mt5-docker-import`).
2. **Configure** — Create `test.ini` at `/Users/champp/Champ/PhoenixEA/test.ini` with `Expert`, `Symbol=XAUUSD`, `Period`, `FromDate`/`ToDate`, `Visual=0` (OFF), `Report=ReportTester`, `ShutdownTerminal=1`.
3. **Launch** — Headless: `docker cp test.ini → mt5:/config/test.ini` then `docker exec ... wine terminal64.exe /config:test.ini`. Or VNC: open `http://localhost:3000` → `Strategy Tester` → set params → `Visual mode OFF` → `Start`.
4. **Wait** — Poll `Tester/logs/YYYYMMDD.log` modification time or wait for `ReportTester.html` to appear; backtests run 30s–10m.
5. **Read logs** — `iconv -f UTF-16 -t UTF-8 <newest YYYYMMDD.log> | grep -iE "phoenix|final balance|STATS|testing of"` to extract outcome without GUI.
6. **Read reports** — `ls -lth /config/ReportTester*` and `docker cp` the `.html`/`.xlsx` back to `/Users/champp/Champ/PhoenixEA/` for archival.
7. **Diagnose failures** — If no output, `iconv ... | grep -iE "error|failed|not found"` in same log; check EA name matches `.ex5`, symbol exists, dates valid, and `ShutdownTerminal` did not kill terminal prematurely.
8. **Chart cleanup** — If visual mode was ON and `http://localhost:3000` shows chart flood, run `mt5-chart-close` before next test.

## Troubleshooting

- Empty `grep` after `iconv` → try both `-f UTF-16LE` and `-f UTF-16`; some builds use BOM-less UTF-16LE, others UTF-16 with BOM
- No `YYYYMMDD.log` created → tester never started; check `terminal64.exe` path and that `test.ini` was copied to `/config/test.ini` (not just host)
- `final balance` missing → EA may use custom `Print("STATS:")` instead; grep `STATS` or `phoenix` wide
- VNC shows `Market closed` → use valid XAUUSD history range or download history via `Tools` → `History Center` at `http://localhost:3000`
- Backtest stuck at 0% → ensure `2101202007` is connected (check VNC footer) and `.ex5` timestamp is fresh
