//+------------------------------------------------------------------+
//| PhoenixPump.mq5 - grid + lot pumping (double-or-die style)        |
//|                                                                  |
//| Target use: $100 of capital per day, stop the day at +100%       |
//| (i.e. turn 100 into 200), no daily SL by default - the account    |
//| itself is the stop loss. Grid adds on adverse moves with lot      |
//| progression; the whole basket closes on a money target.           |
//|                                                                  |
//| Hard limits kept honest for a $100 account at 1:2000:             |
//|   InpMaxTotalLots  - margin guard (0.45 lot ~= $93 margin)        |
//|   InpMaxMarginUsePct - never commit more than this % of equity    |
//|                                                                  |
//| Not a signal EA: entry is interval-based so the grid/lot          |
//| mechanics can be measured without a directional edge.             |
//+------------------------------------------------------------------+
#property copyright "PhoenixPump"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>

//--- core
input group "Core"
input int    InpMagic           = 20261006; // Magic number
input double InpDailyTargetPct  = 100.0;    // Stop day at this % gain (0=off)
input double InpDailySLPct      = 0.0;      // Stop day at this % loss (0=off -> account is the SL)
input int    InpResetHourServer = 0;        // Server hour that starts a new trading day
input bool   InpLogDaily        = true;     // Print one DAY line per day

//--- entry
input group "Entry"
input int    InpEntryIntervalSec = 0;       // Min seconds between basket entries (0=immediate)
input int    InpDirectionMode    = 2;       // 0=long 1=short 2=alternate 3=random
input bool   InpUseSessionFilter = false;   // Restrict entries to a session window
input int    InpSessionStartUTC  = 7;
input int    InpSessionEndUTC    = 21;
input double InpMaxSpreadPrice   = 0.0;     // Max spread in price units (0=off)
input int    InpMaxEntriesPerDay = 0;       // 0 = unlimited

//--- grid
input group "Grid"
input int    InpStepMode         = 0;       // 0=fixed $  1=ATR multiple
input double InpStepValue        = 2.0;     // $ distance or ATR multiple
input int    InpATRPeriod        = 14;
input int    InpMaxLevels        = 4;       // Max positions per basket

//--- lot progression
input group "Lot"
input double InpBaseLot          = 0.05;    // First position in a basket
input int    InpLotMode          = 1;       // 0=flat 1=multiply 2=add
input double InpLotMult          = 1.6;
input double InpLotAdd           = 0.02;
input double InpMaxTotalLots     = 0.45;    // Margin guard (total basket volume)
input double InpMaxMarginUsePct  = 60.0;    // Max % of equity allowed as margin

//--- exit
input group "Exit"
input double InpBasketTP         = 2.0;     // Close whole basket at this floating profit ($)
input double InpBasketTPPct      = 0.0;     // Or at this % of equity (overrides $ when >0)
input double InpBasketSL         = 0.0;     // Close whole basket at this floating LOSS ($, 0=off)
input bool   InpStopDayAfterSL   = false;   // After a basket SL, stop trading for the day

//--- globals
CTrade   trade;
int      g_atrHandle    = INVALID_HANDLE;
datetime g_dayStamp     = 0;
double   g_dayStartBal  = 0.0;
bool     g_dayDone      = false;
int      g_entriesToday = 0;
int      g_lastSide     = 1;   // 1=buy -1=sell  (for alternate mode)
datetime g_lastEntryTime= 0;

//+------------------------------------------------------------------+
int OnInit()
  {
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(20);
   trade.SetTypeFillingBySymbol(_Symbol);

   g_atrHandle = iATR(_Symbol, PERIOD_M5, InpATRPeriod);
   if(g_atrHandle == INVALID_HANDLE)
      Print("WARN: iATR handle failed - ATR step mode will fall back to fixed $");

   g_dayStamp    = 0;
   g_dayStartBal = AccountInfoDouble(ACCOUNT_BALANCE);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   if(g_atrHandle != INVALID_HANDLE)
      IndicatorRelease(g_atrHandle);
  }

//+------------------------------------------------------------------+
double SpreadPrice()
  {
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   return(ask - bid);
  }

