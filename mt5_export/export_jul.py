from mt5linux import MetaTrader5
from datetime import datetime, timezone
import numpy as np, sys, calendar

YEAR = int(sys.argv[1]) if len(sys.argv) > 1 else 2025
MON  = int(sys.argv[2]) if len(sys.argv) > 2 else 7
out  = f"/config/xauusdm_m1_{YEAR}{MON:02d}.csv"

mt5 = MetaTrader5("localhost", 8001)
if not mt5.initialize():
    print("init failed", mt5.last_error()); sys.exit(1)
mt5.symbol_select("XAUUSDm", True)

CH = 50000
MAX = 1500000
rows = []
start = 0
while start < MAX:
    r = mt5.copy_rates_from_pos("XAUUSDm", mt5.TIMEFRAME_M1, start, CH)
    if r is None or len(r) == 0:
        break
    rows.append(r)
    if len(r) < CH:
        break
    start += CH

a = np.concatenate(rows)
t = a["time"]
_, idx = np.unique(t, return_index=True)
a = a[np.sort(idx)]

lo = int(datetime(YEAR, MON, 1, tzinfo=timezone.utc).timestamp())
nxt = datetime(YEAR+1,1,1,tzinfo=timezone.utc) if MON==12 else datetime(YEAR,MON+1,1,tzinfo=timezone.utc)
hi = int(nxt.timestamp())
a = a[(a["time"] >= lo) & (a["time"] < hi)]

with open(out, "w") as f:
    f.write("time_utc,open,high,low,close,volume\n")
    for x in a:
        ts = datetime.fromtimestamp(int(x["time"]), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        f.write("%s,%.3f,%.3f,%.3f,%.3f,%d\n" % (
            ts, x["open"], x["high"], x["low"], x["close"], x["tick_volume"]))

print("TOTAL_ALL", len(rows) and sum(len(x) for x in rows))
print("WROTE", out, "bars", len(a),
      "from", datetime.fromtimestamp(int(a[0]["time"]), tz=timezone.utc) if len(a) else None,
      "to", datetime.fromtimestamp(int(a[-1]["time"]), tz=timezone.utc) if len(a) else None)
