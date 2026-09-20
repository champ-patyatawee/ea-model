//+------------------------------------------------------------------+
//| FiboAdaptiveEA_v5.0.mq5                                            |
//| Structural Fibonacci FADE EA - regime-study branch                |
//|                                                                  |
//| v5.00 = v4.90 baseline (adaptive toggles default OFF) + a place for
//| regime work. Phase-1 anatomy over 18 months (2025.01-2026.06) shows
//| months differ almost entirely by WINRATE (losing months 40-45% vs
//| winning 56-66%); payoff is flat. Worst month 2026.03 (-248) was a
//| one-sided down trend where Long fades won only 38% (Long net -409).
//| Next: test an external regime filter (trend / volatility) in this file.
//| Phase-2 result (Regime Filter, H1 EMA slope vs H1 ATR): no net gain.
//| baseline train +2146 PF1.17 DD4.07 / OOS +326 PF1.15. thr=1.0 gives
//| train +2104 PF1.17 DD3.45 (net -2%, DD -15%) and OOS +316 -- i.e. a
//| mild risk reduction, not a profit gain. thr<1 hurts net. Default OFF.
//|//| v4.90 (this file, NEW; v4.6 file left untouched): adaptive-Fibo
//| experiments, all DEFAULT OFF because none beat the baseline:
//|   - InpUseATRAdaptiveZone: shift the retracement band by the fast/slow
//|     ATR ratio. Tested: train +2146 -> +1780 (PF 1.17->1.14), OOS +326 ->
//|     +339. Net neutral/slightly worse. OFF.
//|   - InpUseDualMode: on a bullish setup with HTF up, ride the trend
//|     (continuation) instead of fading. Tested HARMFUL: train -343 (PF
//|     0.98), OOS +3. OFF.
//|   - Both together: train -326, OOS -191. OFF.
//|   Baseline (all OFF) reproduces v4.86: train +2146 PF1.17, OOS +326 PF1.15.
//|//| v4.6 = v4.5 with direction INVERTED (single-variable test).
//| Evidence: v4.5 lost 12/14 with TP-at-extreme unreachable — entries
//| are systematically on the wrong side, so fade the signal:
//| bullish pullback setup -> SHORT (TP at impulse origin, SL above),
//| bearish pullback setup -> LONG. Zone, reaction (mirrored), profile,
//| touches, session, vol gate, BE/trail, partial — ALL UNCHANGED.
//| InpFadeMode=false restores v4.5 behavior for A/B comparison.
//|
//| v4.61: single 7-17 UTC window replaced by Tokyo/London/NewYork
//| session windows (all ON by default = trade 0-21 UTC).
//|
//| v4.80: parameter defaults set from a walk-forward optimizer run in the
//| mt5 docker container (XAUUSDm M5, Exness-MT5Trial7, 1-min OHLC model).
//| Train 2025.01-2026.07 ($10k): best cluster PF 1.19, DD 12%, 2733 trades.
//| Validated OUT-OF-SAMPLE 2026.07-09: $10k PF 1.14 DD 5%; $100 PF 1.08.
//| Changed defaults: MinImpulseATR 1.2->0.8, MaxImpulseATR 4->5,
//| FadeMinEfficiency 0.65->0.40, EntryFib 0.50/0.66 -> 0.382/0.727,
//| SL_ATR 1.5->1.75, TP_R 1.0->2.0, MinReactionScore 3.0->2.5.
//|
//| v4.81/4.82: daily-budget risk controls for the "$100/day, cap the day at
//| -$100, never lose $100 in one trade" model:
//|   - InpDailyLossMoney  = 100  (absolute $ daily stop, EnforceDailyLossCap
//|     closes open positions the moment the day hits -$100)
//|   - InpMaxRiskMoneyPerTrade = 30 (single trade can never risk more)
//|   - InpFixedLot = 0.02 (constant $ risk/trade; disable risk-% sizing)
//|   - InpMaxConsecutiveLosses 3 -> 10 (daily $ cap governs, not streak)
//| Daily-budget sim ($10k, 18 months, lot 0.02): mean +$5.3/day, 31% of days
//| >= +$20, worst day ~ -$105, max losing streak 6.
//| v4.83 regime-filter experiments (all DEFAULT OFF - they did not help):
//|   - HTF EMA trend filter (InpUseHTFTrendFilter): skip fades against the
//|     H1 EMA slope. Tested harmful: train net +2146 -> +435, OOS +326 ->
//|     +128 (halves trades). The mean-reversion edge lives IN the trades
//|     that fade the higher-timeframe trend, so filtering them kills it.
//|   - Daily direction lock (InpUseDailyDirLock): after N losses in one
//|     side, stop that side for the day. Tested neutral: N=2 train +2046 /
//|     PF 1.19 / DD 3.87%, N=3 +2128 / PF 1.18; OOS +311 / +275 vs +326
//|     baseline. No net gain - the heavy losing days are the cost of the
//|     same behaviour that produces the winners.
//| Conclusion: keep both OFF for max net; they are kept for future study.
//|
//| v4.7 fixes (post-mortem of 05-09 backtests):
//|  1. FADE REGIME GATE: fade only CLEAN (efficient) impulses, i.e. require
//|     efficiency >= InpFadeMinEfficiency (0.65). Jul-2026 A/B showed the
//|     low-efficiency (choppy) fades were the losers and the efficient ones
//|     were the winners, so the choppy band below the floor is skipped.
//|  2. TP GEOMETRY: default TP mode TP_R_MULT. v4.72: InpTP_R 2.0 -> 1.0.
//|     Over Jan-Jun (366 trades) only 12.6% reached the 2R target while 33%
//|     reached 1R and were scratched by BE; a resting 1R TP banks those at
//|     +1R instead of +0.25R. InpMinRR=1.0 matches.
//|  3. EXIT LADDER: BE @1R (+0.25R), trail from 1.5R. With TP=1R the trail
//|     never fires and BE is overtaken by the TP; both are inert by design.
//|  4. RISK / SMALL ACCOUNT: InpMaxLotRiskPercent=10 lets the broker minimum
//|     lot trade (a $100 account is forced to 0.01 lot = 4-9% actual risk on
//|     XAUUSD) but SKIPS the extreme-vol min-lot trades that risked 13-19%
//|     and produced the largest losses. InpDailyLossPercent=15 so one loss
//|     does not stop the day. WarnAccountSize logs the real risk per trade.
//|     Partial stays off below 2x min lot.
//|  5. COMMENT FIT: position comments shortened ("F-SELL PROF=n RISK=x")
//|     so the broker's 31-char limit never truncates RISK; previously 27/49
//|     entries lost it and GetInitialRisk fell back to the live SL.
//| v4.71: fade efficiency gate direction corrected (require eff >= min).
//| Tokyo session default OFF (matches the 7-17 UTC evidence window).
//+------------------------------------------------------------------+
#property strict
#property version "5.00"

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
int      g_htfHandle=INVALID_HANDLE;
int      g_atrH1Handle=INVALID_HANDLE;
datetime g_lastBar=0;
datetime g_day=0;
double   g_dayStartEquity=0.0;
int      g_consecutiveLosses=0;
bool     g_dailyLocked=false;
int      g_dayLossLong=0;    // losing LONG positions closed today
int      g_dayLossShort=0;   // losing SHORT positions closed today

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
// v4.3: remember last 20 impulses (v4.2 remembered only 1).
datetime g_tradedA[];
datetime g_tradedB[];