//+------------------------------------------------------------------+
double StepDistance()
  {
   if(InpStepMode == 1 && g_atrHandle != INVALID_HANDLE)
     {
      double buf[];
      ArraySetAsSeries(buf, true);
      if(CopyBuffer(g_atrHandle, 0, 0, 1, buf) == 1 && buf[0] > 0.0)
         return(buf[0] * InpStepValue);
     }
   return(InpStepValue);
  }

//+------------------------------------------------------------------+
double NormalizeLot(double lot)
  {
   double minL  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxL  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double stepL = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(stepL <= 0.0)
      stepL = minL;
   lot = MathFloor(lot / stepL) * stepL;
   if(lot < minL) lot = minL;
   if(lot > maxL) lot = maxL;
   return(NormalizeDouble(lot, 2));
  }

//+------------------------------------------------------------------+
double LotForLevel(int level)
  {
   double lot = InpBaseLot;
   if(InpLotMode == 1)
      lot = InpBaseLot * MathPow(InpLotMult, level);
   else if(InpLotMode == 2)
      lot = InpBaseLot + InpLotAdd * level;
   return(NormalizeLot(lot));
  }

//+------------------------------------------------------------------+
//| Basket helpers                                                    |
//+------------------------------------------------------------------+
int BasketCount()
  {
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if((int)PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      n++;
     }
   return(n);
  }

double BasketProfit()
  {
   double pl = 0.0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if((int)PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      pl += PositionGetDouble(POSITION_PROFIT)
          + PositionGetDouble(POSITION_SWAP);
     }
   return(pl);
  }

double BasketLots()
  {
   double v = 0.0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if((int)PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      v += PositionGetDouble(POSITION_VOLUME);
     }
   return(v);
  }

//--- last opened position of the basket: price + side
bool BasketLast(double &lastPrice, int &side)
  {
   datetime newest = 0;
   bool found = false;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if((int)PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      datetime tm = (datetime)PositionGetInteger(POSITION_TIME);
      if(tm >= newest)
        {
         newest    = tm;
         lastPrice = PositionGetDouble(POSITION_PRICE_OPEN);
         side      = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
         found     = true;
        }
     }
   return(found);
  }

//+------------------------------------------------------------------+
void CloseBasket()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if((int)PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      trade.PositionClose(t);
     }
  }

//+------------------------------------------------------------------+
bool SessionOk()
  {
   if(!InpUseSessionFilter)
      return(true);
   MqlDateTime tm;
   TimeToStruct(TimeCurrent(), tm);
   if(InpSessionStartUTC <= InpSessionEndUTC)
      return(tm.hour >= InpSessionStartUTC && tm.hour < InpSessionEndUTC);
   return(tm.hour >= InpSessionStartUTC || tm.hour < InpSessionEndUTC);
  }

//+------------------------------------------------------------------+
int NextSide()
  {
   if(InpDirectionMode == 0) return(1);
   if(InpDirectionMode == 1) return(-1);
   if(InpDirectionMode == 3) return((MathRand() % 2 == 0) ? 1 : -1);
   g_lastSide = -g_lastSide;
   return(g_lastSide);
  }

//+------------------------------------------------------------------+
bool MarginOk(double addLot, double price, int side)
  {
   double total = BasketLots() + addLot;
   if(total > InpMaxTotalLots)
      return(false);

   double margin = 0.0;
   if(!OrderCalcMargin(side > 0 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL,
                       _Symbol, addLot, price, margin))
      return(false);

   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double used   = AccountInfoDouble(ACCOUNT_MARGIN);
   if(equity <= 0.0)
      return(false);
   if((used + margin) / equity * 100.0 > InpMaxMarginUsePct)
      return(false);
   return(true);
  }

//+------------------------------------------------------------------+
bool OpenLeg(int side, double lot, string comment)
  {
   double price = (side > 0) ? SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                             : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(!MarginOk(lot, price, side))
      return(false);

   bool ok = (side > 0) ? trade.Buy(lot, _Symbol, 0.0, 0.0, 0.0, comment)
                        : trade.Sell(lot, _Symbol, 0.0, 0.0, 0.0, comment);
   if(ok)
     {
      g_lastEntryTime = TimeCurrent();
      g_entriesToday++;
     }
   return(ok);
  }

