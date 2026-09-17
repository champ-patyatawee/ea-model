//+------------------------------------------------------------------+
//| FiboAdaptiveEA_v4.8.mq5                                            |
//| Daily Sprint $100 -> target +$50-150/day, bust accepted           |
//|                                                                  |
//| v4.8 = v4.7 fade + SNIPER re-entry + RUNNER exits + TARGET LOCK:
//| - RE-ENTRY: same-impulse retest allowed after cooldown bars
//|   (InpAllowReentry/InpReentryCooldownBars); touch cap still limits.
//| - RUNNER EXITS: no hard TP (3R ceiling), chandelier trail 2.0 ATR
//|   from 1.0R, BE at +0.75R, partial 25% at 1R, time exit 180 min.
//| - FIXED $ RISK per trade (InpRiskMoneyUSD, default $10).
//| - DAILY TARGET LOCK (default +$100): stop new entries for the day.
//|   NO daily stop-loss per operator instruction (bust accepted).
//+------------------------------------------------------------------+
#property strict
#property version "4.80"

#include <Trade/Trade.mqh>

CTrade trade;

enum ENUM_TP_MODE
  {
   TP_AT_EXTREME=0,
   TP_AT_MID=1,
   TP_R_MULT=2
  };

enum ENUM_DIRECTION
  {
   DIR_NONE=0,
   DIR_BUY,
   DIR_SELL
  };

enum ENUM_PIVOT_TYPE
  {
   PIVOT_NONE=0,
   PIVOT_HIGH,
   PIVOT_LOW
  };

struct Pivot
  {
   ENUM_PIVOT_TYPE type;
   int             shift;
   double          price;
   datetime        time;
  };

struct Impulse
  {
   bool     valid;
   int      direction;
   double   low;
   double   high;
   int      lowShift;
   int      highShift;
   datetime lowTime;
   datetime highTime;
  };

int      g_atrHandle=INVALID_HANDLE;
int      g_atrSlowHandle=INVALID_HANDLE;
datetime g_lastBar=0;
datetime g_day=0;
double   g_dayStartEquity=0.0;
int      g_consecutiveLosses=0;

// Partial-take state (MaxPositions=1 so a single slot is enough).
ulong    g_partialTicket=0;
bool     g_partialDone=false;

// Zone touch counter for the currently tracked impulse.
datetime g_touchA=0;
datetime g_touchB=0;
int      g_touchN=0;

// MFE/MAE tracking for the single live position (diagnostic).
ulong    g_mfeTicket=0;
double   g_mfeR=0.0;
double   g_maeR=0.0;
int      g_mfeProf=-1;

// Prevent repeated entries from the same structural impulse.
// v4.8 sniper: re-entry allowed after cooldown (touch cap still limits).
datetime g_tradedA[];
datetime g_tradedB[];
datetime g_lastTradeBar=0;

//====================================================================
// INPUTS
//====================================================================
input group "Core"
input long   InpMagic                 = 20260916;
input ENUM_TIMEFRAMES InpTF           = PERIOD_M5;
input double InpRiskPercent           = 0.50;
input double InpMinRR                 = 0.30;
input int    InpMaxPositions          = 1;
input bool   InpDebug                 = true;
input bool   InpForceMinLot            = true;
input double InpMaxLotRiskPercent     = 10.0;
input bool   InpUseMfeLog             = true;
input bool   InpFadeMode              = true;
input double InpRiskMoneyUSD          = 10.0;
input bool   InpAllowReentry          = true;
input int    InpReentryCooldownBars   = 10;
input double InpDailyTargetUSD        = 100.0;

input group "Session"
input bool   InpUseSessionFilter      = false;
input int    InpSessionStartUTC       = 7;
input int    InpSessionEndUTC         = 17;

input group "Structure"
input int    InpATRPeriod             = 14;
input int    InpLookbackBars          = 150;
input int    InpSwingLeft             = 2;
input int    InpSwingRight            = 2;
input double InpMinImpulseATR         = 1.20;
input double InpMaxImpulseATR         = 4.00;
input double InpTrendEfficiencyMin    = 0.35;
input int    InpMaxImpulseAgeBars     = 30;
input bool   InpRequireBOS            = true;
input bool   InpRequireStructure      = true;

input group "Volatility Regime (realtime)"
input bool   InpUseVolGate           = true;
input int    InpATRSlowPeriod        = 50;
input double InpMaxVolRatio          = 2.00;
input double InpMinVolRatio          = 0.50;

input group "Fibonacci Profiles (realtime)"
input double InpEntryFibMin           = 0.382;
input double InpEntryFibMax           = 0.66;
input bool   InpUseDeepProfile        = true;
input double InpDeepFibMin            = 0.66;
input double InpDeepFibMax            = 0.786;
input double InpDeepEffBelow          = 0.50;
input double InpDeepVolAbove          = 1.50;
input int    InpDeepTouchMin          = 3;
input int    InpMaxTouches            = 8;
input double InpDeepSL_ATR            = 2.00;

input group "Adaptive Exits (R from entry)"
input double InpSL_ATR                = 1.00;
input ENUM_TP_MODE InpTPMode          = TP_R_MULT;
input double InpTP_R                  = 3.00;

input group "Reaction"
input double InpMinReactionScore      = 2.0;
input double InpMinBodyATR            = 0.10;
input double InpMaxSpreadATR          = 0.15;
input bool   InpRequireReactionClose  = false;

input group "Position Management (runner)"
input bool   InpUseBreakEven          = true;
input double InpBreakEvenR            = 0.75;
input double InpBreakEvenOffsetR      = 0.05;
input bool   InpUseTrailing            = true;
input double InpTrailStartR           = 1.00;
input double InpTrailATR              = 2.00;
input bool   InpUsePartial            = true;
input double InpPartialR              = 1.00;
input double InpPartialPct            = 25.0;
input bool   InpUseTimeExit           = true;
input int    InpMaxHoldMinutes        = 180;

input group "Daily Protection"
input double InpDailyLossPercent      = 2.0;
input int    InpMaxConsecutiveLosses  = 3;

