---
name: mt5-chart-close
description: Diagnose and clean the flood of XAUUSD Strategy Tester charts in the mt5 VNC and prevent recurrence
license: MIT
compatibility: opencode
metadata:
  audience: developers
---

## What I do

- Diagnose why `http://localhost:3000` (VNC, port 3000) is flooded with dozens of `XAUUSD` charts after a Strategy Tester run
- Locate the chart profile files at `MQL5/Profiles/Charts/Default/chart*.chr` and `profiles/Charts/Default/chart0*.chr` inside the Wine prefix
- Remove the 21+ stale `chart*.chr` files and restart the `mt5` container to force a clean chart window on next VNC connect
- Verify the fix via `browseros-neo` screenshot at `http://localhost:3000`
- Prevent recurrence by disabling Tester visual mode or auto-deleting chart files post-test

## When to use me

- After any Strategy Tester backtest with **visual mode ON** (`Visual=1` / "visual mode with the display" checked) and VNC now shows 10–30 overlapping `XAUUSD` charts
- Before starting a new backtest when the chart area is unreadable and you need a single clean chart
- When `docker exec mt5 find ... -name "*.chr"` returns ~21 files in `MQL5/Profiles/Charts/Default/`
- As a post-backtest cleanup step in an automated loop that runs many `mt5-backtest-and-read` cycles

## Usage

### Prerequisites

- Docker container `mt5` running: `/Applications/Docker.app/Contents/Resources/bin/docker ps | grep mt5` shows `gmag11/metatrader5_vnc`
- MT5 account `2101202007` (IUX Demo) — chart flood is per-profile, so `Default` profile is the target
- VNC accessible at `http://localhost:3000` (port 3000 VNC/noVNC, port 8001 Python bridge) — used for visual verification
- Absolute Docker binary: `/Applications/Docker.app/Contents/Resources/bin/docker`
- `browseros-neo` skill available for automated screenshot verification (optional but recommended)

### Step 1 — Diagnose: count and list chart files

```bash
# Count chart files in the two known locations
/Applications/Docker.app/Contents/Resources/bin/docker exec mt5 bash -c '
  echo "=== MQL5/Profiles/Charts/Default ==="
  find "/config/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Profiles/Charts/Default" -maxdepth 1 -name "chart*.chr" 2>/dev/null | head -30
  echo "count: $(find "/config/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Profiles/Charts/Default" -maxdepth 1 -name "chart*.chr" 2>/dev/null | wc -l)"
  echo ""
  echo "=== profiles/Charts/Default ==="
  find "/config/.wine/drive_c/Program Files/MetaTrader 5/profiles/Charts/Default" -maxdepth 1 -name "chart*.chr" 2>/dev/null | head -30
  echo "count: $(find "/config/.wine/drive_c/Program Files/MetaTrader 5/profiles/Charts/Default" -maxdepth 1 -name "chart*.chr" 2>/dev/null | wc -l)"
'

# Quick single-command diagnosis (count + list)
/Applications/Docker.app/Contents/Resources/bin/docker exec mt5 find "/config/.wine/drive_c/Program Files/MetaTrader 5" -name "chart*.chr" 2>/dev/null | head -30
/Applications/Docker.app/Contents/Resources/bin/docker exec mt5 bash -c 'find "/config/.wine/drive_c/Program Files/MetaTrader 5" -name "chart*.chr" 2>/dev/null | wc -l; echo "total chart*.chr files"'

# Mac native equivalent diagnosis
find "$HOME/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5" -name "chart*.chr" 2>/dev/null | head -30
find "$HOME/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5" -name "chart*.chr" 2>/dev/null | wc -l
```

If you see **~21 files** like `chart01.chr`, `chart02.chr` ... `chart21.chr` in `MQL5/Profiles/Charts/Default/`, this is the visual-mode Tester flood — proceed to fix.

### Step 2 — Visual confirmation via VNC screenshot (optional but recommended)