//+------------------------------------------------------------------+
//| New-day bookkeeping                                              |
//+------------------------------------------------------------------+
void CheckNewDay()
  {
   MqlDateTime tm;
   TimeToStruct(TimeCurrent(), tm);
   tm.hour = InpResetHourServer; tm.min = 0; tm.sec = 0;
   datetime boundary = StructToTime(tm);

   if(g_dayStamp == 0)
     {
      // first tick: compute the boundary of the current trading day
      datetime now = TimeCurrent();
      if(now < boundary)
         boundary -= 86400;
     }

   if(g_dayStamp != boundary)
     {
      if(g_dayStamp != 0 && InpLogDaily)
        {
         double eq  = AccountInfoDouble(ACCOUNT_EQUITY);
         double pnl = eq - g_dayStartBal;
         Print("DAY ", TimeToString(boundary, TIME_DATE), " pnl=", DoubleToString(pnl, 2),
               " eq=", DoubleToString(eq, 2), " entries=", IntegerToString(g_entriesToday),
               (g_dayDone ? " stopped" : ""));
        }
      g_dayStamp     = boundary;
      g_dayStartBal  = AccountInfoDouble(ACCOUNT_EQUITY);
      g_dayDone      = false;
      g_entriesToday = 0;
     }
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   CheckNewDay();

   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   if(eq <= 0.0)
      return;

   //--- daily target / optional daily stop
   if(!g_dayDone && g_dayStartBal > 0.0)
     {
      if(InpDailyTargetPct > 0.0 && eq >= g_dayStartBal * (1.0 + InpDailyTargetPct / 100.0))
        {
         CloseBasket();
         g_dayDone = true;
         Print("DAY TARGET HIT at ", DoubleToString(eq, 2));
        }
      else if(InpDailySLPct > 0.0 && eq <= g_dayStartBal * (1.0 - InpDailySLPct / 100.0))
        {
         CloseBasket();
         g_dayDone = true;
         Print("DAY STOP HIT at ", DoubleToString(eq, 2));
        }
     }

   if(g_dayDone)
      return;

   //--- basket management
   int n = BasketCount();
   if(n > 0)
     {
      double fl = BasketProfit();
      double target = InpBasketTP;
      if(InpBasketTPPct > 0.0)
         target = eq * InpBasketTPPct / 100.0;

      if(fl >= target)
        {
         CloseBasket();
         return;
        }

      //--- basket stop loss: the thing that keeps a martingale grid alive
      if(InpBasketSL > 0.0 && fl <= -InpBasketSL)
        {
         CloseBasket();
         if(InpStopDayAfterSL)
            g_dayDone = true;
         Print("BASKET SL hit, loss=", DoubleToString(fl, 2));
         return;
        }

      //--- grid add
      if(n < InpMaxLevels)
        {
         double lastPrice; int side;
         if(BasketLast(lastPrice, side))
           {
            double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            double adverse = (side > 0) ? (lastPrice - bid) : (ask - lastPrice);
            if(adverse >= StepDistance())
              {
               double lot = LotForLevel(n);
               double px  = (side > 0) ? ask : bid;
               if(MarginOk(lot, px, side))
                  OpenLeg(side, lot, "P-ADD" + IntegerToString(n + 1));
              }
           }
        }
      return;
     }

   //--- flat -> new basket
   if(InpMaxEntriesPerDay > 0 && g_entriesToday >= InpMaxEntriesPerDay)
      return;
   if(!SessionOk())
      return;
   if(InpMaxSpreadPrice > 0.0 && SpreadPrice() > InpMaxSpreadPrice)
      return;
   if(InpEntryIntervalSec > 0 && TimeCurrent() - g_lastEntryTime < InpEntryIntervalSec)
      return;

   int side = NextSide();
   double lot = LotForLevel(0);
   OpenLeg(side, lot, "P-IN");
  }
//+------------------------------------------------------------------+