//====================================================================
// INIT
//====================================================================
int OnInit()
  {
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(30);

   g_atrHandle=iATR(_Symbol,InpTF,InpATRPeriod);
   if(g_atrHandle==INVALID_HANDLE)
      return(INIT_FAILED);

   g_atrSlowHandle=iATR(_Symbol,InpTF,InpATRSlowPeriod);
   if(g_atrSlowHandle==INVALID_HANDLE)
     {
      Print("WARNING: slow ATR unavailable, vol gate fail-open.");
      // Non-fatal: vol gate will fail open without slow ATR.
      g_atrSlowHandle=INVALID_HANDLE;
     }

   ResetDailyState();
   return(INIT_SUCCEEDED);
   }

void OnDeinit(const int reason)
   {
   if(g_atrHandle!=INVALID_HANDLE)
      IndicatorRelease(g_atrHandle);
   if(g_atrSlowHandle!=INVALID_HANDLE)
      IndicatorRelease(g_atrSlowHandle);
   }

//====================================================================
// MAIN
//====================================================================
void OnTick()
   {
   UpdateDailyState();
   ManagePositions();

   if(!IsNewBar())
      return;

   double atr=GetATR(1);
   if(atr<=0.0)
     {
      GateMsg("WAIT: ATR not ready");
      return;
     }

   string reason="";
   if(!TradingAllowed(reason)) { GateMsg("BLOCKED Trading: "+reason); return; }
   if(!SessionAllowed())       { GateMsg("BLOCKED Session (UTC 7-17 filter)"); return; }
   if(!SpreadAllowed(atr))     { GateMsg("BLOCKED Spread (>max ATR ratio)"); return; }
   if(!VolRegimeAllowed())     return;  // self-logging
   if(CountMyPositions()>=InpMaxPositions)
     {
      GateMsg("BLOCKED MaxPositions");
      return;
     }

   double bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
   double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK);

   Impulse setup;
   int direction=FindCurrentSetup(atr,bid,ask,setup);

   if(direction==DIR_NONE)
      return;

   if(InpDebug)
      Print("FIBO setup: ",
            direction==DIR_BUY ? "BUY" : "SELL",
            " A=",DoubleToString(setup.low,2),
            " B=",DoubleToString(setup.high,2),
            " range=",DoubleToString(setup.high-setup.low,2),
            " ageBars=",IntegerToString(
               direction==DIR_BUY ? setup.highShift : setup.lowShift));

   if(direction==DIR_BUY)
      EvaluateBuy(setup,atr,ask,bid);
   else
      EvaluateSell(setup,atr,ask,bid);
  }

//====================================================================
// FIND CURRENT SETUP
//
// v4.2 structural validation:
// We do NOT first classify the entire market into a regime.
// We search for a structural sequence and require BOS plus
// higher-low / lower-high confirmation before using Fibonacci.
// This prevents arbitrary swing pairs from becoming trade setups.
//====================================================================
int FindCurrentSetup(double atr,double bid,double ask,Impulse &out)
  {
   out.valid=false;
   out.direction=DIR_NONE;

   Pivot pivots[];
   int count=CollectPivots(pivots);

   if(count<4)
      return(DIR_NONE);

   CompressPivots(pivots,count);

   if(count<4)
      return(DIR_NONE);

   // Search newest -> oldest.  A candidate is accepted only when:
   // 1) it forms a real structural sequence,
   // 2) it produces BOS / HH-HL or LH-LL when enabled,
   // 3) the impulse is large and directional enough,
   // 4) the impulse is still fresh,
   // 5) current price is actually inside the Fibonacci retracement zone.
   for(int i=count-1;i>=3;i--)
     {
      // ---------------------------------------------------------------
      // BULLISH STRUCTURE: previous LOW -> previous HIGH ->
      //                      higher LOW -> higher HIGH (BOS)
      // ---------------------------------------------------------------
      if(pivots[i].type==PIVOT_HIGH &&
         pivots[i-1].type==PIVOT_LOW &&
         pivots[i-2].type==PIVOT_HIGH &&
         pivots[i-3].type==PIVOT_LOW)
        {
         double previousHigh=pivots[i-2].price;
         double previousLow =pivots[i-3].price;
         double low=pivots[i-1].price;
         double high=pivots[i].price;
         double range=high-low;

         bool bos=(high>previousHigh);
         bool higherLow=(low>previousLow);

         if(InpRequireBOS && !bos)
            continue;

         if(InpRequireStructure && !higherLow)
            continue;

          if(range<InpMinImpulseATR*atr)
             continue;

          if(InpMaxImpulseATR>0 && range>InpMaxImpulseATR*atr)
             continue;

          int impulseAge=pivots[i].shift;
          if(InpMaxImpulseAgeBars>0 && impulseAge>InpMaxImpulseAgeBars)
             continue;

          if(iClose(_Symbol,InpTF,pivots[i].shift)<=
             iClose(_Symbol,InpTF,pivots[i-1].shift))
             continue;

          double efficiency=ImpulseEfficiency(pivots[i-1].shift,
                                              pivots[i].shift);
          if(efficiency<InpTrendEfficiencyMin)
             continue;

          double zoneHigh=high-range*InpEntryFibMin;
          double zoneLow =high-range*InpEntryFibMax;

          if(bid>=zoneLow && bid<=zoneHigh)
            {
             out.valid=true;
             out.direction=DIR_BUY;
            out.low=low;
            out.high=high;
            out.lowShift=pivots[i-1].shift;
            out.highShift=pivots[i].shift;
            out.lowTime=pivots[i-1].time;
            out.highTime=pivots[i].time;

            if(InpDebug)
               Print("STRUCTURE BUY: ",
                     "BOS=",bos ? "true" : "false",
                     " HL=",higherLow ? "true" : "false",
                     " rangeATR=",DoubleToString(range/atr,2),
                     " efficiency=",DoubleToString(efficiency,2),
                     " age=",impulseAge,
                     " FibZone=",DoubleToString(zoneLow,2),
                     "-",DoubleToString(zoneHigh,2));

            return(DIR_BUY);
           }
        }

      // ---------------------------------------------------------------
      // BEARISH STRUCTURE: previous HIGH -> previous LOW ->
      //                      lower HIGH -> lower LOW (BOS)
      // ---------------------------------------------------------------
      if(pivots[i].type==PIVOT_LOW &&
         pivots[i-1].type==PIVOT_HIGH &&
         pivots[i-2].type==PIVOT_LOW &&
         pivots[i-3].type==PIVOT_HIGH)
        {
         double previousLow =pivots[i-2].price;
         double previousHigh=pivots[i-3].price;
         double high=pivots[i-1].price;
         double low=pivots[i].price;
         double range=high-low;

         bool bos=(low<previousLow);
         bool lowerHigh=(high<previousHigh);

         if(InpRequireBOS && !bos)
            continue;

         if(InpRequireStructure && !lowerHigh)
            continue;

          if(range<InpMinImpulseATR*atr)
             continue;

          if(InpMaxImpulseATR>0 && range>InpMaxImpulseATR*atr)
             continue;

          int impulseAge=pivots[i].shift;
          if(InpMaxImpulseAgeBars>0 && impulseAge>InpMaxImpulseAgeBars)
             continue;

          if(iClose(_Symbol,InpTF,pivots[i].shift)>=
             iClose(_Symbol,InpTF,pivots[i-1].shift))
             continue;

          double efficiency=ImpulseEfficiency(pivots[i-1].shift,
                                              pivots[i].shift);
          if(efficiency<InpTrendEfficiencyMin)
             continue;

          double zoneLow =low+range*InpEntryFibMin;
          double zoneHigh=low+range*InpEntryFibMax;

          if(ask>=zoneLow && ask<=zoneHigh)
            {
             out.valid=true;
             out.direction=DIR_SELL;
             out.low=low;
             out.high=high;
             out.lowShift=pivots[i].shift;
             out.highShift=pivots[i-1].shift;
             out.lowTime=pivots[i].time;
             out.highTime=pivots[i-1].time;

             if(InpDebug)
                Print("STRUCTURE SELL: ",
                      "BOS=",bos ? "true" : "false",
                      " LH=",lowerHigh ? "true" : "false",
                      " rangeATR=",DoubleToString(range/atr,2),
                      " efficiency=",DoubleToString(efficiency,2),
                      " age=",impulseAge,
                      " FibZone=",DoubleToString(zoneLow,2),
                      "-",DoubleToString(zoneHigh,2));

             return(DIR_SELL);
           }
        }
     }

   return(DIR_NONE);
  }

