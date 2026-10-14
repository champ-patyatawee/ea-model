//+------------------------------------------------------------------+
//| ImpulseBasketEA_v2.1.mq5  --  PRICE-STEP GRID EXPERIMENT           |
//|                                                                   |
//| v2.1 = v2.0 + a second entry mode: instead of waiting for an       |
//| impulse candle to close, open a new position every time PRICE      |
//| moves InpGridStepUSD away from the last entry ("เปิดไม้ตามราคา").   |
//| Everything else (one-sided group, +$target, no SL, no basket stop) |
//| is identical, so the two entry engines can be compared directly.   |
//|                                                                   |
//|   InpEntryMode = 0 : signal (v2.0 behaviour, shipped)              |
//|   InpEntryMode = 1 : price step, add in the direction of the move  |
//|   InpEntryMode = 2 : price step, add against the move (recovery)   |
//|                                                                   |
//| v2.0 = v1.1 with the winning defaults measured in the sweeps      |
//| (research/impulse-basket.md). Attach it and you get the best      |
//| EV/run configuration found, with the brief's own scoring rule.    |
//|                                                                   |
//| Measured (XAUUSDm M5, $1,000, 2023.01-2026.10, Model=2,           |
//| 1,157 rolling 21-trading-day runs):                               |
//|     EV per run = +$198      runs that blew up = 38.5 %            |
//| Tune 2023-2024 +184 / 25.0 % ruin, validate 2025-2026 +211 / 53.7 |
//| Calendar-month framing (46 months): +$314 per run, 18/46 ruined.  |
//|                                                                   |
//| The three switches that produced that number, and why:            |
//|   InpSameSideOnly = true  -- without it the group opens both ways |
//|     as impulses arrive, freezes at 8 positions with net lot 0.00, |
//|     and can never reach the profit target again (measured over    |
//|     267,180 of 267,899 samples). This is the trap of the brief's  |
//|     literal "open both ways, close the group at a small target"   |
//|     design; one-sided groups fix the mechanics.                   |
//|   InpAllowShort = false   -- the measured impulse edge is         |
//|     continuation, and on this sample the continuation that pays   |
//|     is the LONG one (gold 1830 -> 4160 over the sample). The      |
//|     short-only mirror of the identical logic scores -$281/run,    |
//|     so read this build as a leveraged long-gold trend bet with a  |
//|     39 % ruin rate at $1,000, not as a market-neutral edge.       |
//|   InpHTF = 2              -- only buy when price is above the     |
//|     day's open (small EV gain: +194 -> +198, ruin 41 % -> 38.5 %).|
//|                                                                   |
//| No per-trade SL and no basket stop, exactly as the brief demands: |
//| the account is the stop. A survivor variant lives in the same     |
//| file: InpMaxPositions=2 + InpUseTimeExit=true + InpMaxHoldBars=12 |
//| gives EV +$26 per run with a 1.7 % ruin rate (full period) and    |
//| +$179 with 0.0 % ruin on the real-tick Jul-Oct 2026 window.       |
//+------------------------------------------------------------------+
#property strict
#property version "2.00"
#property description "Impulse-candle basket EA (shipped build v2.0)"

#include <Trade/Trade.mqh>

//--- entry geometry -------------------------------------------------
input double InpImpulseRangeATR  = 1.5;
//--- entry engine ---------------------------------------------------
input int    InpEntryMode       = 0;     // 0 = impulse signal | 1 = price step (with move) | 2 = price step (against move)
input double InpGridStepUSD     = 1.00;  // price distance in $/oz that triggers the next entry
input bool   InpGridFillOnBar   = true;  // only fill a new grid level on a new M5 bar (else every tick)
input double InpImpulseBodyRatio = 0.50;
input bool   InpUseClosePos      = true;
input double InpImpulseClosePos  = 0.75;
input int    InpATRPeriod        = 14;
input double InpMinATR           = 0.0;
input int    InpDirMode          = 0;     // 0 continuation | 1 fade
input int    InpHTF              = 2;     // 0 off | 1 H1 EMA50 side | 2 day-open side (shipped)
input int    InpHTFEMA           = 50;