//====================================================================
// INPUTS
//====================================================================
input group "Core"
input long   InpMagic                 = 20260916;
input ENUM_TIMEFRAMES InpTF           = PERIOD_M5;
input double InpRiskPercent           = 0.50;
input double InpMinRR                 = 1.00;
input int    InpMaxPositions          = 1;
input bool   InpDebug                 = true;
input bool   InpForceMinLot            = true;
input double InpMaxLotRiskPercent     = 10.0;
input double InpMaxRiskMoneyPerTrade  = 30.0;
input double InpFixedLot              = 0.02;
input bool   InpUseMfeLog             = true;
input bool   InpFadeMode              = true;
input bool   InpRandomEntry           = false;
input int    InpRandomEntryBars       = 12;

input group "Sessions (UTC)"
input bool   InpUseTokyo              = false;
input int    InpTokyoStartUTC         = 0;
input int    InpTokyoEndUTC           = 8;
input bool   InpUseLondon             = true;
input int    InpLondonStartUTC        = 7;
input int    InpLondonEndUTC          = 16;
input bool   InpUseNewYork            = true;
input int    InpNewYorkStartUTC       = 12;
input int    InpNewYorkEndUTC         = 21;

input group "Structure"
input int    InpATRPeriod             = 14;
input int    InpLookbackBars          = 150;
input int    InpSwingLeft             = 2;
input int    InpSwingRight            = 2;
input double InpMinImpulseATR         = 0.80;
input double InpMaxImpulseATR         = 5.00;
input double InpTrendEfficiencyMin    = 0.40;
input int    InpMaxImpulseAgeBars     = 30;
input bool   InpRequireBOS            = true;
input bool   InpRequireStructure      = true;