//====================================================================
// IMPULSE QUALITY
//====================================================================
// Measures how efficiently price travelled between the two structural
// pivot endpoints. 1.0 = nearly one-directional movement; lower values
// indicate choppy movement / excessive back-and-forth price action.
//====================================================================
double ImpulseEfficiency(int olderShift,int newerShift)
  {
   if(olderShift<=newerShift)
      return(0.0);

   int bars=olderShift-newerShift;
   if(bars<1)
      return(0.0);

   double path=0.0;

   for(int shift=newerShift;shift<olderShift;shift++)
     {
      double c1=iClose(_Symbol,InpTF,shift);
      double c2=iClose(_Symbol,InpTF,shift+1);

      if(c1==0.0 || c2==0.0)
         return(0.0);

      path+=MathAbs(c1-c2);
     }

   if(path<=0.0)
      return(0.0);

   double net=MathAbs(iClose(_Symbol,InpTF,newerShift)-
                      iClose(_Symbol,InpTF,olderShift));

   return(net/path);
  }

//====================================================================
// PROFILE SELECTOR (v4.5)
//
// 0 = Normal pullback (50-66%, TP at extreme)
// 1 = Deep/chop     (66-78.6%, TP at mid-impulse, wider SL)
// Deep triggers: weak efficiency, hot ATR ratio, or repeated touches
// of the same zone (support going stale -> demand a discount).
// Returns -1 when the zone is exhausted (touches > max).
//====================================================================
int SelectProfile(const Impulse &impulse,double efficiency,double atrRatio,
                  double zoneLow,double zoneHigh,double closePrice)
   {
   if(impulse.lowTime==g_touchA && impulse.highTime==g_touchB)
     {
      if(closePrice>=zoneLow && closePrice<=zoneHigh)
         g_touchN++;
     }
   else
     {
      g_touchA=impulse.lowTime;
      g_touchB=impulse.highTime;
      g_touchN=(closePrice>=zoneLow && closePrice<=zoneHigh) ? 1 : 0;
     }

   if(InpMaxTouches>0 && g_touchN>InpMaxTouches)
     {
      if(InpDebug)
         Print("Exhausted zone: touches=",g_touchN);
      return(-1);
     }

   if(!InpUseDeepProfile)
      return(0);

   if(efficiency<InpDeepEffBelow)
      return(1);
   if(InpDeepVolAbove>0 && atrRatio>InpDeepVolAbove)
      return(1);
   if(InpDeepTouchMin>0 && g_touchN>=InpDeepTouchMin)
      return(1);

   return(0);
   }

double AtrRatio(double atr)
   {
   double slow=GetSlowATR(1);
   if(atr<=0.0) return(1.0);
   if(slow<=0.0) return(1.0);
   return(atr/slow);
   }

