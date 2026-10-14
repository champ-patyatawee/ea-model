//+------------------------------------------------------------------+
//| ImpulseBasketEA_v1.0.mq5                                          |
//|                                                                   |
//| Brief: XAUUSDm M5, $1,000 deposit, no per-trade SL and no basket  |
//| stop -- the account is the stop. Open frequently in BOTH          |
//| directions on impulse candles, and close the WHOLE GROUP when its |
//| combined floating P/L reaches a small profit target.              |
//|                                                                   |
//| The entry rule is NOT a guess: tools/edge_probe.py measured it on |
//| 267,759 M5 bars (2023.01-2026.10). Findings that shaped v1.0:     |
//|   * FADING an impulse is wrong: the fade drift is negative at    |
//|     every horizon. CONTINUATION is the statistically positive    |
//|     side (range>=1.5xATR & body>=0.5: +0.029R at h=2, t=+3.0).   |
//|   * Best family by dollars: range>=1.5xATR & body>=0.5 & the     |
//|     close in the top/bottom 15% of the bar ("thrust bar") --     |
//|     +0.266 $/oz at h=16 against a ~0.24 $/oz round-trip spread.  |
//|   * So one impulse trade does NOT pay for its own spread. The    |
//|     group exit has to earn the difference; that is what this EA  |
//|     is built to measure, not to assume.                          |
//+------------------------------------------------------------------+
#property strict
#property version "1.00"
#property description "Impulse-candle basket EA (research build v1.0)"

#include <Trade/Trade.mqh>

//--- entry geometry -------------------------------------------------
input double InpImpulseRangeATR  = 1.5;   // impulse bar range >= k * ATR(14) M5
input double InpImpulseBodyRatio = 0.50;  // |close-open| >= b * range
input bool   InpUseClosePos      = true;  // require the close near the bar extreme
input double InpImpulseClosePos  = 0.75;  // >= this (long) or <= 1-this (short)
input int    InpATRPeriod        = 14;
input double InpMinATR           = 0.0;   // skip entries while ATR($/oz) < this
input int    InpDirMode          = 0;     // 0 = CONTINUATION (measured edge), 1 = FADE

//--- group / basket -------------------------------------------------
input double InpBasketTP         = 20.0;  // close the whole group at +$ this
input int    InpMaxPositions     = 8;     // max concurrent positions in the group
input bool   InpSameSideOnly     = false; // only add on the side of the open group
input double InpNetCapLots       = 0.0;   // 0 = off; skip a trade that pushes |net| above this
input bool   InpUseTimeExit      = false; // close the group after InpMaxHoldBars
input int    InpMaxHoldBars      = 0;
input bool   InpCloseBeforeWeekend = false;

//--- frequency ------------------------------------------------------
input int    InpCooldownBars     = 0;     // bars to wait after any entry
input int    InpMaxEntriesPerDay = 0;     // 0 = unlimited

//--- sizing ---------------------------------------------------------
input double InpLot              = 0.02;  // base lot
input int    InpLotMode          = 0;     // 0 fixed | 1 vol-scaled | 2 step-up | 3 loss-recovery
input double InpLotStep          = 0.01;  // mode 2: extra lot per already-open position
input double InpLotRecoveryMult  = 1.0;   // mode 3: lot = base * (1 + k*groupLoss/baseLotDollarRisk)
input double InpMaxLot           = 0.10;

//--- accounting / logging -------------------------------------------
input long   InpMagic            = 20261014;
input bool   InpLogEquity        = true;
input string InpLogFile          = "ibe_equity.csv";

CTrade trade;
int    hATR = INVALID_HANDLE;
string g_sym;
int    g_digits;
double g_point;
double g_contract;
int    g_lastBarTime = 0;
int    g_cooldownLeft = 0;
int    g_dayStamp = -1;
int    g_dayEntries = 0;
long   g_groupOpenBar = 0;      // bar time when the group became non-empty
int    g_fh = INVALID_HANDLE;