input group "Fade Regime"
input bool   InpUseFadeRegimeGate     = true;
input double InpFadeMinEfficiency     = 0.40;

input group "HTF Trend Filter"
input bool   InpUseHTFTrendFilter     = false;
input ENUM_TIMEFRAMES InpHTF_TF       = PERIOD_H1;
input int    InpHTFEMA_Period         = 50;
input int    InpHTFSlopeBars          = 6;

input group "Daily Direction Lock"
input bool   InpUseDailyDirLock       = false;
input int    InpMaxDirLossesPerDay    = 3;

input group "Adaptive Fibo (v4.90)"
input bool   InpUseATRAdaptiveZone    = false;
input double InpATRZoneShift          = 0.10;
input bool   InpUseDualMode           = false;

input group "Regime Filter (v5.0)"
input bool   InpUseRegimeFilter       = false;
input int    InpRegimeSlopeBars       = 6;
input double InpRegimeStrengthMin     = 0.50;

input group "Volatility Regime (realtime)"
input bool   InpUseVolGate           = true;
input int    InpATRSlowPeriod        = 50;
input double InpMaxVolRatio          = 2.00;
input double InpMinVolRatio          = 0.50;

input group "Fibonacci Profiles (realtime)"
input double InpEntryFibMin           = 0.382;
input double InpEntryFibMax           = 0.727;
input bool   InpUseDeepProfile        = true;
input double InpDeepFibMin            = 0.66;
input double InpDeepFibMax            = 0.786;
input double InpDeepEffBelow          = 0.50;
input double InpDeepVolAbove          = 1.50;
input int    InpDeepTouchMin          = 3;
input int    InpMaxTouches            = 5;
input double InpDeepSL_ATR            = 2.00;

input group "Adaptive Exits (R from entry)"
input double InpSL_ATR                = 1.75;
input ENUM_TP_MODE InpTPMode          = TP_R_MULT;
input double InpTP_R                  = 2.00;

input group "Reaction"
input double InpMinReactionScore      = 2.5;
input double InpMinBodyATR            = 0.25;
input double InpMaxSpreadATR          = 0.15;
input bool   InpRequireReactionClose  = true;

input group "Position Management"
input bool   InpUseBreakEven          = true;
input double InpBreakEvenR            = 1.00;
input double InpBreakEvenOffsetR      = 0.25;
input bool   InpUseTrailing            = true;
input double InpTrailStartR           = 1.50;
input double InpTrailATR              = 1.50;
input bool   InpUsePartial            = true;
input double InpPartialR              = 1.00;
input double InpPartialPct            = 50.0;
input bool   InpUseTimeExit           = true;
input int    InpMaxHoldMinutes        = 180;