//====================================================================
// BULLISH SETUP (v4.6: fade executes SHORT here — same zone, mirrored
// reaction/SL/TP; InpFadeMode=false = original LONG)
//====================================================================
void EvaluateBuy(const Impulse &impulse,double atr,double ask,double bid)
   {
   double range=impulse.high-impulse.low;
   if(range<=0.0) return;

   double zoneHigh=impulse.high-range*InpEntryFibMin;
   double zoneLow =impulse.high-range*InpEntryFibMax;

   if(bid<zoneLow || bid>zoneHigh)
      return;

   // Avoid re-entering the exact same impulse.
   if(AlreadyTradedImpulse(impulse))
      return;

   // Fade mirrors the reaction: expect continuation DOWN, not bounce UP.
   double score=ReactionScore(!InpFadeMode,atr,zoneLow,zoneHigh);
   if(score<InpMinReactionScore)
      return;

   double c=iClose(_Symbol,InpTF,1);
   if(InpRequireReactionClose)
     {
      if(c<zoneLow || c>zoneHigh)
         return;
     }

   double eff=ImpulseEfficiency(impulse.lowShift,impulse.highShift);
   int prof=SelectProfile(impulse,eff,AtrRatio(atr),zoneLow,zoneHigh,c);
   if(prof<0)
      return;

   if(prof==1)
     {
      zoneHigh=impulse.high-range*InpDeepFibMin;
      zoneLow =impulse.high-range*InpDeepFibMax;
      if(bid<zoneLow || bid>zoneHigh)
         return;
      if(InpRequireReactionClose && (c<zoneLow || c>zoneHigh))
         return;
     }

   double slATR=(prof==1 ? InpDeepSL_ATR : InpSL_ATR);
   double riskDist=slATR*atr;
   double sl,tp;
   string cm;

   if(!InpFadeMode)
     {
      sl=ask-riskDist;
      if(InpTPMode==TP_R_MULT)
         tp=ask+InpTP_R*riskDist;
      else if(prof==1 || InpTPMode==TP_AT_MID)
         tp=(impulse.high+impulse.low)/2.0;
      else
         tp=impulse.high;
      if(tp<=ask || sl>=ask)
         return;
      cm="FiboV4.8 BUY PROF="+IntegerToString(prof);
      if(OpenPosition(ORDER_TYPE_BUY,ask,sl,tp,cm))
         MarkImpulse(impulse);
     }
   else
     {
      // FADE: short the pullback, target the origin (reversal).
      sl=bid+riskDist;
      if(InpTPMode==TP_R_MULT)
         tp=bid-InpTP_R*riskDist;
      else if(prof==1)
         tp=(impulse.high+impulse.low)/2.0;
      else if(InpTPMode==TP_AT_MID)
         tp=(impulse.high+impulse.low)/2.0;
      else
         tp=impulse.low;
      if(tp>=bid || sl<=bid)
         return;
      cm="FiboV4.8 SELL-FADE PROF="+IntegerToString(prof);
      if(OpenPosition(ORDER_TYPE_SELL,bid,sl,tp,cm))
         MarkImpulse(impulse);
     }
   }

//====================================================================
// BEARISH SETUP (v4.6: fade executes LONG here)
//====================================================================
void EvaluateSell(const Impulse &impulse,double atr,double ask,double bid)
   {
   double range=impulse.high-impulse.low;
   if(range<=0.0) return;

   double zoneLow =impulse.low+range*InpEntryFibMin;
   double zoneHigh=impulse.low+range*InpEntryFibMax;

   if(ask<zoneLow || ask>zoneHigh)
      return;

   if(AlreadyTradedImpulse(impulse))
      return;

   bool wantBearish=!InpFadeMode;
   double score=ReactionScore(!wantBearish,atr,zoneLow,zoneHigh);
   if(score<InpMinReactionScore)
      return;

   double c=iClose(_Symbol,InpTF,1);
   if(InpRequireReactionClose)
     {
      if(c<zoneLow || c>zoneHigh)
         return;
     }

   double eff=ImpulseEfficiency(impulse.highShift,impulse.lowShift);
   int prof=SelectProfile(impulse,eff,AtrRatio(atr),zoneLow,zoneHigh,c);
   if(prof<0)
      return;

   if(prof==1)
     {
      zoneLow =impulse.low+range*InpDeepFibMin;
      zoneHigh=impulse.low+range*InpDeepFibMax;
      if(ask<zoneLow || ask>zoneHigh)
         return;
      if(InpRequireReactionClose && (c<zoneLow || c>zoneHigh))
         return;
     }

   double slATR=(prof==1 ? InpDeepSL_ATR : InpSL_ATR);
   double riskDist=slATR*atr;
   double sl,tp;
   string cm;

   if(!InpFadeMode)
     {
      sl=bid+riskDist;
      if(InpTPMode==TP_R_MULT)
         tp=bid-InpTP_R*riskDist;
      else if(prof==1 || InpTPMode==TP_AT_MID)
         tp=(impulse.high+impulse.low)/2.0;
      else
         tp=impulse.low;
      if(tp>=bid || sl<=bid)
         return;
      cm="FiboV4.8 SELL PROF="+IntegerToString(prof);
      if(OpenPosition(ORDER_TYPE_SELL,bid,sl,tp,cm))
         MarkImpulse(impulse);
     }
   else
     {
      // FADE: buy the pullback, target the origin (reversal).
      sl=ask-riskDist;
      if(InpTPMode==TP_R_MULT)
         tp=ask+InpTP_R*riskDist;
      else if(prof==1)
         tp=(impulse.high+impulse.low)/2.0;
      else if(InpTPMode==TP_AT_MID)
         tp=(impulse.high+impulse.low)/2.0;
      else
         tp=impulse.high;
      if(tp<=ask || sl>=ask)
         return;
      cm="FiboV4.8 BUY-FADE PROF="+IntegerToString(prof);
      if(OpenPosition(ORDER_TYPE_BUY,ask,sl,tp,cm))
         MarkImpulse(impulse);
     }
   }

//====================================================================
// REACTION
//
// Score:
// +1 directional candle
// +1 body >= threshold
// +1 rejection wick
// +1 candle range >= 0.8 ATR
// +1 close near directional extreme
//
// v4 additionally requires the previous closed candle to TOUCH the
// Fibonacci zone, so a reaction candle cannot be unrelated to the zone.
//====================================================================
double ReactionScore(bool bullish,double atr,double zoneLow,double zoneHigh)
  {
   double o=iOpen(_Symbol,InpTF,1);
   double c=iClose(_Symbol,InpTF,1);
   double h=iHigh(_Symbol,InpTF,1);
   double l=iLow(_Symbol,InpTF,1);

   if(h<=l || atr<=0.0)
      return(0.0);

   bool touched=(h>=zoneLow && l<=zoneHigh);
   if(!touched)
      return(0.0);

   double body=MathAbs(c-o);
   double range=h-l;
   double upperWick=h-MathMax(o,c);
   double lowerWick=MathMin(o,c)-l;

   double score=0.0;

   if(bullish && c>o) score+=1.0;
   if(!bullish && c<o) score+=1.0;

   if(body>=InpMinBodyATR*atr)
      score+=1.0;

   if(bullish &&
      lowerWick>=MathMax(body*0.8,range*0.15))
      score+=1.0;

   if(!bullish &&
      upperWick>=MathMax(body*0.8,range*0.15))
      score+=1.0;

   if(range>=atr*0.8)
      score+=1.0;

   if(bullish && (h-c)<=range*0.30)
      score+=1.0;

   if(!bullish && (c-l)<=range*0.30)
      score+=1.0;

   return(score);
  }