Use `browseros-neo` to capture the flooded state before fixing:

```js
// Run via browseros-neo browser SDK
const page = await browser.pages.newPage("http://localhost:3000");
await browser.wait(page, { for: "selector", value: "canvas", timeout: 15000 });
await browser.screenshot(page); // verify: many overlapping XAUUSD charts
// Or via CLI skill wrapper: browserclaw / browseros-neo snapshot at http://localhost:3000
```

Expected flooded screenshot: tab bar shows `XAUUSD` repeated, chart area tiled with many identical candles, Navigator/Toolbox obscured.

### Step 3 — Fix: delete chart files and restart

```bash
# Delete ALL Tester-generated chart files in both locations
/Applications/Docker.app/Contents/Resources/bin/docker exec mt5 bash -c '
  rm -fv "/config/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Profiles/Charts/Default/chart"*.chr 2>&1 | head -30
  rm -fv "/config/.wine/drive_c/Program Files/MetaTrader 5/profiles/Charts/Default/chart0"*.chr 2>&1 | head -30
  echo "--- after delete ---"
  find "/config/.wine/drive_c/Program Files/MetaTrader 5" -name "chart*.chr" 2>/dev/null | wc -l; echo "remaining chart*.chr files"
'

# Alternative broad delete (covers both paths in one)
/Applications/Docker.app/Contents/Resources/bin/docker exec mt5 bash -c 'find "/config/.wine/drive_c/Program Files/MetaTrader 5" -name "chart*.chr" -delete 2>/dev/null; echo "deleted"; find "/config/.wine/drive_c/Program Files/MetaTrader 5" -name "chart*.chr" 2>/dev/null | wc -l; echo "remaining"'

# Restart container to force MT5 to regenerate a single default chart
/Applications/Docker.app/Contents/Resources/bin/docker restart mt5

# Wait for MT5 to come back (VNC takes 15-30s)
/Applications/Docker.app/Contents/Resources/bin/docker ps | grep mt5
sleep 20
/Applications/Docker.app/Contents/Resources/bin/docker exec mt5 bash -c 'ls -lh "/config/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Profiles/Charts/Default/" | head -20'
```

> **Note on `profiles` vs `MQL5/Profiles`:** Both exist. `MQL5/Profiles/Charts/Default/` is the Tester visual-mode flood (21 files). `profiles/Charts/Default/` is the main terminal profile. Delete both `chart*.chr` sets to guarantee a clean slate — MT5 will recreate `chart01.chr` on next launch.

### Step 4 — Verify fix via VNC screenshot

```bash
# Container should show 0-1 chart files after restart
/Applications/Docker.app/Contents/Resources/bin/docker exec mt5 bash -c 'find "/config/.wine/drive_c/Program Files/MetaTrader 5" -name "chart*.chr" 2>/dev/null | head -10; echo "---"; ls -lh "/config/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Profiles/Charts/Default/" 2>/dev/null | head -10'
```

Then re-screenshot VNC:

```js
const page = await browser.pages.newPage("http://localhost:3000");
await browser.wait(page, { for: "selector", value: "canvas", timeout: 20000 });
await browser.screenshot(page); // verify: single clean chart, no flood
```

Expected clean screenshot: single `XAUUSD` chart, no tiled duplicates, Toolbox/Navigator visible.

### Step 5 — Prevent recurrence

#### Option A — Disable visual mode (recommended for automation)

In `test.ini` for headless runs (`mt5-backtest-and-read`):

```ini
[Tester]
Visual=0
```

In VNC GUI: `Strategy Tester` panel → **uncheck** `visual mode with the display` before clicking `Start`.

This prevents Tester from writing any `chart*.chr` files at all.

#### Option B — Auto-delete after each test (if visual mode needed)

Append to your backtest automation after reading logs:

```bash
/Applications/Docker.app/Contents/Resources/bin/docker exec mt5 bash -c '
  LOG=$(ls -t "/config/.wine/drive_c/Program Files/MetaTrader 5/Tester/logs/"*.log | head -1)
  iconv -f UTF-16 -t UTF-8 "$LOG" 2>/dev/null | grep -qi "final balance" && \
  find "/config/.wine/drive_c/Program Files/MetaTrader 5" -name "chart*.chr" -delete 2>/dev/null && \
  echo "cleaned chart*.chr after successful test"
'
```

#### Option C — Keep visual mode but close charts manually (VNC)

If you must watch a visual test once, then clean:

1. Let visual test finish, read results.
2. In VNC at `http://localhost:3000`: right-click each duplicate chart tab → `Close`, or run the `rm -f .../*.chr` + `docker restart mt5` fix above before the next test.

## Format / Templates

### Diagnosis template

```
/Applications/Docker.app/Contents/Resources/bin/docker exec mt5 bash -c 'find "/config/.wine/drive_c/Program Files/MetaTrader 5" -name "chart*.chr" 2>/dev/null | head -30; echo "---"; find "/config/.wine/drive_c/Program Files/MetaTrader 5" -name "chart*.chr" 2>/dev/null | wc -l'
```

### Fix template (delete + restart)

```
/Applications/Docker.app/Contents/Resources/bin/docker exec mt5 bash -c 'rm -f "/config/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Profiles/Charts/Default/"*.chr "/config/.wine/drive_c/Program Files/MetaTrader 5/profiles/Charts/Default/chart0"*.chr 2>/dev/null; echo "deleted"'
/Applications/Docker.app/Contents/Resources/bin/docker restart mt5
sleep 20
```

### Verification template

```
/Applications/Docker.app/Contents/Resources/bin/docker exec mt5 bash -c 'find "/config/.wine/drive_c/Program Files/MetaTrader 5" -name "chart*.chr" 2>/dev/null | wc -l; echo "remaining charts"'
# then screenshot http://localhost:3000 via browseros-neo
```

### Prevention template (test.ini)

```ini
[Tester]
Visual=0
```

## Workflow

1. **Pre-check** — Confirm `mt5` container up, VNC at `http://localhost:3000` shows chart flood, account `2101202007` still connected.
2. **Diagnose** — `docker exec mt5 find ... -name "chart*.chr" | head` and `| wc -l` — expect ~21 files in `MQL5/Profiles/Charts/Default/`; screenshot VNC via `browseros-neo` for before/after record.
3. **Delete** — `docker exec mt5 rm -f ".../MQL5/Profiles/Charts/Default/*.chr" ".../profiles/Charts/Default/chart0*.chr"` (or broad `find ... -delete`).
4. **Restart** — `docker restart mt5` then `sleep 20` for Wine/MT5 to fully reload.
5. **Verify** — `find ... -name "chart*.chr" | wc -l` should be `0` or `1`; screenshot `http://localhost:3000` again — single clean chart expected.
6. **Prevent** — Set `Visual=0` in `test.ini` or uncheck `visual mode with the display` in Tester GUI; alternatively auto-delete `chart*.chr` after each backtest in your loop.

## Troubleshooting

- `rm: cannot remove ... No such file or directory` → path case-sensitive; check `MQL5/Profiles/Charts/Default` vs `profiles/Charts/Default` (lowercase `profiles`) — run both `rm` commands
- Charts reappear immediately after restart → a detached Tester run is still writing; ensure no `terminal64.exe /config:test.ini` is still running via `docker exec mt5 ps aux | grep terminal`
- VNC shows black screen after restart → normal for 15-30s while Wine boots; wait and refresh `http://localhost:3000`
- `find` returns 0 but VNC still flooded → VNC is caching; hard refresh (`Ctrl+F5`) or close/reopen the `browseros-neo` page at `http://localhost:3000`
- Mac native flood → same `rm` but at `~/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/...` then restart `MetaTrader 5.app`