input group "Daily Protection"
input double InpDailyLossPercent      = 15.0;
input double InpDailyLossMoney        = 100.0;
input int    InpMaxConsecutiveLosses  = 10;

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

   g_htfHandle=iMA(_Symbol,InpHTF_TF,InpHTFEMA_Period,0,MODE_EMA,PRICE_CLOSE);
   if(g_htfHandle==INVALID_HANDLE)
      Print("WARNING: HTF EMA unavailable, HTF filter fail-open.");

   g_atrH1Handle=iATR(_Symbol,PERIOD_H1,14);
   if(g_atrH1Handle==INVALID_HANDLE)
      Print("WARNING: H1 ATR unavailable, regime filter fail-open.");

   ResetDailyState();
   return(INIT_SUCCEEDED);
   }

void OnDeinit(const int reason)
   {
   if(g_atrHandle!=INVALID_HANDLE)
      IndicatorRelease(g_atrHandle);
   if(g_atrSlowHandle!=INVALID_HANDLE)
      IndicatorRelease(g_atrSlowHandle);
   if(g_htfHandle!=INVALID_HANDLE)
      IndicatorRelease(g_htfHandle);
   if(g_atrH1Handle!=INVALID_HANDLE)
      IndicatorRelease(g_atrH1Handle);
   }

//====================================================================
// MAIN
//====================================================================
void OnTick()
   {
   UpdateDailyState();
   EnforceDailyLossCap();
   ManagePositions();

   if(!IsNewBar())
      return;

   double atr=GetATR(1);
   if(atr<=0.0)
     {
      GateMsg("WAIT: ATR not ready");
      return;
     }

   // v4.7: one-shot risk sanity check so a too-small account is loud, not
   // silently trading 5-9% per position while configured for 0.5%.
   static bool sizeWarned=false;
   if(!sizeWarned)
     {
      sizeWarned=true;
      WarnAccountSize(atr);
     }

   string reason="";
   if(!TradingAllowed(reason)) { GateMsg("BLOCKED Trading: "+reason); return; }
   if(!SessionAllowed())       { GateMsg("BLOCKED Session (all 3 off-hours)"); return; }
   if(!SpreadAllowed(atr))     { GateMsg("BLOCKED Spread (>max ATR ratio)"); return; }
   if(!VolRegimeAllowed())     return;  // self-logging
   if(CountMyPositions()>=InpMaxPositions)
     {
      GateMsg("BLOCKED MaxPositions");
      return;
     }

   double bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
   double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK);

   // v4.84 research benchmark: random entries with identical money
   // management, to test whether the Fibo setup beats a coin flip.
   if(InpRandomEntry)
     {
      static datetime lastRandomBar=0;
      datetime bt=iTime(_Symbol,InpTF,0);
      int every=MathMax(1,InpRandomEntryBars);
      long barIdx=(long)bt/(long)PeriodSeconds(InpTF);
      if((barIdx%(long)every)!=0 || bt==lastRandomBar)
         return;
      lastRandomBar=bt;

      // v4.86: alternate direction by entry counter, not by barIdx parity
      // (barIdx%every==0 made barIdx always even -> always LONG).
      long entryN=barIdx/every;
      bool buy=((entryN%2)==0);

      double rd=InpSL_ATR*atr;
      double e=buy ? ask : bid;
      double sl=buy ? e-rd : e+rd;
      double tp=buy ? e+InpTP_R*rd : e-InpTP_R*rd;
      string rc=buy ? "RND BUY PROF=0" : "RND SELL PROF=0";
      if(buy)
         OpenPosition(ORDER_TYPE_BUY,ask,sl,tp,rc);
      else
         OpenPosition(ORDER_TYPE_SELL,bid,sl,tp,rc);
      return;
     }

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

          double fmin,fmax;
          AdaptiveFibBand(AtrRatio(atr),fmin,fmax);
          double zoneHigh=high-range*fmin;
          double zoneLow =high-range*fmax;

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

          double fmin,fmax;
          AdaptiveFibBand(AtrRatio(atr),fmin,fmax);
          double zoneLow =low+range*fmin;
          double zoneHigh=low+range*fmax;

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
// ADAPTIVE FIB BAND (v4.90)
//
// Option B: shift the retracement band by volatility regime. When the
// fast/slow ATR ratio is above 1 (volatile) we demand a DEEPER retracement
// (zone moves toward the origin), when calm a shallower one.
//   shift = (atrRatio-1) * InpATRZoneShift
//====================================================================
void AdaptiveFibBand(double atrRatio,double &fmin,double &fmax)
  {
   fmin=InpEntryFibMin;
   fmax=InpEntryFibMax;
   if(!InpUseATRAdaptiveZone)
      return;

   double shift=(atrRatio-1.0)*InpATRZoneShift;
   fmin=MathMax(0.0,fmin+shift);
   fmax=MathMin(0.95,fmax+shift);
   if(fmax<fmin+0.05)
      fmax=fmin+0.05;
  }