//====================================================================
// PIVOTS
//====================================================================
int CollectPivots(Pivot &arr[])
  {
   int bars=Bars(_Symbol,InpTF);
   if(bars<InpLookbackBars+InpSwingLeft+InpSwingRight+10)
      return(0);

   ArrayResize(arr,InpLookbackBars);
   int count=0;

   int maxShift=MathMin(InpLookbackBars,
                        bars-InpSwingRight-2);

   for(int shift=maxShift;shift>=InpSwingRight+1;shift--)
     {
      if(IsSwingHigh(shift))
        {
         arr[count].type=PIVOT_HIGH;
         arr[count].shift=shift;
         arr[count].price=iHigh(_Symbol,InpTF,shift);
         arr[count].time=iTime(_Symbol,InpTF,shift);
         count++;
        }

      if(IsSwingLow(shift))
        {
         arr[count].type=PIVOT_LOW;
         arr[count].shift=shift;
         arr[count].price=iLow(_Symbol,InpTF,shift);
         arr[count].time=iTime(_Symbol,InpTF,shift);
         count++;
        }

      if(count>=ArraySize(arr))
         break;
     }

   ArrayResize(arr,count);
   return(count);
  }

void CompressPivots(Pivot &arr[],int &count)
  {
   if(count<=1) return;

   Pivot temp[];
   ArrayResize(temp,count);
   int n=0;

   for(int i=0;i<count;i++)
     {
      if(n==0)
        {
         temp[n++]=arr[i];
         continue;
        }

      if(temp[n-1].type!=arr[i].type)
        {
         temp[n++]=arr[i];
         continue;
        }

      if(arr[i].type==PIVOT_HIGH &&
         arr[i].price>temp[n-1].price)
         temp[n-1]=arr[i];

      if(arr[i].type==PIVOT_LOW &&
         arr[i].price<temp[n-1].price)
         temp[n-1]=arr[i];
     }

   ArrayResize(arr,n);
   for(int i=0;i<n;i++)
      arr[i]=temp[i];

   count=n;
  }

bool IsSwingHigh(int shift)
  {
   double x=iHigh(_Symbol,InpTF,shift);

   for(int i=1;i<=InpSwingLeft;i++)
      if(x<=iHigh(_Symbol,InpTF,shift+i))
         return(false);

   for(int i=1;i<=InpSwingRight;i++)
      if(x<=iHigh(_Symbol,InpTF,shift-i))
         return(false);

   return(true);
  }

bool IsSwingLow(int shift)
  {
   double x=iLow(_Symbol,InpTF,shift);

   for(int i=1;i<=InpSwingLeft;i++)
      if(x>=iLow(_Symbol,InpTF,shift+i))
         return(false);

   for(int i=1;i<=InpSwingRight;i++)
      if(x>=iLow(_Symbol,InpTF,shift-i))
         return(false);

   return(true);
  }

//====================================================================
// ORDER
//====================================================================
bool OpenPosition(ENUM_ORDER_TYPE type,double entry,double sl,double tp,string comment)
  {
   int digits=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);

   double minStop=MinimumStopDistance();

   if(type==ORDER_TYPE_BUY)
     {
      if(entry-sl<minStop)
         sl=entry-minStop;
      if(tp-entry<minStop)
         tp=entry+minStop;
     }
   else
     {
      if(sl-entry<minStop)
         sl=entry+minStop;
      if(entry-tp<minStop)
         tp=entry-minStop;
     }

   double risk=MathAbs(entry-sl);
   double reward=MathAbs(tp-entry);

   if(risk<=0.0) return(false);

   double rr=reward/risk;

   if(rr<InpMinRR)
     {
      if(InpDebug)
         Print("Rejected: RR=",DoubleToString(rr,2));
      return(false);
     }

   double volume=CalculateRiskVolume(risk);
   if(volume<=0.0)
     {
      if(InpDebug)
        {
         double minVolume=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
         Print("Rejected: calculated volume below broker minimum. ",
               "ForceMinLot=",InpForceMinLot ? "true" : "false",
               " BrokerMin=",DoubleToString(minVolume,2));
        }
      return(false);
     }

   sl=NormalizeDouble(sl,digits);
   tp=NormalizeDouble(tp,digits);

   bool ok=false;
   string orderComment=comment+" RISK="+DoubleToString(risk,8);

   if(type==ORDER_TYPE_BUY)
      ok=trade.Buy(volume,_Symbol,0.0,sl,tp,orderComment);
   else
      ok=trade.Sell(volume,_Symbol,0.0,sl,tp,orderComment);

   if(!ok)
     {
      Print("Order failed: ",
            trade.ResultRetcode()," ",
            trade.ResultRetcodeDescription());
      return(false);
     }

   if(InpDebug)
     {
      double minVolume=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
      double step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);

      Print("ORDER OPENED ",
            type==ORDER_TYPE_BUY ? "BUY" : "SELL",
            " lot=",DoubleToString(volume,2),
            " minLot=",DoubleToString(minVolume,2),
            " step=",DoubleToString(step,2),
            " SL=",DoubleToString(sl,digits),
            " TP=",DoubleToString(tp,digits),
            " RR=",DoubleToString(rr,2),
            " RiskDistance=",DoubleToString(risk,digits));
     }

   return(true);
  }

