from mt5linux import MetaTrader5
from datetime import datetime
import numpy as np

mt5 = MetaTrader5("localhost", 8001)
mt5.initialize()
mt5.symbol_select("XAUUSDm", True)

CH = 20000
MAX = 2000000
rows = []
start = 0
while start < MAX:
    r = mt5.copy_rates_from_pos("XAUUSDm", mt5.TIMEFRAME_M1, start, CH)
    if r is None or len(r) == 0:
        break
    rows.append(r)
    print("start", start, "got", len(r), flush=True)
    if len(r) < CH:
        break
    start += CH

a = np.concatenate(rows)
t = a["time"]
_, idx = np.unique(t, return_index=True)
a = a[np.sort(idx)]

with open("/config/xauusdm_m1.csv", "w") as f:
    f.write("time_utc,open,high,low,close,volume\n")
    for x in a:
        ts = datetime.utcfromtimestamp(int(x["time"])).strftime("%Y-%m-%d %H:%M:%S")
        f.write("%s,%.3f,%.3f,%.3f,%.3f,%d\n" % (
            ts, x["open"], x["high"], x["low"], x["close"], x["tick_volume"]))

print("TOTAL", len(a),
      "oldest", datetime.utcfromtimestamp(int(a[0]["time"])),
      "newest", datetime.utcfromtimestamp(int(a[-1]["time"])))