//====================================================================
// HTF TREND (v4.83)
//
// The heavy losing days were trend days: the EA faded an up impulse
// (short) while the higher timeframe was rising, and each new pullback
// looked the same before continuing. This returns the HTF trend from an
// EMA slope so fades against an established HTF trend can be skipped.
//   +1 = HTF up, -1 = HTF down, 0 = unknown/flat (fail-open)
//====================================================================
int HTFTrendState()
  {
   if(g_htfHandle==INVALID_HANDLE)
      return(0);

   int need=InpHTFSlopeBars+1;
   if(need<2) need=2;

   double e[];
   ArraySetAsSeries(e,true);
   if(CopyBuffer(g_htfHandle,0,0,need,e)!=need)
      return(0);

   double now=e[1];                 // last closed HTF bar
   double then=e[InpHTFSlopeBars];

   if(now>then) return(1);
   if(now<then) return(-1);
   return(0);
  }

//====================================================================
// REGIME STRENGTH (v5.0)
//
// |EMA(HTF) slope over InpRegimeSlopeBars| compared to the H1 ATR.
// Trend is "strong" when the slope >= InpRegimeStrengthMin * ATR(H1).
// The regime filter skips counter-trend fades ONLY when the trend is
// strong (the always-on HTF filter, which skipped every counter-trend
// fade, destroyed the edge in testing).
//====================================================================
bool RegimeTrendStrong()
  {
   if(g_htfHandle==INVALID_HANDLE || g_atrH1Handle==INVALID_HANDLE)
      return(false);

   int need=InpRegimeSlopeBars+1;
   if(need<2) need=2;

   double e[];
   ArraySetAsSeries(e,true);
   if(CopyBuffer(g_htfHandle,0,0,need,e)!=need)
      return(false);

   double a[];
   ArraySetAsSeries(a,true);
   if(CopyBuffer(g_atrH1Handle,0,1,1,a)!=1)
      return(false);

   if(a[0]<=0.0)
      return(false);

   double slope=MathAbs(e[1]-e[InpRegimeSlopeBars]);
   return(slope>=InpRegimeStrengthMin*a[0]);
  }