double CalculateRiskVolume(double stopDistance)
   {
   double equity=AccountInfoDouble(ACCOUNT_EQUITY);
   // v4.8: fixed $ risk per trade when enabled (daily sprint sizing).
   double riskMoney=(InpRiskMoneyUSD>0.0 ? InpRiskMoneyUSD :
                     equity*InpRiskPercent/100.0);

   double tickValue=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE);
   double tickSize =SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);

   if(tickValue<=0.0 || tickSize<=0.0)
      return(0.0);

   double moneyPerLot=(stopDistance/tickSize)*tickValue;
   if(moneyPerLot<=0.0)
      return(0.0);

   double calculatedVolume=riskMoney/moneyPerLot;

   double minVolume=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   double maxVolume=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   double step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);

   if(minVolume<=0.0 || maxVolume<=0.0)
      return(0.0);

   if(step<=0.0)
      step=minVolume;

   // Normalize the risk-based volume DOWN to the broker volume step.
   double volume=MathFloor(calculatedVolume/step)*step;

    // If the risk-based volume is below the broker minimum, optionally
    // force the minimum lot so valid Fibo setups can actually trade.
    // v4.3: guard against over-risk on small accounts (Jul-2026: $100
    // account took -$24 on 0.01 lot = 24% instead of 0.5%).
    if(volume<minVolume)
      {
       if(!InpForceMinLot)
          return(0.0);

       double actualRiskMoney=minVolume*moneyPerLot;
       double actualPct=(equity>0.0 ? actualRiskMoney/equity*100.0 : 1000.0);
       if(InpMaxLotRiskPercent>0 && actualPct>InpMaxLotRiskPercent)
         {
          if(InpDebug)
             Print("Rejected: min lot over-risk. Actual=",
                   DoubleToString(actualPct,2),"% > max ",
                   DoubleToString(InpMaxLotRiskPercent,2),"%");
          return(0.0);
         }

       volume=minVolume;

      if(InpDebug)
        {
         Print("Risk lot below broker minimum: ",
               "Risk lot=",DoubleToString(calculatedVolume,4),
               " Broker min=",DoubleToString(minVolume,2),
               " Using lot=",DoubleToString(volume,2),
               " Risk%=",DoubleToString(InpRiskPercent,2));
        }
     }

   // Safety cap at broker maximum.
   if(volume>maxVolume)
      volume=maxVolume;

   volume=NormalizeVolume(volume);

   // Final broker bounds check.
   if(volume<minVolume)
      volume=minVolume;

   if(volume>maxVolume)
      volume=maxVolume;

   return(volume);
  }

double NormalizeVolume(double volume)
  {
   double step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   int digits=2;

   if(step>=1.0) digits=0;
   else if(step>=0.1) digits=1;
   else if(step>=0.01) digits=2;
   else if(step>=0.001) digits=3;
   else digits=4;

   return(NormalizeDouble(volume,digits));
  }

double MinimumStopDistance()
  {
   double point=SymbolInfoDouble(_Symbol,SYMBOL_POINT);
   long stops=(long)SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL);
   long freeze=(long)SymbolInfoInteger(_Symbol,SYMBOL_TRADE_FREEZE_LEVEL);

   long level=MathMax(stops,freeze);
   return((double)level*point*1.10);
  }

//====================================================================
// POSITION MANAGEMENT
//
// v3 bug fixed:
// v3 calculated "initialRisk" from the CURRENT SL. After BE/trailing,
// R changed. v4 stores original risk in the position comment.
//====================================================================
void ManagePositions()
  {
   double atr=GetATR(1);
   if(atr<=0.0) return;

   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0 || !PositionSelectByTicket(ticket))
         continue;

      if(PositionGetString(POSITION_SYMBOL)!=_Symbol)
         continue;

      if((long)PositionGetInteger(POSITION_MAGIC)!=InpMagic)
         continue;

      ENUM_POSITION_TYPE type=(ENUM_POSITION_TYPE)
         PositionGetInteger(POSITION_TYPE);

      double open=PositionGetDouble(POSITION_PRICE_OPEN);
      double sl=PositionGetDouble(POSITION_SL);
      double tp=PositionGetDouble(POSITION_TP);

      double bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
      double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK);
      double current=(type==POSITION_TYPE_BUY)?bid:ask;

      double initialRisk=GetInitialRisk(ticket,open,sl);
      if(initialRisk<=0.0)
         continue;

      double profitDistance=(type==POSITION_TYPE_BUY)?
         current-open:open-current;

      double r=profitDistance/initialRisk;

      // v4.5 MFE/MAE diagnostic (no behavior change).
      TrackMfe(ticket,r);

      if(InpUseTimeExit)
        {
         datetime openTime=(datetime)
            PositionGetInteger(POSITION_TIME);

         if(TimeCurrent()-openTime>=InpMaxHoldMinutes*60)
           {
            trade.PositionClose(ticket);
            continue;
           }
        }

      // v4.4 PARTIAL: bank InpPartialPct% at InpPartialR once per ticket.
      if(InpUsePartial && !IsPartialDone(ticket) && r>=InpPartialR)
        {
         double vol=PositionGetDouble(POSITION_VOLUME);
         double minVol=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
         double closeVol=NormalizeDouble(vol*InpPartialPct/100.0,2);
         if(closeVol>=minVol && vol-closeVol>=minVol)
           {
            if(trade.PositionClosePartial(ticket,closeVol))
              {
               g_partialTicket=ticket;
               g_partialDone=true;
               if(InpDebug)
                  Print("PARTIAL closed ",DoubleToString(InpPartialPct,0),
                        "% at ",DoubleToString(r,2),"R ticket=",ticket);
               continue;
              }
           }
        }

      if(InpUseBreakEven && r>=InpBreakEvenR)
        {
         double newSL;

         if(type==POSITION_TYPE_BUY)
            newSL=open+InpBreakEvenOffsetR*initialRisk;
         else
            newSL=open-InpBreakEvenOffsetR*initialRisk;

         bool improve=
            (type==POSITION_TYPE_BUY &&
             (sl==0.0 || newSL>sl)) ||
            (type==POSITION_TYPE_SELL &&
             (sl==0.0 || newSL<sl));

         if(improve)
            trade.PositionModify(ticket,newSL,tp);
        }

      if(InpUseTrailing && r>=InpTrailStartR)
        {
         double newSL;

         if(type==POSITION_TYPE_BUY)
           {
            newSL=bid-InpTrailATR*atr;
            if(newSL>sl && newSL<bid)
               trade.PositionModify(ticket,newSL,tp);
           }
         else
           {
            newSL=ask+InpTrailATR*atr;
            if((sl==0.0 || newSL<sl) && newSL>ask)
               trade.PositionModify(ticket,newSL,tp);
           }
        }
     }
  }

