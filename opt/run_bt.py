#!/usr/bin/env python3
"""Headless MT5 backtest harness (docker container 'mt5').

Usage:
  python3 run_bt.py                 # run one backtest with current test.ini params
  python3 run_bt.py --params '{"InpTP_R":1.5}' --from 2026.07.01 --to 2026.08.01

Prints a JSON line with metrics. Appends to ledger.csv.
"""
import subprocess, re, html, os, sys, json, argparse, csv, time

DOCKER = "/Applications/Docker.app/Contents/Resources/bin/docker"
CONTAINER = "mt5"
M = "/config/.wine/drive_c/Program Files/MetaTrader 5"
HOST = os.path.dirname(os.path.abspath(__file__))
EXPERT = os.environ.get("MT5_EXPERT", "FiboAdaptiveEA_v4.72")
SYMBOL = os.environ.get("MT5_SYMBOL", "XAUUSDm")
LEDGER = os.path.join(HOST, "ledger.csv")


def sh(args, timeout=None, check=False):
    return subprocess.run(args, timeout=timeout, check=check,
                          capture_output=True, text=True)


def build_ini(fromdate, todate, params, deposit=100, leverage=2000, model=None):
    expert=os.environ.get("MT5_EXPERT", EXPERT)
    if model is None: model=int(os.environ.get("MT5_MODEL","1"))
    lines = [
        "[Tester]",
        f"Expert={expert}",
        f"Symbol={SYMBOL}",
        "Period=M5",
        f"FromDate={fromdate}",
        f"ToDate={todate}",
        f"Model={model}",
        f"Deposit={deposit}",
        f"Leverage={leverage}",
        "Currency=USD",
        "ForwardMode=0",
        "Report=ReportTester",
        "ReplaceReport=1",
        "ShutdownTerminal=1",
        "Visual=0",
    ]
    if params:
        lines.append("[TesterInputs]")
        for k, v in params.items():
            lines.append(f"{k}={v}")
    return "\n".join(lines) + "\n"


def run(ini_text, timeout=600):
    ini_local = os.path.join(HOST, "test.ini")
    with open(ini_local, "w") as f:
        f.write(ini_text)
    sh([DOCKER, "cp", ini_local, f"{CONTAINER}:{M}/test.ini"], check=True)
    # ensure no GUI terminal holds the tester config
    sh([DOCKER, "exec", CONTAINER, "bash", "-c",
        "pkill -f terminal64.exe; sleep 1"], check=False)
    # remove stale report so we never read an old one
    sh([DOCKER, "exec", CONTAINER, "bash", "-c",
        f"rm -f '{M}/ReportTester.htm'"], check=False)
    t0 = time.time()
    r = sh([DOCKER, "exec", "-w", M, CONTAINER, "wine",
            "terminal64.exe", "/config:test.ini"], timeout=timeout)
    dt = time.time() - t0
    sh([DOCKER, "cp", f"{CONTAINER}:{M}/ReportTester.htm",
        os.path.join(HOST, "report.htm")], check=True)
    return dt


def _num(t, key):
    i = t.find(key + ":")
    if i < 0:
        return None
    seg = t[i + len(key) + 1:i + len(key) + 120]
    m = re.search(r"(-?\d[\d\u00a0\u202f ,]*\.?\d*)", seg)
    if not m:
        return None
    return float(m.group(1).replace(",", "").replace("\u00a0", "")
                 .replace("\u202f", "").replace(" ", ""))


def parse():
    p = os.path.join(HOST, "report.htm")
    s = open(p, encoding="utf-16").read()
    t = html.unescape(re.sub(r"<[^>]+>", "|", s))
    t = re.sub(r"[ \t]+", " ", t)
    out = {
        "net": _num(t, "Total Net Profit"),
        "pf": _num(t, "Profit Factor"),
        "trades": _num(t, "Total Trades"),
        "gross_profit": _num(t, "Gross Profit"),
        "gross_loss": _num(t, "Gross Loss"),
        "payoff": _num(t, "Expected Payoff"),
        "recovery": _num(t, "Recovery Factor"),
        "dd_bal": _num(t, "Balance Drawdown Maximal"),
        "dd_eq": _num(t, "Equity Drawdown Maximal"),
    }
    # drawdown percent: "24.82 (15.49%)"
    i = t.find("Equity Drawdown Maximal:")
    if i >= 0:
        m = re.search(r"\(\s*([\d.]+)%", t[i:i + 200])
        out["dd_pct"] = float(m.group(1)) if m else None
    # win rate
    m = re.search(r"Profit Trades \(% of total\):\s*\|\s*\|?\s*(\d+)\s*\(([\d.]+)%", t)
    if m:
        out["wins"] = int(m.group(1))
        out["win_pct"] = float(m.group(2))
    return out


def parse_deals():
    """Return list of (date_str, profit_float) for out-deals (closed trades)."""
    p = os.path.join(HOST, "report.htm")
    s = open(p, encoding="utf-16").read()
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", s, flags=re.S | re.I)
    out = []
    header = None
    for r in rows:
        c = [html.unescape(re.sub(r"<[^>]+>", "", x)).strip()
             for x in re.findall(r"<td[^>]*>(.*?)</td>", r, flags=re.S | re.I)]
        if c and c[0] == "Time" and "Profit" in c:
            header = c
            continue
        if header and len(c) >= len(header) and c[0][:2] == "20":
            try:
                di = header.index("Direction")
                pi = header.index("Profit")
            except ValueError:
                continue
            if c[di] != "out":
                continue
            prof = float(c[pi].replace(" ", "").replace("\u00a0", "")
                         .replace("\u202f", "") or 0)
            out.append((c[0][:10], prof))
    return out


def daily_pnl():
    """Aggregate realized daily P/L: {date: [profit...]}."""
    d = {}
    for date, prof in parse_deals():
        d.setdefault(date, []).append(prof)
    return {k: sum(v) for k, v in d.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--params", default="{}")
    ap.add_argument("--from", dest="fromdate", default="2026.07.01")
    ap.add_argument("--to", dest="todate", default="2026.08.01")
    ap.add_argument("--tag", default="")
    ap.add_argument("--model", type=int, default=1)
    ap.add_argument("--deposit", type=float, default=100)
    ap.add_argument("--leverage", type=int, default=2000)
    a = ap.parse_args()

    params = json.loads(a.params)
    ini = build_ini(a.fromdate, a.todate, params, deposit=a.deposit,
                    leverage=a.leverage, model=a.model)
    dt = run(ini)
    m = parse()
    m["tag"] = a.tag
    m["from"] = a.fromdate
    m["to"] = a.todate
    m["secs"] = round(dt, 1)
    m["params"] = params
    print(json.dumps(m))

    fields = ["tag", "from", "to", "net", "pf", "trades", "gross_profit",
              "gross_loss", "payoff", "recovery", "dd_bal", "dd_eq",
              "dd_pct", "wins", "win_pct", "secs", "params"]
    new = not os.path.exists(LEDGER)
    with open(LEDGER, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new:
            w.writeheader()
        w.writerow({k: m.get(k) for k in fields})


if __name__ == "__main__":
    main()
