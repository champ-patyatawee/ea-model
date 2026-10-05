"""MT5 bridge via raw rpyc (bypasses mt5linux's broken dict/datetime f-strings).

mt5linux 0.1.9 builds `mt5.order_check(*{args},**{kwargs})` with an f-string, which
cannot serialise a dict or a tz-aware datetime. We talk to the same rpyc server on
port 8001 directly and build request dicts *inside* the Wine process, then eval.
"""
from __future__ import annotations
import rpyc


class MT5:
    def __init__(self, host: str = "localhost", port: int = 8001):
        self.host = host
        self.port = port
        self.conn = None
        self._connect()

    def _connect(self):
        self.conn = rpyc.classic.connect(self.host, self.port)
        self.conn.execute("import MetaTrader5 as mt5")
        if not self.conn.eval("mt5.initialize()"):
            raise RuntimeError(f"mt5.initialize failed: {self.conn.eval('mt5.last_error()')}")

    def reconnect(self):
        """Drop and re-open the rpyc connection (bridge restarts, EOF, etc.)."""
        try:
            if self.conn is not None:
                self.conn.close()
        except Exception:
            pass
        self._connect()

    # ---- read ----------------------------------------------------------------
    def account(self) -> dict:
        self.conn.execute("_acc = mt5.account_info()")
        if self.conn.eval("_acc is None"):
            return {}
        return {
            "login": self.conn.eval("_acc.login"),
            "server": self.conn.eval("_acc.server"),
            "balance": self.conn.eval("_acc.balance"),
            "equity": self.conn.eval("_acc.equity"),
            "currency": self.conn.eval("_acc.currency"),
            "trade_mode": self.conn.eval("_acc.trade_mode"),
        }

    def symbol_info(self, symbol: str) -> dict:
        self.conn.execute(f'mt5.symbol_select("{symbol}", True)')
        self.conn.execute(f'_si = mt5.symbol_info("{symbol}")')
        if self.conn.eval("_si is None"):
            return {}
        keys = ["digits", "point", "trade_contract_size", "volume_min", "volume_step",
                "volume_max", "trade_stops_level", "spread", "ask", "bid", "filling_mode"]
        return {k: self.conn.eval(f"_si.{k}") for k in keys}

    def fetch_h1(self, symbol: str, count: int):
        """Return list of dicts (oldest->newest) of H1 bars."""
        self.conn.execute(f'mt5.symbol_select("{symbol}", True)')
        self.conn.execute(
            f'_h1 = mt5.copy_rates_from_pos("{symbol}", mt5.TIMEFRAME_H1, 0, {int(count)})')
        return self._rates_to_list("_h1")

    def fetch_m1(self, symbol: str, count: int):
        self.conn.execute(f'mt5.symbol_select("{symbol}", True)')
        self.conn.execute(
            f'_m1 = mt5.copy_rates_from_pos("{symbol}", mt5.TIMEFRAME_M1, 0, {int(count)})')
        return self._rates_to_list("_m1")

    def _rates_to_list(self, var: str):
        self.conn.execute("import numpy as _np")
        return self.conn.eval(
            f"[(int(r['time']), float(r['open']), float(r['high']), float(r['low']), "
            f"float(r['close']), int(r['tick_volume'])) for r in {var}]"
        )

    def positions(self, symbol: str, magic: int):
        self.conn.execute(f'_pos = mt5.positions_get(symbol="{symbol}")')
        if self.conn.eval("_pos is None"):
            return []
        return self.conn.eval(
            f"[dict(ticket=p.ticket, dir=d, volume=p.volume, price_open=p.price_open, "
            f"sl=p.sl, tp=p.tp, profit=p.profit) "
            f"for p in _pos for d in [1 if p.type==mt5.POSITION_TYPE_BUY else -1] "
            f"if p.magic=={int(magic)}]"
        )

    # ---- trade ---------------------------------------------------------------
    def market_order(self, symbol: str, direction: int, volume: float, sl: float, tp: float,
                     magic: int, deviation: int = 50) -> dict:
        """direction: 1 buy, -1 sell. sl/tp absolute prices (0 = none)."""
        otype = "mt5.ORDER_TYPE_BUY" if direction == 1 else "mt5.ORDER_TYPE_SELL"
        price = "s.ask" if direction == 1 else "s.bid"
        self.conn.execute(f'mt5.symbol_select("{symbol}", True)')
        self.conn.execute(
            f'''
s = mt5.symbol_info("{symbol}")
req = dict(action=mt5.TRADE_ACTION_DEAL, symbol="{symbol}", volume=float({volume}),
           type={otype}, price={price}, sl=float({sl}), tp=float({tp}),
           deviation={deviation}, magic={magic}, comment="rl_v3_live",
           type_time=mt5.ORDER_TIME_GTC, type_filling=mt5.ORDER_FILLING_IOC)
res = mt5.order_send(req)
''')
        return {
            "retcode": self.conn.eval("res.retcode"),
            "order": self.conn.eval("res.order"),
            "volume": self.conn.eval("res.volume"),
            "price": self.conn.eval("res.price"),
            "comment": self.conn.eval("res.comment"),
        }

    def close_position(self, position_ticket: int, symbol: str, direction: int, volume: float,
                       magic: int, deviation: int = 50) -> dict:
        """Close by opposite market deal (hedging-safe)."""
        otype = "mt5.ORDER_TYPE_SELL" if direction == 1 else "mt5.ORDER_TYPE_BUY"
        price = "s.bid" if direction == 1 else "s.ask"
        self.conn.execute(f'mt5.symbol_select("{symbol}", True)')
        self.conn.execute(
            f'''
s = mt5.symbol_info("{symbol}")
req = dict(action=mt5.TRADE_ACTION_DEAL, symbol="{symbol}", volume=float({volume}),
           type={otype}, price={price}, position={int(position_ticket)},
           deviation={deviation}, magic={magic}, comment="rl_v3_close",
           type_time=mt5.ORDER_TIME_GTC, type_filling=mt5.ORDER_FILLING_IOC)
res = mt5.order_send(req)
''')
        return {
            "retcode": self.conn.eval("res.retcode"),
            "order": self.conn.eval("res.order"),
            "comment": self.conn.eval("res.comment"),
        }

    def modify_position(self, position_ticket: int, sl: float, tp: float) -> dict:
        self.conn.execute(
            f'''
req = dict(action=mt5.TRADE_ACTION_SLTP, position={int(position_ticket)},
           sl=float({sl}), tp=float({tp}))
res = mt5.order_send(req)
''')
        return {"retcode": self.conn.eval("res.retcode"), "comment": self.conn.eval("res.comment")}

    @staticmethod
    def retcode_done() -> int:
        return 10009

    def retcode_code(self, name: str) -> int:
        return self.conn.eval(f"mt5.{name}")
