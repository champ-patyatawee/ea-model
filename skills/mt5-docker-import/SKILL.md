---
name: mt5-docker-import
description: Import .mq5/.ex5 files into the gmag11/metatrader5_vnc Docker container (mt5) and compile with MetaEditor64
license: MIT
compatibility: opencode
metadata:
  audience: developers
---

## What I do

- Copy `.mq5` source files from host `/Users/champp/Champ/PhoenixEA/` into the Docker MT5 container `mt5` (image `gmag11/metatrader5_vnc`)
- Place files at the two canonical Experts locations inside the container's Wine prefix
- Compile via `MetaEditor64.exe /compile` inside the container and verify the UTF-16LE log for errors/warnings
- Mirror the same workflow for the **Mac native MT5** Wine prefix at `~/Library/Application Support/net.metaquotes.wine.metatrader5/`
- Verify `.ex5` generation with `ls -lh` and copy to `Advisors/` subfolder

## When to use me

- After editing any `Phoenix*.mq5`, `*.mq5` in `/Users/champp/Champ/PhoenixEA/` and needing to test in the Docker MT5 VNC at `http://localhost:3000`
- When `docker exec mt5 ls` does not show the latest `.mq5` timestamp inside the container
- Before running a Strategy Tester backtest — compiled `.ex5` must exist and be error-free
- When switching between Docker MT5 and Mac native MT5 (`/Applications/MetaTrader 5.app`) and needing both in sync

## Usage

### Prerequisites

- Docker container `mt5` is running: `/Applications/Docker.app/Contents/Resources/bin/docker ps | grep mt5` must show `gmag11/metatrader5_vnc`
- Docker binary absolute path: `/Applications/Docker.app/Contents/Resources/bin/docker` (use this, not bare `docker`)
- Account `2101202007` on `IUX Demo` server is logged in inside MT5 (check VNC at `http://localhost:3000` — port 3000 VNC, port 8001 Python bridge)
- Host source directory exists: `/Users/champp/Champ/PhoenixEA/`
- Container Wine prefix exists: `/config/.wine/drive_c/Program Files/MetaTrader 5/` inside `mt5`

### Step 1 — Verify container is up

```bash
/Applications/Docker.app/Contents/Resources/bin/docker ps --format "{{.Names}} {{.Image}} {{.Status}}" | grep mt5
/Applications/Docker.app/Contents/Resources/bin/docker exec mt5 ls -lh "/config/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Experts/" | head -20
```

### Step 2 — Copy .mq5 from host into container (Experts)

```bash
# Single file — replace <File> with actual name, e.g. PhoenixEA
/Applications/Docker.app/Contents/Resources/bin/docker cp /Users/champp/Champ/PhoenixEA/PhoenixEA.mq5 "mt5:/config/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Experts/PhoenixEA.mq5"

# Bulk copy all mq5 files (loop to preserve spaces in Wine path)
/Applications/Docker.app/Contents/Resources/bin/docker cp /Users/champp/Champ/PhoenixEA/PhoenixAdaptive.mq5 "mt5:/config/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Experts/"
/Applications/Docker.app/Contents/Resources/bin/docker cp /Users/champp/Champ/PhoenixEA/PhoenixAllWeather.mq5 "mt5:/config/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Experts/"
# ... repeat for each Phoenix*.mq5 or use a loop:
for f in /Users/champp/Champ/PhoenixEA/*.mq5; do
  /Applications/Docker.app/Contents/Resources/bin/docker cp "$f" "mt5:/config/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Experts/"
done
```

### Step 3 — Copy to Advisors/ subfolder (required by some MT5 builds)

```bash
/Applications/Docker.app/Contents/Resources/bin/docker exec mt5 bash -c 'cp -v "/config/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Experts/PhoenixEA.mq5" "/config/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Experts/Advisors/PhoenixEA.mq5"'

# Bulk Advisors copy
/Applications/Docker.app/Contents/Resources/bin/docker exec mt5 bash -c 'for f in "/config/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Experts/"*.mq5; do cp -v "$f" "/config/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Experts/Advisors/"; done; ls -lh "/config/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Experts/Advisors/" | head -20'
```

### Step 4 — Compile inside container via MetaEditor64

```bash
# Compile a single file — working dir MUST be the MT5 root so MQL5/Experts/<File>.mq5 resolves
/Applications/Docker.app/Contents/Resources/bin/docker exec -w "/config/.wine/drive_c/Program Files/MetaTrader 5" mt5 wine MetaEditor64.exe /compile:"MQL5/Experts/PhoenixEA.mq5" /log

# Wait 8-15 seconds for compilation, then check log (UTF-16LE)
sleep 10
/Applications/Docker.app/Contents/Resources/bin/docker exec mt5 bash -c 'iconv -f UTF-16LE -t UTF-8 "/config/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Experts/PhoenixEA.log" 2>/dev/null | grep -iE "error|warning|Result|compiled" | head -20'

# Alternative log location check (Advisors subfolder)
/Applications/Docker.app/Contents/Resources/bin/docker exec mt5 bash -c 'iconv -f UTF-16LE -t UTF-8 "/config/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Experts/Advisors/PhoenixEA.log" 2>/dev/null | grep -iE "error|warning|Result" | head -20'
```

Expected success log line:

```
Result: 0 error(s), 0 warning(s)
```

If you see `error(s)` > 0, fix source and re-copy/re-compile.

### Step 5 — Verify .ex5 generation

```bash
/Applications/Docker.app/Contents/Resources/bin/docker exec mt5 bash -c 'ls -lh "/config/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Experts/"*.ex5 | head -20'
/Applications/Docker.app/Contents/Resources/bin/docker exec mt5 bash -c 'ls -lh "/config/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Experts/Advisors/"*.ex5 | head -20'
# Timestamps should be within the last minute and file size > 0
```

### Step 6 — Mac native MT5 (parallel path, when needed)

```bash
# Host path for Mac Wine MT5 (note: space in "Application Support")
MAC_MQL5="$HOME/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5"

# Copy to Mac-native Experts and Advisors
cp -v /Users/champp/Champ/PhoenixEA/PhoenixEA.mq5 "$MAC_MQL5/Experts/PhoenixEA.mq5"
cp -v /Users/champp/Champ/PhoenixEA/PhoenixEA.mq5 "$MAC_MQL5/Experts/Advisors/PhoenixEA.mq5"

# Compile via Wine bundled inside MetaTrader 5.app — MUST set WINEPREFIX
WINEPREFIX="$HOME/Library/Application Support/net.metaquotes.wine.metatrader5" \
  /Applications/MetaTrader\ 5.app/Contents/SharedSupport/wine/bin/wine \
  "$HOME/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MetaEditor64.exe" \
  /compile:"MQL5/Experts/PhoenixEA.mq5" /log

# Verify Mac log (UTF-16LE)
/usr/bin/iconv -f UTF-16LE -t UTF-8 "$MAC_MQL5/Experts/PhoenixEA.log" 2>/dev/null | grep -iE "error|warning|Result"
ls -lh "$MAC_MQL5/Experts/"*.ex5 | head -20
ls -lh "$MAC_MQL5/Experts/Advisors/"*.ex5 | head -20
```

## Format / Templates

### Docker cp template

```
/Applications/Docker.app/Contents/Resources/bin/docker cp /Users/champp/Champ/PhoenixEA/<File>.mq5 "mt5:/config/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Experts/<File>.mq5"
```

### Advisors mirror template

```
/Applications/Docker.app/Contents/Resources/bin/docker exec mt5 bash -c 'cp -v "/config/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Experts/<File>.mq5" "/config/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Experts/Advisors/<File>.mq5"'
```

### Compile template (Docker)

```
/Applications/Docker.app/Contents/Resources/bin/docker exec -w "/config/.wine/drive_c/Program Files/MetaTrader 5" mt5 wine MetaEditor64.exe /compile:"MQL5/Experts/<File>.mq5" /log
```

### Log verification template

```
/Applications/Docker.app/Contents/Resources/bin/docker exec mt5 bash -c 'iconv -f UTF-16LE -t UTF-8 "/config/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Experts/<File>.log" | grep -iE "error|warning|Result"'
```

### Mac native template

```
WINEPREFIX="$HOME/Library/Application Support/net.metaquotes.wine.metatrader5" /Applications/MetaTrader\ 5.app/Contents/SharedSupport/wine/bin/wine "$HOME/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MetaEditor64.exe" /compile:"MQL5/Experts/<File>.mq5" /log
```

## Workflow

1. **Pre-check** — Confirm `mt5` container is up and VNC at `http://localhost:3000` shows account `2101202007` (IUX Demo) connected.
2. **Copy** — `docker cp` each `.mq5` from `/Users/champp/Champ/PhoenixEA/` into both `.../MQL5/Experts/` and `.../MQL5/Experts/Advisors/` inside container.
3. **Compile** — `docker exec -w ".../MetaTrader 5" mt5 wine MetaEditor64.exe /compile:"MQL5/Experts/<File>.mq5" /log` — wait 10s.
4. **Verify log** — `iconv -f UTF-16LE -t UTF-8 .../<File>.log | grep -iE "error|warning|Result"` must show `0 error(s)`.
5. **Verify binary** — `ls -lh .../*.ex5` shows fresh timestamp and non-zero size in both `Experts/` and `Advisors/`.
6. **Mac sync (if needed)** — `cp` to `~/Library/Application Support/net.metaquotes.wine.metatrader5/.../MQL5/Experts/` and compile with `WINEPREFIX=... /Applications/MetaTrader\ 5.app/Contents/SharedSupport/wine/bin/wine ... MetaEditor64.exe /compile:... /log`, then `iconv` verify.
7. **Ready to test** — EA now appears in Navigator > Expert Advisors inside MT5; proceed to backtest skill `mt5-backtest-and-read`.

## Troubleshooting

- `docker: command not found` → always use absolute path `/Applications/Docker.app/Contents/Resources/bin/docker`
- `cannot stat` on `docker cp` → check host file exists at `/Users/champp/Champ/PhoenixEA/<File>.mq5` and quote container path with spaces
- Log file not found → compilation still running; `sleep 5` and retry, or check `Advisors/<File>.log` variant
- `wine: command not found` inside container → use `wine64` or check `which wine` via `docker exec mt5 which wine`
- Mac compile needs `WINEPREFIX` — without it wine creates a new prefix and compile silently fails