//====================================================================
// BULLISH SETUP (v4.6: fade executes SHORT here — same zone, mirrored
// reaction/SL/TP; InpFadeMode=false = original LONG)
//====================================================================
void EvaluateBuy(const Impulse &impulse,double atr,double ask,double bid)
   {
   double range=impulse.high-impulse.low;
   if(range<=0.0) return;

   double zfmin,zfmax;
   AdaptiveFibBand(AtrRatio(atr),zfmin,zfmax);
   double zoneHigh=impulse.high-range*zfmin;
   double zoneLow =impulse.high-range*zfmax;

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

   // v4.71: fade only CLEAN (efficient) impulses. Backtest Jul-2026 showed
   // the gated-out low-efficiency trades were the losers; the profitable
   // fades were the efficient ones. So require eff >= floor, skip choppy.
   if(InpFadeMode && InpUseFadeRegimeGate && eff<InpFadeMinEfficiency)
     {
      if(InpDebug)
         Print("Skip fade (weak/choppy impulse): eff=",DoubleToString(eff,2),
               " < ",DoubleToString(InpFadeMinEfficiency,2));
      return;
     }

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

   // v4.90 dual-mode: on a bullish setup, if the HTF is trending up, ride the
   // trend (continuation LONG) instead of fading it (SHORT).
   bool fade=InpFadeMode;
   if(InpUseDualMode && HTFTrendState()==1)
      fade=false;

   if(!fade)
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
      cm="BUY PROF="+IntegerToString(prof);
      if(OpenPosition(ORDER_TYPE_BUY,ask,sl,tp,cm))
         MarkImpulse(impulse);
     }
   else
     {
      // FADE: short the pullback. v4.7 default is an R-multiple target;
      // the impulse-origin target only applies in TP_AT_EXTREME mode.
       // v4.83: skip shorting into an established HTF up-trend.
       if(InpUseHTFTrendFilter && HTFTrendState()==1)
         {
          if(InpDebug)
             Print("Skip fade: HTF up-trend, no short into it");
          return;
         }
       // v5.0: skip short fade only when the up-trend is STRONG.
       if(InpUseRegimeFilter && HTFTrendState()==1 && RegimeTrendStrong())
         {
          if(InpDebug)
             Print("Skip fade: strong HTF up-trend, no short into it");
          return;
         }
      // v4.83: reactive daily lock - stop shorting after N short losses today.
      if(InpUseDailyDirLock && InpMaxDirLossesPerDay>0 &&
         g_dayLossShort>=InpMaxDirLossesPerDay)
        {
         if(InpDebug)
            Print("Skip short fade: daily short-loss limit (",
                  g_dayLossShort,") reached");
         return;
        }
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
      cm="F-SELL PROF="+IntegerToString(prof);
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

   double zfmin,zfmax;
   AdaptiveFibBand(AtrRatio(atr),zfmin,zfmax);
   double zoneLow =impulse.low+range*zfmin;
   double zoneHigh=impulse.low+range*zfmax;

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

   // v4.71: fade only CLEAN (efficient) impulses (mirror of EvaluateBuy).
   if(InpFadeMode && InpUseFadeRegimeGate && eff<InpFadeMinEfficiency)
     {
      if(InpDebug)
         Print("Skip fade (weak/choppy impulse): eff=",DoubleToString(eff,2),
               " < ",DoubleToString(InpFadeMinEfficiency,2));
      return;
     }

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

   // v4.90 dual-mode: on a bearish setup, if the HTF is trending down, ride
   // the trend (continuation SHORT) instead of fading it (LONG).
   bool fade=InpFadeMode;
   if(InpUseDualMode && HTFTrendState()==-1)
      fade=false;

   if(!fade)
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
      cm="SELL PROF="+IntegerToString(prof);
      if(OpenPosition(ORDER_TYPE_SELL,bid,sl,tp,cm))
         MarkImpulse(impulse);
     }
   else
     {
      // FADE: buy the pullback. v4.7 default is an R-multiple target;
      // the impulse-origin target only applies in TP_AT_EXTREME mode.
       // v4.83: skip buying into an established HTF down-trend.
       if(InpUseHTFTrendFilter && HTFTrendState()==-1)
         {
          if(InpDebug)
             Print("Skip fade: HTF down-trend, no long into it");
          return;
         }
       // v5.0: skip long fade only when the down-trend is STRONG.
       if(InpUseRegimeFilter && HTFTrendState()==-1 && RegimeTrendStrong())
         {
          if(InpDebug)
             Print("Skip fade: strong HTF down-trend, no long into it");
          return;
         }
      // v4.83: reactive daily lock - stop longing after N long losses today.
      if(InpUseDailyDirLock && InpMaxDirLossesPerDay>0 &&
         g_dayLossLong>=InpMaxDirLossesPerDay)
        {
         if(InpDebug)
            Print("Skip long fade: daily long-loss limit (",
                  g_dayLossLong,") reached");
         return;
        }
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
      cm="F-BUY PROF="+IntegerToString(prof);
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
   string orderComment=comment+" RISK="+DoubleToString(risk,2);

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
   double riskMoney=equity*InpRiskPercent/100.0;

   double tickValue=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE);
   double tickSize =SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);

   if(tickValue<=0.0 || tickSize<=0.0)
      return(0.0);

   double moneyPerLot=(stopDistance/tickSize)*tickValue;
   if(moneyPerLot<=0.0)
      return(0.0);

   double calculatedVolume=(InpFixedLot>0.0)
      ? InpFixedLot
      : riskMoney/moneyPerLot;

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

   // v4.81: hard per-trade money risk cap. Enforces "one trade can never
   // lose more than InpMaxRiskMoneyPerTrade" so the daily cap of
   // InpDailyLossMoney is reached only after several trades, never one.
   if(InpMaxRiskMoneyPerTrade>0.0)
     {
      double maxVolByMoney=MathFloor(
         (InpMaxRiskMoneyPerTrade/moneyPerLot)/step)*step;
      if(maxVolByMoney<volume)
        {
         if(maxVolByMoney<minVolume)
           {
            if(InpDebug)
               Print("Rejected: single-trade risk cap. min lot risk=",
                     DoubleToString(minVolume*moneyPerLot,2),
                     " > MaxRiskMoneyPerTrade=",
                     DoubleToString(InpMaxRiskMoneyPerTrade,2));
            return(0.0);
           }
         volume=NormalizeVolume(maxVolByMoney);
         if(InpDebug)
            Print("Lot capped by per-trade risk: lot=",
                  DoubleToString(volume,2)," risk$=",
                  DoubleToString(volume*moneyPerLot,2));
        }
     }

   return(volume);
   }