//--- group / basket -------------------------------------------------
input int    InpTPMode           = 0;     // 0 = fixed $, 1 = $ per oz of open exposure
input double InpBasketTP         = 20.0;  // mode 0: dollars
input double InpTPPerOz          = 1.50;  // mode 1: dollars per ounce of exposure
input int    InpMaxPositions     = 8;
input int    InpMaxPosPerDir     = 0;     // 0 = no per-direction cap
input bool   InpAllowLong        = true;  // shipped
input bool   InpAllowShort       = false; // shipped: the measured edge is the long continuation
input bool   InpSameSideOnly     = true;  // shipped: stops the frozen hedged group
input double InpNetCapLots       = 0.0;
input double InpAddMinGroupPL    = -1e9;  // add only while group P/L >= this
input bool   InpUseTimeExit      = false;
input int    InpMaxHoldBars      = 0;
input bool   InpCloseBeforeWeekend = false;
input bool   InpUseGroupTrail    = false; // give-back band after a profit peak
input double InpTrailArmPL       = 40.0;
input double InpTrailGiveback    = 20.0;
input int    InpFlatHour         = -1;    // >=0: close the group at this server hour
input int    InpBlockHourFrom    = -1;    // >=0: do not open new trades in [from,to)
input int    InpBlockHourTo      = -1;

//--- frequency ------------------------------------------------------
input int    InpCooldownBars     = 0;
input int    InpCooldownAfterClose = 0;
input int    InpMaxEntriesPerDay = 0;

//--- sizing ---------------------------------------------------------
input double InpLot              = 0.02;
input int    InpLotMode          = 0;
input double InpLotStep          = 0.01;
input double InpLotRecoveryMult  = 1.0;
input double InpMaxLot           = 0.10;

//--- accounting / logging -------------------------------------------
input long   InpMagic            = 20261014;
input bool   InpLogEquity        = true;
input bool   InpLogCycles        = true;
input string InpLogFile          = "ibe_equity.csv";
input string InpCycleFile        = "ibe_cycles.csv";
input string InpLogEvery         = "M5";   // M5 = one sample per bar, M1 = per minute

CTrade trade;
int    hATR = INVALID_HANDLE, hEMA = INVALID_HANDLE;
string g_sym;
int    g_digits;
double g_point, g_contract;
int    g_lastBarTime = 0;
int    g_cooldownLeft = 0;
int    g_dayStamp = -1;
int    g_dayEntries = 0;
int    g_groupOpenBar = 0;
int    g_fh = INVALID_HANDLE, g_cfh = INVALID_HANDLE;
double g_peakPL = 0.0;
double g_gridAnchor = 0.0;      // last price at which a grid level was filled
int    g_lastGridBar = 0;       // bar on which the last grid level was filled
double g_spreadSum = 0.0, g_spreadMin = 1e9, g_spreadMax = 0.0;
long   g_spreadN = 0;