//+------------------------------------------------------------------+
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
   if(hATR == INVALID_HANDLE)
   {
      Print("IBE: iATR failed");
      return(INIT_FAILED);
   }

   if(InpLogEquity)
   {
      g_fh = FileOpen(InpLogFile, FILE_WRITE | FILE_TXT | FILE_ANSI);
      if(g_fh != INVALID_HANDLE)
         FileWriteString(g_fh, "time,balance,equity,margin_free,positions,netlot,groupPL\n");
      else
         PrintFormat("IBE: equity log open failed err=%d", GetLastError());
   }

   int mode = (int)AccountInfoInteger(ACCOUNT_MARGIN_MODE);
   PrintFormat("IBE init: sym=%s deposit=%.2f lev=%d margin_mode=%d(%s) spread_points=%d contract=%.1f tick=%.3f swapL=%.3f swapS=%.3f",
               g_sym, AccountInfoDouble(ACCOUNT_BALANCE),
               (int)AccountInfoInteger(ACCOUNT_LEVERAGE), mode,
               (mode == ACCOUNT_MARGIN_MODE_RETAIL_HEDGING ? "hedging" : "netting"),
               (int)SymbolInfoInteger(g_sym, SYMBOL_SPREAD), g_contract,
               SymbolInfoDouble(g_sym, SYMBOL_TRADE_TICK_SIZE),
               SymbolInfoDouble(g_sym, SYMBOL_SWAP_LONG),
               SymbolInfoDouble(g_sym, SYMBOL_SWAP_SHORT));
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(hATR != INVALID_HANDLE) IndicatorRelease(hATR);
   if(g_fh != INVALID_HANDLE) FileClose(g_fh);
}

//+------------------------------------------------------------------+
double GroupPL(int &count, double &netlot)
{
   double pl = 0.0;
   count = 0;
   netlot = 0.0;
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
      count++;
   }
   return pl;
}

//+------------------------------------------------------------------+
void CloseAll(string why)
{
   int count = 0; double net = 0.0;
   double pl = GroupPL(count, net);
   if(count == 0) return;
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
   PrintFormat("IBE BASKET CLOSE %s n=%d pl=%.2f net=%.2f", why, count, pl, net);
   g_groupOpenBar = 0;
}

//+------------------------------------------------------------------+
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

//+------------------------------------------------------------------+
void LogEquity()
{
   if(g_fh == INVALID_HANDLE) return;
   int count = 0; double net = 0.0;
   double pl = GroupPL(count, net);
   FileWriteString(g_fh, StringFormat("%s,%.2f,%.2f,%.2f,%d,%.2f,%.2f\n",
                                      TimeToString(TimeCurrent(), TIME_DATE | TIME_MINUTES),
                                      AccountInfoDouble(ACCOUNT_BALANCE),
                                      AccountInfoDouble(ACCOUNT_EQUITY),
                                      AccountInfoDouble(ACCOUNT_MARGIN_FREE),
                                      count, net, pl));
}

//+------------------------------------------------------------------+
void OpenTrade(int dir, double lot)
{
   trade.SetExpertMagicNumber(InpMagic);
   double ask = SymbolInfoDouble(g_sym, SYMBOL_ASK);
   double bid = SymbolInfoDouble(g_sym, SYMBOL_BID);
   bool ok = false;
   if(dir > 0) ok = trade.Buy(lot, g_sym, 0.0, 0.0, 0.0, "IBE");
   else        ok = trade.Sell(lot, g_sym, 0.0, 0.0, 0.0, "IBE");
   if(!ok)
      PrintFormat("IBE: order failed dir=%d lot=%.2f ret=%d %s (ask=%.3f bid=%.3f)",
                  dir, lot, trade.ResultRetcode(), trade.ResultRetcodeDescription(), ask, bid);
}