// v4.7: report the real per-trade risk implied by the broker minimum lot.
// On a small account the min lot alone is 5-9% of equity on XAUUSD, so the
// 0.5% configuration is fiction; surface it instead of losing silently.
void WarnAccountSize(double atr)
  {
   if(!InpDebug || atr<=0.0)
      return;

   double riskDist=InpSL_ATR*atr;
   double equity=AccountInfoDouble(ACCOUNT_EQUITY);
   double minVolume=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   double tickValue=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE);
   double tickSize =SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);

   if(equity<=0.0 || minVolume<=0.0 || tickValue<=0.0 || tickSize<=0.0)
      return;

   double moneyPerLot=(riskDist/tickSize)*tickValue;
   if(moneyPerLot<=0.0)
      return;

   double minLotRiskPct=(minVolume*moneyPerLot)/equity*100.0;

   if(minLotRiskPct>InpMaxLotRiskPercent)
      Print("WARNING: account too small for risk model. Min-lot risk=",
            DoubleToString(minLotRiskPct,2),"% > MaxLotRiskPercent=",
            DoubleToString(InpMaxLotRiskPercent,2),
            "%. Trades will be REJECTED. Raise InpMaxLotRiskPercent or use a",
            " cent/micro account.");
   else if(minLotRiskPct>InpRiskPercent)
      Print("SMALL ACCOUNT: using min lot ",
            DoubleToString(minVolume,2),
            ". Target risk=",DoubleToString(InpRiskPercent,2),
            "%, actual min-lot risk=",DoubleToString(minLotRiskPct,2),
            "% (SL=",DoubleToString(riskDist,2)," price units). Partial-take",
            " needs >= ",DoubleToString(2.0*minVolume,2)," lot so it is OFF.");
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
// v4.81: hard daily money stop. When the day's loss reaches InpDailyLossMoney
// close every EA position and lock out for the rest of the day. Without this
// an OPEN position can overshoot the cap (the pre-entry gate only blocks
// new trades).
void EnforceDailyLossCap()
  {
   if(g_dailyLocked || InpDailyLossMoney<=0.0)
      return;
   if(g_dayStartEquity<=0.0)
      return;

   double equity=AccountInfoDouble(ACCOUNT_EQUITY);
   if((g_dayStartEquity-equity)<InpDailyLossMoney)
      return;

   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0 || !PositionSelectByTicket(ticket))
         continue;
      if(PositionGetString(POSITION_SYMBOL)!=_Symbol)
         continue;
      if((long)PositionGetInteger(POSITION_MAGIC)!=InpMagic)
         continue;
      trade.PositionClose(ticket);
     }

   g_dailyLocked=true;
   if(InpDebug)
      Print("DAILY LOSS CAP hit ($",DoubleToString(InpDailyLossMoney,2),
            "): closed all, locked until next day.");
  }

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

         // v4.7: partial is impossible below 2x min lot. Say so once.
         if(vol<2.0*minVol)
           {
            static bool partialWarned=false;
            if(!partialWarned && InpDebug)
              {
               partialWarned=true;
               Print("NOTE: partial-take disabled: lot ",DoubleToString(vol,2),
                     " < 2x broker min ",DoubleToString(minVol,2),
                     ". Partial needs >= ",DoubleToString(2.0*minVol,2)," lot.");
              }
           }

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
// IMPULSE STATE (v4.3: history of last 20, v4.2 kept only 1)
//====================================================================
bool AlreadyTradedImpulse(const Impulse &impulse)
   {
    int n=ArraySize(g_tradedA);
    for(int i=0;i<n;i++)
       if(impulse.lowTime==g_tradedA[i] && impulse.highTime==g_tradedB[i])
          return(true);
    return(false);
   }

