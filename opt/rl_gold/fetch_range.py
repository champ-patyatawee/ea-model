"""Fetch an MT5 M1 date range via the raw rpyc bridge and write it to CSV.

Run inside the `rl` container (which has rpyc):
    python3 /work/rl_gold/fetch_range.py <host> <port> <out_path> <start> <end> [symbol]

<start>/<end> are UTC dates "YYYY-MM-DD" (end exclusive). The file is written
*inside* the Wine process (mt5 container); copy it out with:
    docker cp mt5:<out_path> /path/on/host
"""
from __future__ import annotations
import sys

import rpyc


def main():
    host = sys.argv[1]
    port = int(sys.argv[2])
    out = sys.argv[3]
    start = sys.argv[4]
    end = sys.argv[5]
    symbol = sys.argv[6] if len(sys.argv) > 6 else "XAUUSDm"

    conn = rpyc.classic.connect(host, port)
    conn.execute("import MetaTrader5 as mt5")
    if not conn.eval("mt5.initialize()"):
        raise SystemExit(f"mt5.initialize failed: {conn.eval('mt5.last_error()')}")
    conn.execute(f'mt5.symbol_select("{symbol}", True)')

    code = f'''
import MetaTrader5 as mt5
import datetime as _dt
_fm = _dt.datetime.strptime("{start}", "%Y-%m-%d")
_to = _dt.datetime.strptime("{end}", "%Y-%m-%d")
_r = mt5.copy_rates_range("{symbol}", mt5.TIMEFRAME_M1, _fm, _to)
_n = 0 if _r is None else len(_r)
if _n:
    with open(r"{out}", "w") as f:
        f.write("time_utc,open,high,low,close,volume\\n")
        for x in _r:
            ts = _dt.datetime.utcfromtimestamp(int(x["time"])).strftime("%Y-%m-%d %H:%M:%S")
            f.write("%s,%.3f,%.3f,%.3f,%.3f,%d\\n" % (
                ts, x["open"], x["high"], x["low"], x["close"], int(x["tick_volume"])))
'''
    conn.execute(code)
    n = conn.eval("_n")
    print(f"rows={n}  wrote={out}", flush=True)


if __name__ == "__main__":
    main()