int OnInit()
{
   g_sym      = _Symbol;
   g_digits   = (int)SymbolInfoInteger(g_sym, SYMBOL_DIGITS);
   g_point    = SymbolInfoDouble(g_sym, SYMBOL_POINT);
   g_contract = SymbolInfoDouble(g_sym, SYMBOL_TRADE_CONTRACT_SIZE);

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetTypeFillingBySymbol(g_sym);
   trade.SetDeviationInPoints(30);

   hATR = iATR(g_sym, PERIOD_M5, InpATRPeriod);
   if(InpHTF == 1) hEMA = iMA(g_sym, PERIOD_H1, InpHTFEMA, 0, MODE_EMA, PRICE_CLOSE);
   if(hATR == INVALID_HANDLE || (InpHTF == 1 && hEMA == INVALID_HANDLE))
   {
      Print("IBE: indicator init failed");
      return(INIT_FAILED);
   }

   if(InpLogEquity)
      g_fh = FileOpen(InpLogFile, FILE_WRITE | FILE_TXT | FILE_ANSI);
   if(g_fh != INVALID_HANDLE)
      FileWriteString(g_fh, "time,balance,equity,margin_free,positions,netlot,groupPL\n");
   if(InpLogCycles)
      g_cfh = FileOpen(InpCycleFile, FILE_WRITE | FILE_TXT | FILE_ANSI);
   if(g_cfh != INVALID_HANDLE)
      FileWriteString(g_cfh, "time,event,reason,dir,lot,atr,n,netlot,pl,age_bars\n");

   int mode = (int)AccountInfoInteger(ACCOUNT_MARGIN_MODE);
   PrintFormat("IBE init v1.1: sym=%s deposit=%.2f lev=%d margin_mode=%d spread_points=%d contract=%.1f swapL=%.3f swapS=%.3f",
               g_sym, AccountInfoDouble(ACCOUNT_BALANCE),
               (int)AccountInfoInteger(ACCOUNT_LEVERAGE), mode,
               (int)SymbolInfoInteger(g_sym, SYMBOL_SPREAD), g_contract,
               SymbolInfoDouble(g_sym, SYMBOL_SWAP_LONG),
               SymbolInfoDouble(g_sym, SYMBOL_SWAP_SHORT));
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   // Cost decomposition: realised gross P/L vs swap vs commission. This is the
   // only way to see whether a configuration is losing to the entry spread or
   // to the overnight carry.
   if(HistorySelect(0, TimeCurrent() + 86400))
   {
      int deals = HistoryDealsTotal();
      double dprofit = 0.0, dswap = 0.0, dcomm = 0.0;
      int n = 0;
      for(int i = 0; i < deals; i++)
      {
         ulong ticket = HistoryDealGetTicket(i);
         if(ticket == 0) continue;
         if((long)HistoryDealGetInteger(ticket, DEAL_MAGIC) != InpMagic) continue;
         dprofit += HistoryDealGetDouble(ticket, DEAL_PROFIT);
         dswap   += HistoryDealGetDouble(ticket, DEAL_SWAP);
         dcomm   += HistoryDealGetDouble(ticket, DEAL_COMMISSION);
         n++;
      }
      PrintFormat("IBE SUMMARY deals=%d profit=%.2f swap=%.2f commission=%.2f net=%.2f final=%.2f",
                  n, dprofit, dswap, dcomm, dprofit + dswap + dcomm,
                  AccountInfoDouble(ACCOUNT_BALANCE));
      if(g_spreadN > 0)
         PrintFormat("IBE SPREAD n=%d mean=%.4f min=%.4f max=%.4f (price units)",
                     (int)g_spreadN, g_spreadSum / g_spreadN, g_spreadMin, g_spreadMax);
      if(g_cfh != INVALID_HANDLE)
         FileWriteString(g_cfh, StringFormat("%s,SUMMARY,,0,%.2f,0.0,%d,0.0,%.2f,0\n",
                                             TimeToString(TimeCurrent(), TIME_DATE | TIME_MINUTES),
                                             dprofit + dswap + dcomm, n));
   }
   if(hATR != INVALID_HANDLE) IndicatorRelease(hATR);
   if(hEMA != INVALID_HANDLE) IndicatorRelease(hEMA);
   if(g_fh != INVALID_HANDLE) FileClose(g_fh);
   if(g_cfh != INVALID_HANDLE) FileClose(g_cfh);
}

double GroupState(int &count, double &netlot, double &oz)
{
   double pl = 0.0;
   count = 0; netlot = 0.0; oz = 0.0;
   int total = PositionsTotal();
   for(int i = 0; i < total; i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != g_sym) continue;
      if((long)PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      double lots = PositionGetDouble(POSITION_VOLUME);
      long   type = PositionGetInteger(POSITION_TYPE);
      pl     += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
      netlot += (type == POSITION_TYPE_BUY ? lots : -lots);
      oz     += lots * g_contract;
      count++;
   }
   return pl;
}