void MarkImpulse(const Impulse &impulse)
   {
    int n=ArraySize(g_tradedA);
    ArrayResize(g_tradedA,n+1);
    ArrayResize(g_tradedB,n+1);
    g_tradedA[n]=impulse.lowTime;
    g_tradedB[n]=impulse.highTime;
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
   MqlDateTime utc;
   TimeToStruct(TimeGMT(),utc);

   int now=utc.hour*60+utc.min;

   if(InpUseTokyo && InWindow(now,InpTokyoStartUTC,InpTokyoEndUTC))
      return(true);
   if(InpUseLondon && InWindow(now,InpLondonStartUTC,InpLondonEndUTC))
      return(true);
   if(InpUseNewYork && InWindow(now,InpNewYorkStartUTC,InpNewYorkEndUTC))
      return(true);

   return(false);
   }

// Handles overnight windows (e.g. 22-6 UTC).
bool InWindow(int nowMin,int startHour,int endHour)
   {
   int start=startHour*60;
   int end=endHour*60;
   if(start<=end)
      return(nowMin>=start && nowMin<end);
   return(nowMin>=start || nowMin<end);
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

   double dailyLoss=
      (g_dayStartEquity-equity)/g_dayStartEquity*100.0;

   // v4.81: absolute daily loss cap (money) takes priority when set.
   if(InpDailyLossMoney>0.0 && (g_dayStartEquity-equity)>=InpDailyLossMoney)
     {
      reason="daily loss limit ($)";
      return(false);
     }

   if(InpDailyLossMoney<=0.0 && dailyLoss>=InpDailyLossPercent)
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
   g_dailyLocked=false;
   g_dayLossLong=0;
   g_dayLossShort=0;
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
     {
      g_consecutiveLosses++;
      // v4.83 daily direction lock: count losses per position side.
      // Closing deal type is opposite the position: BUY closes a SHORT.
      long dtype=(long)HistoryDealGetInteger(trans.deal,DEAL_TYPE);
      if(dtype==DEAL_TYPE_BUY)
         g_dayLossShort++;
      else if(dtype==DEAL_TYPE_SELL)
         g_dayLossLong++;
     }
   else if(profit>0.0)
      g_consecutiveLosses=0;

   // v4.5 MFE/MAE diagnostic, v4.84: only log once the position is FULLY
   // closed (a partial close keeps the ticket open), so MFE/MAE cover the
   // whole life instead of stopping at the first partial.
   if(InpUseMfeLog)
     {
      ulong posId=(ulong)HistoryDealGetInteger(trans.deal,DEAL_POSITION_ID);
      if(posId==g_mfeTicket && !PositionSelectByTicket(posId))
        {
         if(g_mfeProf>=0)
            Print("MFELOG PROF=",g_mfeProf,
                  " MFE_R=",DoubleToString(g_mfeR,2),
                  " MAE_R=",DoubleToString(g_maeR,2),
                  " P/L=",DoubleToString(profit,2));
         g_mfeTicket=0;
         g_mfeProf=-1;
        }
     }
   }

//+------------------------------------------------------------------+