double GetInitialRisk(ulong ticket,double open,double currentSL)
  {
   // Position comment is used as a simple persistent store.
   string comment=PositionGetString(POSITION_COMMENT);

   int p=StringFind(comment,"RISK=");
   if(p>=0)
     {
      string s=StringSubstr(comment,p+5);
      double value=StringToDouble(s);
      if(value>0.0)
         return(value);
     }

   // Legacy/fallback positions.
   return(MathAbs(open-currentSL));
  }

//====================================================================
// IMPULSE STATE (v4.8 sniper: same impulse may re-fire after cooldown;
// touch cap in SelectProfile remains the limiter)
//====================================================================
bool ReentryCooldownOk(const Impulse &impulse);

bool AlreadyTradedImpulse(const Impulse &impulse)
   {
    if(InpAllowReentry)
       return(!ReentryCooldownOk(impulse));
    int n=ArraySize(g_tradedA);
    for(int i=0;i<n;i++)
       if(impulse.lowTime==g_tradedA[i] && impulse.highTime==g_tradedB[i])
          return(true);
    return(false);
   }

// True when enough bars passed since this impulse last produced a trade.
bool ReentryCooldownOk(const Impulse &impulse)
   {
    int n=ArraySize(g_tradedA);
    bool seen=false;
    for(int i=0;i<n;i++)
       if(impulse.lowTime==g_tradedA[i] && impulse.highTime==g_tradedB[i])
         {
          seen=true;
          break;
         }
    if(!seen)
       return(true);
    if(g_lastTradeBar==0)
       return(true);
    datetime nowBar=iTime(_Symbol,InpTF,0);
    if(nowBar==0)
       return(false);
    long tfSec=PeriodSeconds(InpTF);
    if(tfSec<=0)
       return(false);
    return((nowBar-g_lastTradeBar)>=InpReentryCooldownBars*tfSec);
   }

void MarkImpulse(const Impulse &impulse)
   {
    int n=ArraySize(g_tradedA);
    ArrayResize(g_tradedA,n+1);
    ArrayResize(g_tradedB,n+1);
    g_tradedA[n]=impulse.lowTime;
    g_tradedB[n]=impulse.highTime;
    datetime bar=iTime(_Symbol,InpTF,0);
    if(bar!=0)
       g_lastTradeBar=bar;
    // Keep only the most recent 20.
    if(ArraySize(g_tradedA)>20)
      {
       for(int i=0;i<20;i++)
         {
          g_tradedA[i]=g_tradedA[ArraySize(g_tradedA)-20+i];
          g_tradedB[i]=g_tradedB[ArraySize(g_tradedB)-20+i];
         }
       ArrayResize(g_tradedA,20);
       ArrayResize(g_tradedB,20);
      }
   }

//====================================================================
// SESSION / SPREAD / SAFETY
//====================================================================
bool SessionAllowed()
  {
   if(!InpUseSessionFilter)
      return(true);

   MqlDateTime utc;
   TimeToStruct(TimeGMT(),utc);

   int now=utc.hour*60+utc.min;
   int start=InpSessionStartUTC*60;
   int end=InpSessionEndUTC*60;

   if(start<=end)
      return(now>=start && now<end);

   return(now>=start || now<end);
  }

// Throttled gate diagnostics: max 1 line/hour so silent blocks
// (the Exness 0-trade case) become visible without log spam.
void GateMsg(string msg)
   {
   static datetime lastMsg=0;
   if(!InpDebug)
      return;
   if(TimeCurrent()-lastMsg<3600)
      return;
   lastMsg=TimeCurrent();
   double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK);
   double bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
   double point=SymbolInfoDouble(_Symbol,SYMBOL_POINT);
   double spreadPts=(point>0.0 ? (ask-bid)/point : -1.0);
   Print(msg,
         " time=",TimeToString(TimeCurrent(),TIME_DATE|TIME_MINUTES),
         " spreadPts=",DoubleToString(spreadPts,1),
         " digits=",(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS));
   }

bool SpreadAllowed(double atr)
   {
   // v4.41: ATR-based spread gate (digit-agnostic).
   // Old fixed 150-point cap silently blocked everything on 3-digit
   // Exness pricing (same $ spread = 10x more points than 2-digit IUX).
   double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK);
   double bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
   if(ask<=0.0 || bid<=0.0 || atr<=0.0)
      return(false);
   return((ask-bid)<=InpMaxSpreadATR*atr);
   }

//====================================================================
// VOL REGIME GATE (v4.4 realtime adaptive)
//
// Compares fast ATR(14) to slow ATR(50):
//  ratio > MaxVolRatio -> volatility spike (news) -> stand aside
//  ratio < MinVolRatio -> dead market (no fuel for 2R TP) -> stand aside
// Fail-open when slow ATR is unavailable (e.g. short history).
//====================================================================
bool VolRegimeAllowed()
   {
   if(!InpUseVolGate)
      return(true);

   double fast=GetATR(1);
   double slow=GetSlowATR(1);
   if(fast<=0.0)
      return(false);
   if(slow<=0.0)
      return(true);

   double ratio=fast/slow;
   if(InpMaxVolRatio>0 && ratio>InpMaxVolRatio)
     {
      GateMsg("BLOCKED VolGate spike: ATR ratio="+DoubleToString(ratio,2));
      return(false);
     }
   if(InpMinVolRatio>0 && ratio<InpMinVolRatio)
     {
      GateMsg("BLOCKED VolGate dead: ATR ratio="+DoubleToString(ratio,2));
      return(false);
     }
   return(true);
   }