void LogCycle(string ev, string reason, int dir, double lot, double atr,
              int n, double netlot, double pl, int ageBars)
{
   if(g_cfh == INVALID_HANDLE) return;
   FileWriteString(g_cfh, StringFormat("%s,%s,%s,%d,%.2f,%.3f,%d,%.2f,%.2f,%d\n",
                                       TimeToString(TimeCurrent(), TIME_DATE | TIME_MINUTES),
                                       ev, reason, dir, lot, atr, n, netlot, pl, ageBars));
}

void CloseAll(string why, int barTime)
{
   int count = 0; double net = 0.0, oz = 0.0;
   double pl = GroupState(count, net, oz);
   if(count == 0) return;
   int age = (g_groupOpenBar > 0 ? (int)((barTime - g_groupOpenBar) / 300) : 0);
   int total = PositionsTotal();
   for(int i = total - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != g_sym) continue;
      if((long)PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      if(!trade.PositionClose(ticket))
         PrintFormat("IBE: close %I64u failed ret=%d %s", ticket, trade.ResultRetcode(),
                     trade.ResultRetcodeDescription());
   }
   LogCycle("CLOSE", why, 0, 0.0, 0.0, count, net, pl, age);
   g_groupOpenBar = 0;
   g_peakPL = 0.0;
   if(InpCooldownAfterClose > 0) g_cooldownLeft = InpCooldownAfterClose;
}