//+------------------------------------------------------------------+
void OnTick()
{
   // ---------------- per-bar logic -------------------------------
   int barTime = (int)iTime(g_sym, PERIOD_M5, 0);
   bool newBar = (barTime != g_lastBarTime);

   static int loggedBar = 0;
   if(newBar)
   {
      g_lastBarTime = barTime;
      if(g_cooldownLeft > 0) g_cooldownLeft--;

      int count = 0; double net = 0.0;
      double pl = GroupPL(count, net);

      // ---- exits -------------------------------------------------
      if(count > 0)
      {
         if(InpBasketTP > 0 && pl >= InpBasketTP)
            CloseAll("target");
         else if(InpUseTimeExit && InpMaxHoldBars > 0 &&
                 (int)((barTime - g_groupOpenBar) / 300) >= InpMaxHoldBars)
            CloseAll("time");
         else if(InpCloseBeforeWeekend)
         {
            MqlDateTime dt; TimeToStruct((datetime)barTime, dt);
            if(dt.day_of_week == 5 && dt.hour >= 20) CloseAll("weekend");
         }
      }
      if(count == 0) g_groupOpenBar = 0;

      // ---- entries ------------------------------------------------
      MqlDateTime dnow; TimeToStruct((datetime)barTime, dnow);
      int stamp = dnow.year * 10000 + dnow.mon * 100 + dnow.day;
      if(stamp != g_dayStamp)
      {
         g_dayStamp = stamp;
         g_dayEntries = 0;
      }

      double atr[];
      if(CopyBuffer(hATR, 0, 1, 2, atr) == 2)
      {
         double a = atr[0];
         // signal bar = the bar that just closed (shift 1)
         double o = iOpen(g_sym, PERIOD_M5, 1);
         double h = iHigh(g_sym, PERIOD_M5, 1);
         double l = iLow(g_sym, PERIOD_M5, 1);
         double c = iClose(g_sym, PERIOD_M5, 1);
         double rng = h - l;
         double body = MathAbs(c - o);
         bool   canTrade = (a >= InpMinATR && rng > 0 && a > 0);
         if(canTrade && rng < InpImpulseRangeATR * a) canTrade = false;
         if(canTrade && body < InpImpulseBodyRatio * rng) canTrade = false;
         double closePos = (rng > 0 ? (c - l) / rng : 0.5);
         int    impDir = (c >= o ? 1 : -1);
         if(canTrade && InpUseClosePos)
         {
            if(impDir > 0 && closePos < InpImpulseClosePos) canTrade = false;
            if(impDir < 0 && closePos > 1.0 - InpImpulseClosePos) canTrade = false;
         }
         if(canTrade && g_cooldownLeft > 0) canTrade = false;
         if(canTrade && InpMaxEntriesPerDay > 0 && g_dayEntries >= InpMaxEntriesPerDay)
            canTrade = false;

         if(canTrade)
         {
            int dir = (InpDirMode == 0 ? impDir : -impDir);

            // group state -------------------------------------------
            GroupPL(count, net);
            if(count >= InpMaxPositions) canTrade = false;
            if(canTrade && InpSameSideOnly && count > 0)
            {
               if((net > 0 && dir < 0) || (net < 0 && dir > 0)) canTrade = false;
            }

            double lot = InpLot;
            if(InpLotMode == 1)
               lot = InpLot * (a / 1.0);                 // vol-scaled, 1.00 $/oz = 1 base lot
            else if(InpLotMode == 2)
               lot = InpLot + InpLotStep * count;        // step-up ladder
            else if(InpLotMode == 3)
               lot = InpLot * (1.0 + InpLotRecoveryMult * MathMax(0.0, -pl) / 20.0);
            lot = NormLot(lot);

            if(canTrade && InpNetCapLots > 0 && MathAbs(net + dir * lot) > InpNetCapLots)
               canTrade = false;

            if(canTrade)
            {
               OpenTrade(dir, lot);
               g_dayEntries++;
               g_cooldownLeft = InpCooldownBars;
               if(count == 0) g_groupOpenBar = barTime;
               PrintFormat("IBE ENTRY dir=%d lot=%.2f impDir=%d rng/atr=%.2f body=%.2f closePos=%.2f atr=%.3f n=%d net=%.2f pl=%.2f",
                           dir, lot, impDir, rng / a, body / rng, closePos, a, count, net, pl);
            }
         }
      }
   }

   // ---------------- equity log (once per M5 bar) ----------------
   if(barTime != loggedBar)
   {
      loggedBar = barTime;
      LogEquity();
   }
}
//+------------------------------------------------------------------+
