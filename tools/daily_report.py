#!/usr/bin/env python3
"""Day-by-day P/L from an MT5 strategy-tester HTML report.

Unlike tools/daily.py (which pairs the EA's own MFELOG lines and therefore
under-counts any config that uses partial closes), this reads the report's
Deals table, where every partial close is its own row with a Profit value.

Usage:
  python3 tools/daily_report.py /tmp/r76sep.htm
"""

import re
import sys
from collections import OrderedDict

ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
TD = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
DATE = re.compile(r"^(\d{4}\.\d{2}\.\d{2}) ")


def read(path):
    raw = open(path, "rb").read()
    for enc in ("utf-16", "utf-8", "cp1252"):
        try:
            t = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    return t


def parse(path):
    text = read(path)
    rows = OrderedDict()
    n = 0
    for m in ROW.finditer(text):
        tds = [re.sub(r"<[^>]+>", "", x).strip() for x in TD.findall(m.group(1))]
        if len(tds) < 12:
            continue
        d = DATE.match(tds[0])
        if not d:
            continue
        if tds[3] in ("balance", ""):
            continue
        try:
            profit = float(tds[10].replace(" ", "") or 0)
        except ValueError:
            continue
        day = d.group(1)
        win = profit > 0
        rows.setdefault(day, [0.0, 0, 0])
        rows[day][0] += profit
        rows[day][1] += 1
        if win:
            rows[day][2] += 1
        n += 1
    return rows, n


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    rows, n = parse(sys.argv[1])
    print("%-12s %10s %8s %6s %6s" % ("day", "P/L", "deals", "win", "loss"))
    for d, (pl, cnt, w) in rows.items():
        print("%-12s %10.2f %8d %6d %6d" % (d, pl, cnt, w, cnt - w))
    tot = sum(v[0] for v in rows.values())
    wd = sum(1 for v in rows.values() if v[0] > 0)
    ld = sum(1 for v in rows.values() if v[0] < 0)
    print()
    print("days=%d winning=%d losing=%d flat=%d  total P/L %.2f  (closing deals=%d)" %
          (len(rows), wd, ld, len(rows) - wd - ld, tot, n))


if __name__ == "__main__":
    main()