double NormLot(double lot)
{
   double minLot  = SymbolInfoDouble(g_sym, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(g_sym, SYMBOL_VOLUME_MAX);
   double stepLot = SymbolInfoDouble(g_sym, SYMBOL_VOLUME_STEP);
   if(stepLot <= 0) stepLot = 0.01;
   lot = MathRound(lot / stepLot) * stepLot;
   if(lot < minLot) lot = minLot;
   if(lot > maxLot) lot = maxLot;
   if(lot > InpMaxLot) lot = InpMaxLot;
   return NormalizeDouble(lot, 2);
}

void LogEquity()
{
   if(g_fh == INVALID_HANDLE) return;
   int count = 0; double net = 0.0, oz = 0.0;
   double pl = GroupState(count, net, oz);
   FileWriteString(g_fh, StringFormat("%s,%.2f,%.2f,%.2f,%d,%.2f,%.2f\n",
                                      TimeToString(TimeCurrent(), TIME_DATE | TIME_MINUTES),
                                      AccountInfoDouble(ACCOUNT_BALANCE),
                                      AccountInfoDouble(ACCOUNT_EQUITY),
                                      AccountInfoDouble(ACCOUNT_MARGIN_FREE),
                                      count, net, pl));
}

void OpenTrade(int dir, double lot, double atr, int n, double net, double pl)
{
   bool ok = (dir > 0 ? trade.Buy(lot, g_sym, 0.0, 0.0, 0.0, "IBE")
                      : trade.Sell(lot, g_sym, 0.0, 0.0, 0.0, "IBE"));
   if(!ok)
      PrintFormat("IBE: order failed dir=%d lot=%.2f ret=%d %s", dir, lot,
                  trade.ResultRetcode(), trade.ResultRetcodeDescription());
   else
      LogCycle("OPEN", "imp", dir, lot, atr, n, net, pl, 0);
}

void OnTick()
{
   int barTime = (int)iTime(g_sym, PERIOD_M5, 0);
   static int loggedBar = 0, loggedMin = 0;

   // Equity sampling comes first: the entry block below returns early on
   // most bars and would otherwise skip the log.
   bool perMinute = (InpLogEvery == "M1");
   int stamp = (perMinute ? (int)(TimeCurrent() / 60) * 60 : barTime);
   int lastStamp = (perMinute ? loggedMin : loggedBar);
   if(stamp != lastStamp)
   {
      if(perMinute) loggedMin = stamp; else loggedBar = stamp;
      LogEquity();
      MqlTick tk;
      if(SymbolInfoTick(g_sym, tk) && tk.ask > tk.bid)
      {
         double sp = tk.ask - tk.bid;
         g_spreadSum += sp;
         g_spreadN++;
         if(sp < g_spreadMin) g_spreadMin = sp;
         if(sp > g_spreadMax) g_spreadMax = sp;
      }
   }

   // ---------------- price-step entry engine (InpEntryMode 1 / 2) --------
   // "เปิดไม้ตามราคา": a new position every InpGridStepUSD of price travel,
   // with no reference to candles. Mode 1 adds in the direction of the move,
   // mode 2 adds against it (the classic recovery grid).
   if(InpEntryMode != 0)
   {
      bool fill = (!InpGridFillOnBar || barTime != g_lastGridBar);
      if(fill)
      {
         int pcount = 0; double pnet = 0.0, poz = 0.0;
         double ppl = GroupState(pcount, pnet, poz);
         double ask = SymbolInfoDouble(g_sym, SYMBOL_ASK);
         double bid = SymbolInfoDouble(g_sym, SYMBOL_BID);
         int pdir = 0;

         if(pcount == 0)
         {
            double po = iOpen(g_sym, PERIOD_M5, 1), pc = iClose(g_sym, PERIOD_M5, 1);
            pdir = (pc >= po ? 1 : -1);          // seed with the last closed bar's direction
            g_gridAnchor = 0.0;
         }
         else if(g_gridAnchor > 0.0)
         {
            if(bid - g_gridAnchor >= InpGridStepUSD)      pdir = (InpEntryMode == 1 ?  1 : -1);
            else if(g_gridAnchor - bid >= InpGridStepUSD) pdir = (InpEntryMode == 1 ? -1 :  1);
         }

         if(pdir != 0 && (pdir > 0 ? InpAllowLong : InpAllowShort) && pcount < InpMaxPositions)
         {
            bool sameSideOK = true;
            if(InpSameSideOnly && pcount > 0 &&
               ((pnet > 0 && pdir < 0) || (pnet < 0 && pdir > 0))) sameSideOK = false;
            if(sameSideOK)
            {
               double lot = NormLot(InpLot);
               double entryPx = (pdir > 0 ? ask : bid);
               int wasFlat = (pcount == 0);
               OpenTrade(pdir, lot, 0.0, pcount, pnet, ppl);
               g_gridAnchor = entryPx;
               g_dayEntries++;
               if(wasFlat) { g_groupOpenBar = barTime; g_peakPL = 0.0; }
            }
         }
         g_lastGridBar = barTime;
      }
   }

   if(barTime != g_lastBarTime)
   {
      g_lastBarTime = barTime;
      if(g_cooldownLeft > 0) g_cooldownLeft--;

      int count = 0; double net = 0.0, oz = 0.0;
      double pl = GroupState(count, net, oz);
      if(count > 0 && pl > g_peakPL) g_peakPL = pl;

      // ---------------- exits -------------------------------------
      double target = (InpTPMode == 1 ? InpTPPerOz * oz : InpBasketTP);
      if(count > 0)
      {
         if(target > 0 && pl >= target)
            CloseAll("target", barTime);
         else if(InpUseGroupTrail && g_peakPL >= InpTrailArmPL &&
                 pl <= g_peakPL - InpTrailGiveback)
            CloseAll("trail", barTime);
         else if(InpUseTimeExit && InpMaxHoldBars > 0 && g_groupOpenBar > 0 &&
                 (int)((barTime - g_groupOpenBar) / 300) >= InpMaxHoldBars)
            CloseAll("time", barTime);
         else if(InpCloseBeforeWeekend)
         {
            MqlDateTime dt; TimeToStruct((datetime)barTime, dt);
            if(dt.day_of_week == 5 && dt.hour >= 20) CloseAll("weekend", barTime);
         }
         else if(InpFlatHour >= 0)
         {
            MqlDateTime dt2; TimeToStruct((datetime)barTime, dt2);
            if(dt2.hour == InpFlatHour) CloseAll("flathour", barTime);
         }
      }
      if(count > 0 && PositionsTotal() == 0) { g_groupOpenBar = 0; g_peakPL = 0.0; }

      // ---------------- entries -----------------------------------
      MqlDateTime dnow; TimeToStruct((datetime)barTime, dnow);
      int stamp = dnow.year * 10000 + dnow.mon * 100 + dnow.day;
      if(stamp != g_dayStamp) { g_dayStamp = stamp; g_dayEntries = 0; }

      double atr[];
      if(CopyBuffer(hATR, 0, 1, 2, atr) != 2) return;
      double a = atr[0];
      double o = iOpen(g_sym, PERIOD_M5, 1);
      double h = iHigh(g_sym, PERIOD_M5, 1);
      double l = iLow(g_sym, PERIOD_M5, 1);
      double c = iClose(g_sym, PERIOD_M5, 1);
      double rng = h - l;
      double body = MathAbs(c - o);
      bool canTrade = (a >= InpMinATR && rng > 0 && a > 0);
      if(canTrade && rng < InpImpulseRangeATR * a) canTrade = false;
      if(canTrade && body < InpImpulseBodyRatio * rng) canTrade = false;
      double closePos = (rng > 0 ? (c - l) / rng : 0.5);
      int impDir = (c >= o ? 1 : -1);
      if(canTrade && InpUseClosePos)
      {
         if(impDir > 0 && closePos < InpImpulseClosePos) canTrade = false;
         if(impDir < 0 && closePos > 1.0 - InpImpulseClosePos) canTrade = false;
      }
      if(canTrade && g_cooldownLeft > 0) canTrade = false;
      if(canTrade && InpMaxEntriesPerDay > 0 && g_dayEntries >= InpMaxEntriesPerDay)
         canTrade = false;
      if(canTrade && InpBlockHourFrom >= 0 && InpBlockHourTo >= 0 &&
         dnow.hour >= InpBlockHourFrom && dnow.hour < InpBlockHourTo) canTrade = false;
      if(!canTrade) return;

      int dir = (InpDirMode == 0 ? impDir : -impDir);
      if(dir > 0 && !InpAllowLong)  return;
      if(dir < 0 && !InpAllowShort) return;

      // higher-timeframe alignment ---------------------------------
      if(InpHTF == 1)
      {
         double ema[];
         if(CopyBuffer(hEMA, 0, 1, 2, ema) != 2) return;
         if(dir > 0 && c <= ema[0]) return;
         if(dir < 0 && c >= ema[0]) return;
      }
      else if(InpHTF == 2)
      {
         double dOpen = iOpen(g_sym, PERIOD_D1, 0);
         if(dir > 0 && c <= dOpen) return;
         if(dir < 0 && c >= dOpen) return;
      }

      GroupState(count, net, oz);
      if(count >= InpMaxPositions) return;
      if(InpMaxPosPerDir > 0)
      {
         int same = 0;
         for(int i = 0; i < PositionsTotal(); i++)
         {
            ulong tk = PositionGetTicket(i);
            if(tk == 0) continue;
            if(PositionGetString(POSITION_SYMBOL) != g_sym) continue;
            if((long)PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
            long tp = PositionGetInteger(POSITION_TYPE);
            if((dir > 0 && tp == POSITION_TYPE_BUY) || (dir < 0 && tp == POSITION_TYPE_SELL)) same++;
         }
         if(same >= InpMaxPosPerDir) return;
      }
      if(InpSameSideOnly && count > 0)
      {
         if((net > 0 && dir < 0) || (net < 0 && dir > 0)) return;
      }
      if(pl < InpAddMinGroupPL) return;

      double lot = InpLot;
      if(InpLotMode == 1)      lot = InpLot * a;
      else if(InpLotMode == 2) lot = InpLot + InpLotStep * count;
      else if(InpLotMode == 3) lot = InpLot * (1.0 + InpLotRecoveryMult * MathMax(0.0, -pl) / 20.0);
      lot = NormLot(lot);

      if(InpNetCapLots > 0 && MathAbs(net + dir * lot) > InpNetCapLots) return;

      int wasFlat = (count == 0);
      OpenTrade(dir, lot, a, count, net, pl);
      g_dayEntries++;
      g_cooldownLeft = InpCooldownBars;
      if(wasFlat) { g_groupOpenBar = barTime; g_peakPL = 0.0; }
   }

}
//+------------------------------------------------------------------+