// Partial state is per-ticket; reset once the ticket is gone.
bool IsPartialDone(ulong ticket)
   {
   if(!g_partialDone)
      return(false);
   if(ticket!=g_partialTicket)
      return(false);
   if(!PositionSelectByTicket(ticket))
     {
      g_partialTicket=0;
      g_partialDone=false;
      return(false);
     }
   return(true);
   }

// v4.5: track max favorable/adverse excursion in R for the live ticket.
// Profile is parsed from the position comment ("PROF=n").
void TrackMfe(ulong ticket,double r)
   {
   if(!InpUseMfeLog)
      return;
   if(ticket!=g_mfeTicket)
     {
      g_mfeTicket=ticket;
      g_mfeR=r;
      g_maeR=r;
      g_mfeProf=ParseProf();
     }
   else
     {
      if(r>g_mfeR) g_mfeR=r;
      if(r<g_maeR) g_maeR=r;
     }
   }

int ParseProf()
   {
   string comment=PositionGetString(POSITION_COMMENT);
   int p=StringFind(comment,"PROF=");
   if(p<0)
      return(-1);
   return((int)StringToInteger(StringSubstr(comment,p+5)));
   }

bool TradingAllowed(string &reason)
   {
   reason="";
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED))
     {
      reason="terminal trade not allowed";
      return(false);
     }

   if(!MQLInfoInteger(MQL_TRADE_ALLOWED))
     {
      reason="EA trade not allowed";
      return(false);
     }

   if(g_dayStartEquity<=0.0)
     {
      reason="no day equity baseline";
      return(false);
     }

   double equity=AccountInfoDouble(ACCOUNT_EQUITY);

   // v4.8 DAILY TARGET LOCK: bank the day, stop new entries.
   // No daily stop-loss per operator instruction (bust accepted).
   if(InpDailyTargetUSD>0 && g_dayStartEquity>0 &&
      equity-g_dayStartEquity>=InpDailyTargetUSD)
     {
      reason="daily target locked";
      return(false);
     }

   double dailyLoss=
      (g_dayStartEquity-equity)/g_dayStartEquity*100.0;

   if(dailyLoss>=InpDailyLossPercent)
     {
      reason="daily loss limit";
      return(false);
     }

   if(g_consecutiveLosses>=InpMaxConsecutiveLosses)
     {
      reason="max consecutive losses";
      return(false);
     }

   return(true);
   }

int CountMyPositions()
  {
   int count=0;

   for(int i=0;i<PositionsTotal();i++)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0 || !PositionSelectByTicket(ticket))
         continue;

      if(PositionGetString(POSITION_SYMBOL)==_Symbol &&
         (long)PositionGetInteger(POSITION_MAGIC)==InpMagic)
         count++;
     }

   return(count);
  }

//====================================================================
// BAR / ATR / DAILY
//====================================================================
bool IsNewBar()
  {
   datetime t=iTime(_Symbol,InpTF,0);

   if(t==0) return(false);

   if(t!=g_lastBar)
     {
      g_lastBar=t;
      return(true);
     }

   return(false);
  }

double GetATR(int shift)
   {
   if(g_atrHandle==INVALID_HANDLE)
      return(0.0);

   double buffer[];
   ArraySetAsSeries(buffer,true);

   if(CopyBuffer(g_atrHandle,0,shift,1,buffer)!=1)
      return(0.0);

   return(buffer[0]);
   }

double GetSlowATR(int shift)
   {
   if(g_atrSlowHandle==INVALID_HANDLE)
      return(0.0);

   double buffer[];
   ArraySetAsSeries(buffer,true);

   if(CopyBuffer(g_atrSlowHandle,0,shift,1,buffer)!=1)
      return(0.0);

   return(buffer[0]);
   }

void ResetDailyState()
  {
   MqlDateTime tm;
   TimeToStruct(TimeCurrent(),tm);

   tm.hour=0;
   tm.min=0;
   tm.sec=0;

   g_day=StructToTime(tm);
   g_dayStartEquity=AccountInfoDouble(ACCOUNT_EQUITY);
   g_consecutiveLosses=0;
  }

void UpdateDailyState()
  {
   MqlDateTime tm;
   TimeToStruct(TimeCurrent(),tm);

   tm.hour=0;
   tm.min=0;
   tm.sec=0;

   datetime today=StructToTime(tm);

   if(today!=g_day)
      ResetDailyState();
  }

//====================================================================
// TRADE TRANSACTION
//====================================================================
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
  {
   if(trans.type!=TRADE_TRANSACTION_DEAL_ADD)
      return;

   if(trans.deal==0 || !HistoryDealSelect(trans.deal))
      return;

   if(HistoryDealGetString(trans.deal,DEAL_SYMBOL)!=_Symbol)
      return;

   if((long)HistoryDealGetInteger(trans.deal,DEAL_MAGIC)!=InpMagic)
      return;

   long entry=HistoryDealGetInteger(trans.deal,DEAL_ENTRY);

   if(entry!=DEAL_ENTRY_OUT && entry!=DEAL_ENTRY_OUT_BY)
      return;

   double profit=
      HistoryDealGetDouble(trans.deal,DEAL_PROFIT)+
      HistoryDealGetDouble(trans.deal,DEAL_SWAP)+
      HistoryDealGetDouble(trans.deal,DEAL_COMMISSION);

   if(profit<0.0)
      g_consecutiveLosses++;
   else if(profit>0.0)
      g_consecutiveLosses=0;

   // v4.5 MFE/MAE diagnostic per closed trade.
   if(InpUseMfeLog)
     {
      ulong posId=(ulong)HistoryDealGetInteger(trans.deal,DEAL_POSITION_ID);
      if(posId==g_mfeTicket && g_mfeProf>=0)
         Print("MFELOG PROF=",g_mfeProf,
               " MFE_R=",DoubleToString(g_mfeR,2),
               " MAE_R=",DoubleToString(g_maeR,2),
               " P/L=",DoubleToString(profit,2));
      if(posId==g_mfeTicket)
        {
         g_mfeTicket=0;
         g_mfeProf=-1;
        }
     }
   }

//+------------------------------------------------------------------+
