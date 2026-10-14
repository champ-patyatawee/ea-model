//+------------------------------------------------------------------+
//|                                    BiDirectionalHedgingGrid.mq5  |
//|  Bi-directional Hedging Grid EA                                  |
//|  XAUUSD / RoboForex — Prop-firm risk overlay                     |
//|                                                                  |
//|  Wymagania: rachunek HEDGING (nie netting).                      |
//|  Plik: MetaTrader 5\MQL5\Experts\                                |
//+------------------------------------------------------------------+
#property copyright "Bi-directional Hedging Grid EA"
#property link      "https://github.com/Yoshinarium/BiDirectionalHedgingGrid"
#property version   "2.20"
#property description "v2.20: hybryda — sztywny TP bazy (pkt); od 2. nogi koszyk BE+USD. BUY/SELL niezaleznie."

//====================================================================
// ENUMS
//====================================================================
enum ENUM_GRID_MODE
  {
   FIXED_POINTS = 0,   // Staly krok w punktach brokera (_Point)
   ATR_MODE     = 1    // Krok = ATR(okres wykresu) * mnoznik
  };

//====================================================================
// INPUTS
//====================================================================
input group "=== General Settings ==="
sinput int               MagicNumberBuy              = 1000;   // Magic Number koszyka BUY
sinput int               MagicNumberSell             = 2000;   // Magic Number koszyka SELL
input  double            BaseLot                     = 0.01;   // Lot pozycji startowej

input group "=== Grid Settings ==="
input  ENUM_GRID_MODE    GridMode                    = FIXED_POINTS; // Tryb odleglosci siatki
input  int               FixedGridPoints             = 100;    // Krok siatki w punktach (gdy FIXED_POINTS)
input  int               AtrPeriod                   = 14;     // Okres ATR (gdy ATR_MODE)
input  double            AtrMultiplier               = 1.5;    // Mnoznik ATR (gdy ATR_MODE)
input  double            LotMultiplier               = 1.3;    // Soft Martingale: lot = ostatni lot * mnoznik

input group "=== Profit Settings ==="
input  int               BaseTakeProfitPoints        = 200;    // TP pojedynczej bazy w punktach (_Point)
input  double            BasketProfitTarget_USD      = 0.5;    // Cel zysku KOSZYKA (od 2. nogi) w walucie depozytu

input group "=== Risk Management - Drawdown ==="
sinput bool              UseDailyDrawdown            = true;   // Wlacz dzienny limit drawdown
sinput double            MaxDailyDrawdownPercent     = 4.5;    // Max DD % od equity z 00:00 czasu serwera

input group "=== Risk Management - Spread & Time ==="
sinput int               MaxSpreadPoints             = 30;     // Max spread w punktach (_Point)
sinput bool              UseMidnightPause            = true;   // Pauza na rollover (brak NOWYCH zlecen)
sinput string            PauseStartTime              = "23:55"; // Poczatek pauzy (HH:MM)
sinput string            PauseEndTime                = "00:15"; // Koniec pauzy (HH:MM)

input group "=== Risk Management - Weekend ==="
sinput bool              CloseBeforeWeekend          = true;   // Zamknij wszystko w piatek i uspij do poniedzialku
sinput string            FridayCloseTime             = "22:00"; // Godzina zamkniecia w piatek (HH:MM)

//====================================================================
// STALE WEWNETRZNE
//====================================================================
#define EA_TAG              "HG"
#define RETRY_COOLDOWN_SEC  2
#define COMMENT_BASE_BUY    "HG-BUY-BASE"
#define COMMENT_GRID_BUY    "HG-BUY-GRID"
#define COMMENT_BASE_SELL   "HG-SELL-BASE"
#define COMMENT_GRID_SELL   "HG-SELL-GRID"
#define LINE_BASKET_BE_BUY  "HG_BasketBE_BUY"
#define LINE_BASKET_BE_SELL "HG_BasketBE_SELL"
#define LINE_BASE_TP_BUY    "HG_BaseTP_BUY"
#define LINE_BASE_TP_SELL   "HG_BaseTP_SELL"
#define LINE_BASKET_TP_BUY  "HG_BasketTP_BUY"
#define LINE_BASKET_TP_SELL "HG_BasketTP_SELL"

//====================================================================
// STRUKTURY
//====================================================================
struct BasketState
  {
   int               magic;
   ENUM_POSITION_TYPE posType;
   string            name;
   ulong             lastTicket;     // ticket ostatnio OTWORTEJ pozycji (nie skanowany co tick)
   double            lastLot;
   double            lastOpenPrice;
   int               count;
   double            pnl;
   double            volumeSum;
   double            weightedAvg;    // Break-Even: suma(cena * wolumen) / suma(wolumen)
   double            basketTp;       // cel koszyka (count>=2): BE +/- dystans USD
   double            baseTp;         // TP pojedynczej bazy (count==1)
   bool              restoredThisTick;
  };

//====================================================================
// GLOBALS
//====================================================================
int                  g_atrHandle          = INVALID_HANDLE;
ENUM_ORDER_TYPE_FILLING g_filling         = ORDER_FILLING_IOC;
MqlTick              g_tickCache;

BasketState          g_buy;
BasketState          g_sell;

double               g_startOfDayEquity   = 0.0;
datetime             g_currentDayStart    = 0;
bool                 g_dailyLocked        = false;
bool                 g_weekendSleep       = false;
datetime             g_nextTradeAttempt   = 0;

int                  g_pauseStartMin      = 0;
int                  g_pauseEndMin        = 0;
int                  g_fridayCloseMin     = 0;

double               g_tickSize           = 0.0;
double               g_point              = 0.0;
int                  g_digits             = 0;
int                  g_stopsLevel         = 0;
ulong                g_deviationPoints    = 30;

//====================================================================
// PROTOTYPY
//====================================================================
double GetGridStep();
bool   ParseHhMm(const string hhmm, int &minutesOut);
void   InitBasket(BasketState &b, const int magic, const ENUM_POSITION_TYPE ptype, const string name);
void   RefreshBasketStats(BasketState &b);
void   RestoreLastOpenFromMarket(BasketState &b);
bool   UpdateDayAndRiskFlags();
bool   IsMidnightPause();
bool   IsWeekendBlocked();
bool   IsSpreadOk();
bool   CanOpenNewOrders();
bool   CloseBasket(BasketState &b);
bool   ClosePositionByTicket(const ulong ticket);
bool   CloseAllOurPositions();
bool   DeleteOurPendingOrders();
bool   OpenMarketPosition(const ENUM_ORDER_TYPE type, const double lots,
                          const int magic, const string comment,
                          const bool asBase, ulong &outTicket);
bool   OpenSameSideBase(const BasketState &closedBasket);
bool   ApplyPositionStops(const ulong ticket, const double sl, const double tp);
void   RememberOpened(const int magic, const ulong ticket, const double volume, const double fill);
void   StripBasketStops(const int magic, const ENUM_POSITION_TYPE ptype);
void   EnsureHybridStops();
void   UpsertHLine(const string name, const double price, const color clr,
                   const ENUM_LINE_STYLE style, const int width, const string caption);
void   DeleteHLine(const string name);
void   UpdateBasketVisuals();
void   DeleteBasketVisuals();
double PriceDistanceForUsdProfit(const double volumeLots);
double BaseTakeProfitDistance();
double BaseTakeProfitPrice(const ENUM_ORDER_TYPE type, const double price);
double NormalizeLot(const double lots);
double NormalizePrice(const double price);
double GetPositionFullPnl();
int    TimeToMinutes(const datetime t);
datetime DayStart(const datetime t);
string GvName(const string key);
void   LoadPersistedState();
void   SavePersistedState();
void   UpdateChartComment();
void   ManageBasket(BasketState &b);
void   TryRestoreHedgePair();
void   TryGridExpansion(BasketState &b);
bool   AccountIsHedging();

//====================================================================
// INIT / DEINIT
//====================================================================
int OnInit()
  {
   if(MagicNumberBuy == MagicNumberSell)
     {
      Print(EA_TAG, ": MagicNumberBuy i MagicNumberSell musza byc rozne.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(BaseLot <= 0.0)
     {
      Print(EA_TAG, ": BaseLot musi byc > 0.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(FixedGridPoints <= 0)
     {
      Print(EA_TAG, ": FixedGridPoints musi byc > 0.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(AtrPeriod < 1)
     {
      Print(EA_TAG, ": AtrPeriod musi byc >= 1.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(AtrMultiplier <= 0.0)
     {
      Print(EA_TAG, ": AtrMultiplier musi byc > 0.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(LotMultiplier < 1.0)
     {
      Print(EA_TAG, ": LotMultiplier musi byc >= 1.0.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(BasketProfitTarget_USD <= 0.0)
     {
      Print(EA_TAG, ": BasketProfitTarget_USD musi byc > 0.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(BaseTakeProfitPoints <= 0)
     {
      Print(EA_TAG, ": BaseTakeProfitPoints musi byc > 0.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(MaxDailyDrawdownPercent <= 0.0 || MaxDailyDrawdownPercent >= 100.0)
     {
      Print(EA_TAG, ": MaxDailyDrawdownPercent musi byc w zakresie (0, 100).");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(MaxSpreadPoints < 0)
     {
      Print(EA_TAG, ": MaxSpreadPoints nie moze byc ujemny.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(!ParseHhMm(PauseStartTime, g_pauseStartMin) ||
      !ParseHhMm(PauseEndTime, g_pauseEndMin) ||
      !ParseHhMm(FridayCloseTime, g_fridayCloseMin))
     {
      Print(EA_TAG, ": Niepoprawny format czasu. Uzyj HH:MM, np. 23:55.");
      return(INIT_PARAMETERS_INCORRECT);
     }

   if(!AccountIsHedging())
     {
      Print(EA_TAG, ": Wymagany rachunek HEDGING. Netting nie utrzyma jednoczesnego Buy i Sell.");
      return(INIT_FAILED);
     }

   g_point    = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   g_tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   g_digits   = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   g_stopsLevel = (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   if(g_point <= 0.0)
      g_point = _Point;
   if(g_tickSize <= 0.0)
      g_tickSize = g_point;

   const double volMin  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   const double volStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   const double volMax  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   const double normBase = NormalizeLot(BaseLot);
   if(normBase < volMin - 1e-8)
     {
      PrintFormat("%s: BaseLot=%.4f jest ponizej SYMBOL_VOLUME_MIN=%.4f", EA_TAG, BaseLot, volMin);
      return(INIT_PARAMETERS_INCORRECT);
     }

   // Filling: RoboForex / XAUUSD czesto IOC lub FOK
   const uint filling = (uint)SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
   if((filling & SYMBOL_FILLING_IOC) == SYMBOL_FILLING_IOC)
      g_filling = ORDER_FILLING_IOC;
   else if((filling & SYMBOL_FILLING_FOK) == SYMBOL_FILLING_FOK)
      g_filling = ORDER_FILLING_FOK;
   else
      g_filling = ORDER_FILLING_RETURN;

   g_deviationPoints = (ulong)MathMax(30, MaxSpreadPoints);

   g_atrHandle = iATR(_Symbol, PERIOD_CURRENT, AtrPeriod);
   if(g_atrHandle == INVALID_HANDLE)
     {
      Print(EA_TAG, ": Nie udalo sie utworzyc uchwytu ATR. GetLastError=", GetLastError());
      return(INIT_FAILED);
     }

   InitBasket(g_buy,  MagicNumberBuy,  POSITION_TYPE_BUY,  "BUY");
   InitBasket(g_sell, MagicNumberSell, POSITION_TYPE_SELL, "SELL");
   RestoreLastOpenFromMarket(g_buy);
   RestoreLastOpenFromMarket(g_sell);
   EnsureHybridStops();   // baza: zostaw/uzupelnij TP; koszyk (n>=2): zeruj TP/SL

   LoadPersistedState();

   const datetime now = TimeCurrent();
   const datetime today = DayStart(now);
   if(g_currentDayStart != today || g_startOfDayEquity <= 0.0)
     {
      g_currentDayStart  = today;
      g_startOfDayEquity = AccountInfoDouble(ACCOUNT_EQUITY);
      g_dailyLocked      = false;
      SavePersistedState();
     }

   PrintFormat("%s: init %s | point=%.8f tick=%.8f digits=%d stops=%d filling=%d volMin=%.4f step=%.4f max=%.4f | SOD equity=%.2f",
               EA_TAG, _Symbol, g_point, g_tickSize, g_digits, g_stopsLevel, g_filling,
               volMin, volStep, volMax, g_startOfDayEquity);

   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason)
  {
   if(g_atrHandle != INVALID_HANDLE)
     {
      IndicatorRelease(g_atrHandle);
      g_atrHandle = INVALID_HANDLE;
     }
   DeleteBasketVisuals();
   Comment("");
   Print(EA_TAG, ": deinit reason=", reason);
  }

//====================================================================
// TICK
//====================================================================
void OnTick()
  {
   if(!UpdateDayAndRiskFlags())
      return;

   RefreshBasketStats(g_buy);
   RefreshBasketStats(g_sell);
   g_buy.restoredThisTick  = false;
   g_sell.restoredThisTick = false;

   // 1) Weekend / Daily DD — twarde zamkniecie, zero nowych zlecen
   if(g_dailyLocked || g_weekendSleep)
     {
      if(g_buy.count > 0 || g_sell.count > 0)
        {
         CloseAllOurPositions();
         DeleteOurPendingOrders();
         RefreshBasketStats(g_buy);
         RefreshBasketStats(g_sell);
        }
      UpdateBasketVisuals();
      UpdateChartComment();
      return;
     }

   // 2) Koszyk (count>=2) zamykany na BE+USD — takze w Midnight Pause.
   //    Pojedyncza baza (count==1) zamyka sie na sztywnym TP brokera.
   ManageBasket(g_buy);
   ManageBasket(g_sell);

   RefreshBasketStats(g_buy);
   RefreshBasketStats(g_sell);

   // 3) Nowe zlecenia tylko poza pauza, przy dobrym spreadzie
   TryRestoreHedgePair();
   TryGridExpansion(g_buy);
   TryGridExpansion(g_sell);

   RefreshBasketStats(g_buy);
   RefreshBasketStats(g_sell);
   UpdateBasketVisuals();
   UpdateChartComment();
  }

//====================================================================
// GET GRID STEP — dystans w formacie cenowym
//====================================================================
double GetGridStep()
  {
   double step = 0.0;

   if(GridMode == FIXED_POINTS)
     {
      // XAUUSD: _Point to najmniejsza zmiana ceny w notowaniu (np. 0.01 albo 0.001),
      // NIE mylic z tick size (SYMBOL_TRADE_TICK_SIZE), ktory bywa wiekszy.
      step = (double)FixedGridPoints * _Point;
     }
   else
     {
      double atr[];
      ArraySetAsSeries(atr, true);
      if(CopyBuffer(g_atrHandle, 0, 0, 1, atr) < 1 || atr[0] <= 0.0)
        {
         // Fallback gdy ATR jeszcze nie gotowy (start testera / brak historii)
         step = (double)FixedGridPoints * _Point;
        }
      else
         step = atr[0] * AtrMultiplier;
     }

   // TP/SL musza spelniac stops level oraz siatke ticka kontraktu na zloto
   const double minStops = (g_stopsLevel > 0 ? g_stopsLevel * _Point : 0.0);
   if(step < minStops)
      step = minStops;
   if(step < g_tickSize)
      step = g_tickSize;

   return(step);
  }

//====================================================================
// ZARZADZANIE KOSZYKIEM
//====================================================================
void ManageBasket(BasketState &b)
  {
   // Hybryda: pojedyncza baza ma sztywny TP brokera — nie zamykamy jej tu.
   if(b.count < 2)
      return;

   if(!SymbolInfoTick(_Symbol, g_tickCache))
      return;

   const bool hitUsdTarget = (b.pnl >= BasketProfitTarget_USD);

   bool hitBasketTp = false;
   if(b.basketTp > 0.0)
     {
      if(b.posType == POSITION_TYPE_BUY)
         hitBasketTp = (g_tickCache.bid >= b.basketTp);
      else
         hitBasketTp = (g_tickCache.ask <= b.basketTp);
     }

   if(!hitUsdTarget && !hitBasketTp)
      return;

   PrintFormat("%s: %s BASKET CLOSE (n=%d) | BE=%s exit=%s pnl=%.2f target=%.2f reason=%s",
               EA_TAG, b.name, b.count,
               DoubleToString(b.weightedAvg, g_digits),
               DoubleToString(b.basketTp, g_digits),
               b.pnl,
               BasketProfitTarget_USD,
               (hitUsdTarget ? "UsdPnL" : "PriceBE"));

   if(!CloseBasket(b))
     {
      PrintFormat("%s: %s — nie udalo sie zamknac calego koszyka, sprobe ponownie na nastepnym ticku",
                  EA_TAG, b.name);
      return;
     }

   RefreshBasketStats(b);

   // Powrot do bazy ze sztywnym TP
   if(CanOpenNewOrders())
     {
      if(OpenSameSideBase(b))
        {
         if(b.posType == POSITION_TYPE_BUY)
            g_buy.restoredThisTick = true;
         else
            g_sell.restoredThisTick = true;
        }
     }
  }

void TryRestoreHedgePair()
  {
   if(!CanOpenNewOrders())
      return;

   // Kazda strona niezaleznie — pusta noga nie blokuje drugiej
   if(g_buy.count == 0 && !g_buy.restoredThisTick)
     {
      ulong ticket = 0;
      if(OpenMarketPosition(ORDER_TYPE_BUY, BaseLot, MagicNumberBuy, COMMENT_BASE_BUY, true, ticket))
        {
         g_buy.restoredThisTick = true;
         PrintFormat("%s: restore BUY baza ticket=%I64u", EA_TAG, ticket);
        }
     }
   if(g_sell.count == 0 && !g_sell.restoredThisTick)
     {
      ulong ticket = 0;
      if(OpenMarketPosition(ORDER_TYPE_SELL, BaseLot, MagicNumberSell, COMMENT_BASE_SELL, true, ticket))
        {
         g_sell.restoredThisTick = true;
         PrintFormat("%s: restore SELL baza ticket=%I64u", EA_TAG, ticket);
        }
     }
  }

void TryGridExpansion(BasketState &b)
  {
   if(!CanOpenNewOrders())
      return;
   if(b.count <= 0 || b.lastOpenPrice <= 0.0 || b.lastLot <= 0.0)
      return;
   // Nie usredniaj od zamknietej pozycji — najnowsza wlasnie zeszla TP i czeka na nowa baze
   if(b.lastTicket > 0 && !PositionSelectByTicket(b.lastTicket))
      return;
   if(TimeCurrent() < g_nextTradeAttempt)
      return;

   if(!SymbolInfoTick(_Symbol, g_tickCache))
      return;

   const double step = GetGridStep();
   bool shouldAdd = false;

   if(b.posType == POSITION_TYPE_BUY)
     {
      // Niekorzystny ruch w dol — mierzony cena, po ktorej realnie otworzymy kolejnego BUY (Ask)
      shouldAdd = (g_tickCache.ask <= b.lastOpenPrice - step);
     }
   else
     {
      // Niekorzystny ruch w gore — Bid, po ktorym otworzymy kolejnego SELL
      shouldAdd = (g_tickCache.bid >= b.lastOpenPrice + step);
     }

   if(!shouldAdd)
      return;

   double nextLot = NormalizeLot(b.lastLot * LotMultiplier);
   const double volStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   // Soft martingale musi realnie rosnac mimo grubego VOLUME_STEP na zlocie (czesto 0.01)
   if(nextLot <= b.lastLot + 1e-8 && volStep > 0.0)
      nextLot = NormalizeLot(b.lastLot + volStep);

   ulong ticket = 0;
   const ENUM_ORDER_TYPE otype = (b.posType == POSITION_TYPE_BUY ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
   const string comment = (b.posType == POSITION_TYPE_BUY ? COMMENT_GRID_BUY : COMMENT_GRID_SELL);

   if(OpenMarketPosition(otype, nextLot, b.magic, comment, false, ticket))
     {
      StripBasketStops(b.magic, b.posType);
      PrintFormat("%s: %s GRID lot=%.4f (poprzedni=%.4f) ticket=%I64u step=%.5f — koszyk, TP/SL zdjete",
                  EA_TAG, b.name, nextLot, b.lastLot, ticket, step);
     }
  }

//====================================================================
// RYZYKO / CZAS
//====================================================================
bool UpdateDayAndRiskFlags()
  {
   const datetime now = TimeCurrent();
   const datetime today = DayStart(now);

   // Nowy dzien serwera: nowy punkt odniesienia equity, zdjecie blokady DD
   if(today != g_currentDayStart)
     {
      g_currentDayStart  = today;
      g_startOfDayEquity = AccountInfoDouble(ACCOUNT_EQUITY);
      g_dailyLocked      = false;
      SavePersistedState();
      PrintFormat("%s: nowy dzien serwera, StartOfDayEquity=%.2f", EA_TAG, g_startOfDayEquity);
     }

   MqlDateTime dt;
   TimeToStruct(now, dt);

   // Weekend: piatek od FridayCloseTime, cala sobota i niedziela
   if(CloseBeforeWeekend)
     {
      const int nowMin = dt.hour * 60 + dt.min;
      const bool fridayClose = (dt.day_of_week == 5 && nowMin >= g_fridayCloseMin);
      const bool satSun      = (dt.day_of_week == 6 || dt.day_of_week == 0);

      if(fridayClose || satSun)
        {
         if(!g_weekendSleep)
           {
            g_weekendSleep = true;
            SavePersistedState();
            PrintFormat("%s: WEEKEND CLOSE — usypiam handel do poniedzialku (sesja).", EA_TAG);
           }
        }
      else if(dt.day_of_week >= 1 && dt.day_of_week <= 5)
        {
         if(g_weekendSleep)
           {
            g_weekendSleep = false;
            SavePersistedState();
            PrintFormat("%s: WEEKEND SLEEP OFF — start sesji poniedzialkowej.", EA_TAG);
           }
        }
     }
   else
      g_weekendSleep = false;

   if(UseDailyDrawdown && !g_dailyLocked && g_startOfDayEquity > 0.0)
     {
      const double equity = AccountInfoDouble(ACCOUNT_EQUITY);
      const double ddPct  = ((g_startOfDayEquity - equity) / g_startOfDayEquity) * 100.0;
      if(ddPct >= MaxDailyDrawdownPercent)
        {
         g_dailyLocked = true;
         SavePersistedState();
         PrintFormat("%s: DAILY DD LOCK %.2f%% >= %.2f%% (SOD equity=%.2f current=%.2f). Handel zablokowany do 00:00.",
                     EA_TAG, ddPct, MaxDailyDrawdownPercent, g_startOfDayEquity, equity);
         CloseAllOurPositions();
         DeleteOurPendingOrders();
        }
     }

   return(true);
  }

bool IsMidnightPause()
  {
   if(!UseMidnightPause)
      return(false);

   const int nowMin = TimeToMinutes(TimeCurrent());
   // Zakres moze przekraczac polnoc (23:55 -> 00:15)
   if(g_pauseStartMin <= g_pauseEndMin)
      return(nowMin >= g_pauseStartMin && nowMin < g_pauseEndMin);
   return(nowMin >= g_pauseStartMin || nowMin < g_pauseEndMin);
  }

bool IsWeekendBlocked()
  {
   return(CloseBeforeWeekend && g_weekendSleep);
  }

bool IsSpreadOk()
  {
   if(!SymbolInfoTick(_Symbol, g_tickCache))
      return(false);
   if(g_tickCache.ask <= 0.0 || g_tickCache.bid <= 0.0)
      return(false);

   const double spreadPoints = (g_tickCache.ask - g_tickCache.bid) / _Point;
   return(spreadPoints <= (double)MaxSpreadPoints + 1e-8);
  }

bool CanOpenNewOrders()
  {
   if(g_dailyLocked || IsWeekendBlocked() || IsMidnightPause())
      return(false);
   if(TimeCurrent() < g_nextTradeAttempt)
      return(false);
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED))
      return(false);
   if(SymbolInfoInteger(_Symbol, SYMBOL_TRADE_MODE) == SYMBOL_TRADE_MODE_DISABLED)
      return(false);
   if(!IsSpreadOk())
      return(false);
   return(true);
  }

//====================================================================
// ZLECENIA — OrderSend + obsluga bledow
//====================================================================
bool OpenMarketPosition(const ENUM_ORDER_TYPE type, const double lots,
                        const int magic, const string comment,
                        const bool asBase, ulong &outTicket)
  {
   outTicket = 0;
   if(TimeCurrent() < g_nextTradeAttempt)
      return(false);

   // Twardy rozdzial magikow: BUY tylko MagicNumberBuy, SELL tylko MagicNumberSell
   if(type == ORDER_TYPE_BUY && magic != MagicNumberBuy)
     {
      PrintFormat("%s: odrzucono BUY z magic=%d (oczekiwano %d)", EA_TAG, magic, MagicNumberBuy);
      return(false);
     }
   if(type == ORDER_TYPE_SELL && magic != MagicNumberSell)
     {
      PrintFormat("%s: odrzucono SELL z magic=%d (oczekiwano %d)", EA_TAG, magic, MagicNumberSell);
      return(false);
     }

   const double volume = NormalizeLot(lots);
   if(volume <= 0.0)
     {
      PrintFormat("%s: OpenMarketPosition — niepoprawny lot po normalizacji (in=%.4f)", EA_TAG, lots);
      return(false);
     }

   if(!SymbolInfoTick(_Symbol, g_tickCache))
     {
      Print(EA_TAG, ": brak ticka, GetLastError=", GetLastError());
      g_nextTradeAttempt = TimeCurrent() + RETRY_COOLDOWN_SEC;
      return(false);
     }

   const double price = (type == ORDER_TYPE_BUY ? g_tickCache.ask : g_tickCache.bid);
   const double tp    = (asBase ? BaseTakeProfitPrice(type, price) : 0.0);

   MqlTradeRequest request = {};
   MqlTradeResult  result  = {};
   request.action       = TRADE_ACTION_DEAL;
   request.symbol       = _Symbol;
   request.volume       = volume;
   request.type         = type;
   request.price        = NormalizePrice(price);
   request.sl           = 0.0;
   request.tp           = tp;           // baza: sztywny TP; siatka: 0 — zarzadza koszyk
   request.deviation    = g_deviationPoints;
   request.magic        = (ulong)magic;
   request.comment      = comment;
   request.type_filling = g_filling;
   request.type_time    = ORDER_TIME_GTC;

   ResetLastError();
   const bool ok = OrderSend(request, result);
   if(!ok || (result.retcode != TRADE_RETCODE_DONE &&
              result.retcode != TRADE_RETCODE_DONE_PARTIAL &&
              result.retcode != TRADE_RETCODE_PLACED))
     {
      PrintFormat("%s: OrderSend FAIL type=%s lot=%.4f price=%s retcode=%u comment=%s lastError=%d",
                  EA_TAG,
                  (type == ORDER_TYPE_BUY ? "BUY" : "SELL"),
                  volume,
                  DoubleToString(request.price, g_digits),
                  result.retcode,
                  result.comment,
                  GetLastError());
      g_nextTradeAttempt = TimeCurrent() + RETRY_COOLDOWN_SEC;
      return(false);
     }

   ulong posTicket = 0;
   if(result.deal > 0 && HistoryDealSelect(result.deal))
      posTicket = (ulong)HistoryDealGetInteger(result.deal, DEAL_POSITION_ID);
   if(posTicket == 0)
      posTicket = result.order;

   outTicket = posTicket;

   double fillPrice = result.price;
   if(fillPrice <= 0.0 && posTicket > 0 && PositionSelectByTicket(posTicket))
      fillPrice = PositionGetDouble(POSITION_PRICE_OPEN);

   RememberOpened(magic, posTicket, volume, (fillPrice > 0.0 ? fillPrice : price));

   // Po slizgu na zlocie doprecyzuj TP bazy wzgledem fill, nie kwotacji sprzed send
   if(asBase && posTicket > 0 && fillPrice > 0.0)
      ApplyPositionStops(posTicket, 0.0, BaseTakeProfitPrice(type, fillPrice));

   PrintFormat("%s: OrderSend OK %s lot=%.4f fill=%s tp=%s ticket=%I64u asBase=%s retcode=%u",
               EA_TAG,
               (type == ORDER_TYPE_BUY ? "BUY" : "SELL"),
               volume,
               DoubleToString(fillPrice, g_digits),
               DoubleToString(tp, g_digits),
               posTicket,
               (asBase ? "true" : "false"),
               result.retcode);
   return(true);
  }

bool ApplyPositionStops(const ulong ticket, const double sl, const double tp)
  {
   if(ticket == 0 || !PositionSelectByTicket(ticket))
      return(false);

   const double curSl = PositionGetDouble(POSITION_SL);
   const double curTp = PositionGetDouble(POSITION_TP);
   const double nSl   = NormalizePrice(sl);
   const double nTp   = NormalizePrice(tp);
   if(MathAbs(curSl - nSl) < g_tickSize * 0.5 && MathAbs(curTp - nTp) < g_tickSize * 0.5)
      return(true);

   MqlTradeRequest request = {};
   MqlTradeResult  result  = {};
   request.action   = TRADE_ACTION_SLTP;
   request.position = ticket;
   request.symbol   = _Symbol;
   request.sl       = nSl;
   request.tp       = nTp;
   request.magic    = (ulong)PositionGetInteger(POSITION_MAGIC);

   ResetLastError();
   if(!OrderSend(request, result) ||
      (result.retcode != TRADE_RETCODE_DONE && result.retcode != TRADE_RETCODE_PLACED))
     {
      PrintFormat("%s: ApplyPositionStops FAIL ticket=%I64u sl=%s tp=%s retcode=%u %s",
                  EA_TAG, ticket,
                  DoubleToString(nSl, g_digits), DoubleToString(nTp, g_digits),
                  result.retcode, result.comment);
      return(false);
     }
   return(true);
  }

bool OpenSameSideBase(const BasketState &closedBasket)
  {
   ulong ticket = 0;
   bool  ok     = false;

   if(closedBasket.posType == POSITION_TYPE_BUY)
     {
      ok = OpenMarketPosition(ORDER_TYPE_BUY, BaseLot, MagicNumberBuy, COMMENT_BASE_BUY, true, ticket);
      if(ok)
         PrintFormat("%s: po zamknieciu koszyka BUY — nowa baza BUY ticket=%I64u", EA_TAG, ticket);
     }
   else
     {
      ok = OpenMarketPosition(ORDER_TYPE_SELL, BaseLot, MagicNumberSell, COMMENT_BASE_SELL, true, ticket);
      if(ok)
         PrintFormat("%s: po zamknieciu koszyka SELL — nowa baza SELL ticket=%I64u", EA_TAG, ticket);
     }

   return(ok);
  }

bool CloseBasket(BasketState &b)
  {
   bool allClosed = true;

   // Zamykanie OD KONCA — indeksy PositionsTotal nie rozjezdzaja sie podczas usuwania
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      const ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)
         continue;
      if((int)PositionGetInteger(POSITION_MAGIC) != b.magic)
         continue;
      if((ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) != b.posType)
         continue;

      if(!ClosePositionByTicket(ticket))
         allClosed = false;
     }

   b.lastTicket    = 0;
   b.lastLot       = 0.0;
   b.lastOpenPrice = 0.0;
   b.weightedAvg   = 0.0;
   b.basketTp      = 0.0;
   b.baseTp        = 0.0;
   b.count         = 0;
   b.pnl           = 0.0;
   b.volumeSum     = 0.0;
   return(allClosed);
  }

bool ClosePositionByTicket(const ulong ticket)
  {
   if(!PositionSelectByTicket(ticket))
      return(true);

   const ENUM_POSITION_TYPE ptype = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
   const double volume = PositionGetDouble(POSITION_VOLUME);
   const int    magic  = (int)PositionGetInteger(POSITION_MAGIC);

   if(!SymbolInfoTick(_Symbol, g_tickCache))
      return(false);

   MqlTradeRequest request = {};
   MqlTradeResult  result  = {};
   request.action       = TRADE_ACTION_DEAL;
   request.position     = ticket;
   request.symbol       = _Symbol;
   request.volume       = volume;
   request.deviation    = g_deviationPoints;
   request.magic        = (ulong)magic;
   request.type_filling = g_filling;
   request.type_time    = ORDER_TIME_GTC;
   request.comment      = "HG-CLOSE";

   if(ptype == POSITION_TYPE_BUY)
     {
      request.type  = ORDER_TYPE_SELL;
      request.price = NormalizePrice(g_tickCache.bid);
     }
   else
     {
      request.type  = ORDER_TYPE_BUY;
      request.price = NormalizePrice(g_tickCache.ask);
     }

   ResetLastError();
   if(!OrderSend(request, result) ||
      (result.retcode != TRADE_RETCODE_DONE &&
       result.retcode != TRADE_RETCODE_DONE_PARTIAL &&
       result.retcode != TRADE_RETCODE_PLACED))
     {
      PrintFormat("%s: CLOSE FAIL ticket=%I64u retcode=%u %s err=%d",
                  EA_TAG, ticket, result.retcode, result.comment, GetLastError());
      g_nextTradeAttempt = TimeCurrent() + RETRY_COOLDOWN_SEC;
      return(false);
     }
   return(true);
  }

bool CloseAllOurPositions()
  {
   bool ok = true;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      const ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)
         continue;
      const int magic = (int)PositionGetInteger(POSITION_MAGIC);
      if(magic != MagicNumberBuy && magic != MagicNumberSell)
         continue;
      if(!ClosePositionByTicket(ticket))
         ok = false;
     }
   g_buy.lastTicket = g_sell.lastTicket = 0;
   g_buy.lastLot = g_sell.lastLot = 0.0;
   g_buy.lastOpenPrice = g_sell.lastOpenPrice = 0.0;
   g_buy.weightedAvg = g_sell.weightedAvg = 0.0;
   g_buy.basketTp = g_sell.basketTp = 0.0;
   g_buy.baseTp = g_sell.baseTp = 0.0;
   return(ok);
  }

bool DeleteOurPendingOrders()
  {
   bool ok = true;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      const ulong ticket = OrderGetTicket(i);
      if(ticket == 0)
         continue;
      if(OrderGetString(ORDER_SYMBOL) != _Symbol)
         continue;
      const int magic = (int)OrderGetInteger(ORDER_MAGIC);
      if(magic != MagicNumberBuy && magic != MagicNumberSell)
         continue;

      MqlTradeRequest request = {};
      MqlTradeResult  result  = {};
      request.action = TRADE_ACTION_REMOVE;
      request.order  = ticket;
      request.magic  = (ulong)magic;

      ResetLastError();
      if(!OrderSend(request, result) ||
         (result.retcode != TRADE_RETCODE_DONE && result.retcode != TRADE_RETCODE_PLACED))
        {
         PrintFormat("%s: DELETE PENDING FAIL ticket=%I64u retcode=%u %s",
                     EA_TAG, ticket, result.retcode, result.comment);
         ok = false;
        }
     }
   return(ok);
  }

//====================================================================
// POMOCNICZE — specyfikacja kontraktu XAUUSD
//====================================================================
double NormalizeLot(const double lots)
  {
   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(minLot <= 0.0)
      minLot = 0.01;
   if(step <= 0.0)
      step = 0.01;

   double v = MathFloor((lots / step) + 1e-8) * step;
   v = NormalizeDouble(v, 8);
   if(v < minLot)
      v = minLot;
   if(v > maxLot)
      v = maxLot;
   return(v);
  }

double NormalizePrice(const double price)
  {
   double tick = g_tickSize;
   if(tick <= 0.0)
      tick = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tick <= 0.0)
      tick = _Point;

   const double aligned = MathRound(price / tick) * tick;
   return(NormalizeDouble(aligned, g_digits > 0 ? g_digits : _Digits));
  }

double BaseTakeProfitDistance()
  {
   double dist = (double)BaseTakeProfitPoints * _Point;
   const double minStops = (g_stopsLevel > 0 ? g_stopsLevel * _Point : 0.0);
   if(dist < minStops)
      dist = minStops;
   if(dist < g_tickSize)
      dist = g_tickSize;
   return(dist);
  }

double BaseTakeProfitPrice(const ENUM_ORDER_TYPE type, const double price)
  {
   const double dist = BaseTakeProfitDistance();
   if(type == ORDER_TYPE_BUY)
      return(NormalizePrice(price + dist));
   return(NormalizePrice(price - dist));
  }

// Przelicza cel USD na dystans ceny dla danego wolumenu koszyka (XAUUSD: tick != point).
double PriceDistanceForUsdProfit(const double volumeLots)
  {
   if(volumeLots <= 0.0 || BasketProfitTarget_USD <= 0.0)
      return(0.0);

   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   if(tickSize <= 0.0)
      tickSize = _Point;
   if(tickValue <= 0.0)
      return(0.0);

   // Wartosc ruchu ceny o 1.0 dla 1 lota = tickValue / tickSize
   // delta = Target / (volume * wartosc_1.0) = Target * tickSize / (volume * tickValue)
   return(BasketProfitTarget_USD * tickSize / (volumeLots * tickValue));
  }

double GetPositionFullPnl()
  {
   // Profit (w walucie depozytu) + swap + prowizja — broker liczy tick value dla zlota
   double pnl = PositionGetDouble(POSITION_PROFIT);
   pnl += PositionGetDouble(POSITION_SWAP);
   pnl += PositionGetDouble(POSITION_COMMISSION);
   return(pnl);
  }

void RememberOpened(const int magic, const ulong ticket, const double volume, const double fill)
  {
   if(magic == MagicNumberBuy)
     {
      g_buy.lastTicket    = ticket;
      g_buy.lastLot       = volume;
      g_buy.lastOpenPrice = fill;
     }
   else if(magic == MagicNumberSell)
     {
      g_sell.lastTicket    = ticket;
      g_sell.lastLot       = volume;
      g_sell.lastOpenPrice = fill;
     }
  }

void InitBasket(BasketState &b, const int magic, const ENUM_POSITION_TYPE ptype, const string name)
  {
   b.magic         = magic;
   b.posType       = ptype;
   b.name          = name;
   b.lastTicket    = 0;
   b.lastLot       = 0.0;
   b.lastOpenPrice = 0.0;
   b.count         = 0;
   b.pnl           = 0.0;
   b.volumeSum     = 0.0;
   b.weightedAvg       = 0.0;
   b.basketTp          = 0.0;
   b.baseTp            = 0.0;
   b.restoredThisTick  = false;
  }

void RefreshBasketStats(BasketState &b)
  {
   b.count       = 0;
   b.pnl         = 0.0;
   b.volumeSum   = 0.0;
   b.weightedAvg = 0.0;
   b.basketTp    = 0.0;
   b.baseTp      = 0.0;

   double priceVolume = 0.0;
   double lastBaseTp  = 0.0;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      const ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)
         continue;
      if((int)PositionGetInteger(POSITION_MAGIC) != b.magic)
         continue;
      if((ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) != b.posType)
         continue;

      const double vol   = PositionGetDouble(POSITION_VOLUME);
      const double open  = PositionGetDouble(POSITION_PRICE_OPEN);

      b.count++;
      b.volumeSum  += vol;
      priceVolume  += open * vol;
      b.pnl        += GetPositionFullPnl();
      lastBaseTp    = PositionGetDouble(POSITION_TP);
     }

   if(b.count > 0 && b.volumeSum > 0.0)
     {
      b.weightedAvg = priceVolume / b.volumeSum;
      if(b.count == 1)
        {
         b.baseTp = lastBaseTp;
         if(b.baseTp <= 0.0)
           {
            const ENUM_ORDER_TYPE otype = (b.posType == POSITION_TYPE_BUY ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
            b.baseTp = BaseTakeProfitPrice(otype, b.weightedAvg);
           }
         b.basketTp = 0.0;
        }
      else
        {
         const double dist = PriceDistanceForUsdProfit(b.volumeSum);
         if(b.posType == POSITION_TYPE_BUY)
            b.basketTp = NormalizePrice(b.weightedAvg + dist);
         else
            b.basketTp = NormalizePrice(b.weightedAvg - dist);
        }
     }
  }

void RestoreLastOpenFromMarket(BasketState &b)
  {
   datetime newest = 0;
   b.lastTicket    = 0;
   b.lastLot       = 0.0;
   b.lastOpenPrice = 0.0;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      const ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)
         continue;
      if((int)PositionGetInteger(POSITION_MAGIC) != b.magic)
         continue;
      if((ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) != b.posType)
         continue;

      const datetime t = (datetime)PositionGetInteger(POSITION_TIME);
      if(t >= newest)
        {
         newest          = t;
         b.lastTicket    = ticket;
         b.lastLot       = PositionGetDouble(POSITION_VOLUME);
         b.lastOpenPrice = PositionGetDouble(POSITION_PRICE_OPEN);
        }
     }
  }

bool ParseHhMm(const string hhmm, int &minutesOut)
  {
   string parts[];
   const int n = StringSplit(hhmm, ':', parts);
   if(n < 2)
      return(false);
   const int h = (int)StringToInteger(parts[0]);
   const int m = (int)StringToInteger(parts[1]);
   if(h < 0 || h > 23 || m < 0 || m > 59)
      return(false);
   minutesOut = h * 60 + m;
   return(true);
  }

int TimeToMinutes(const datetime t)
  {
   MqlDateTime dt;
   TimeToStruct(t, dt);
   return(dt.hour * 60 + dt.min);
  }

datetime DayStart(const datetime t)
  {
   MqlDateTime dt;
   TimeToStruct(t, dt);
   dt.hour = 0;
   dt.min  = 0;
   dt.sec  = 0;
   return(StructToTime(dt));
  }

bool AccountIsHedging()
  {
   const ENUM_ACCOUNT_MARGIN_MODE mode = (ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE);
   return(mode == ACCOUNT_MARGIN_MODE_RETAIL_HEDGING);
  }

string GvName(const string key)
  {
   return(StringFormat("HG_%s_%d_%s", _Symbol, MagicNumberBuy, key));
  }

void LoadPersistedState()
  {
   const string nEq   = GvName("SOD_EQ");
   const string nDay  = GvName("SOD_DAY");
   const string nLock = GvName("LOCKED");
   const string nWk   = GvName("WEEKEND");

   if(GlobalVariableCheck(nDay))
      g_currentDayStart = (datetime)GlobalVariableGet(nDay);
   if(GlobalVariableCheck(nEq))
      g_startOfDayEquity = GlobalVariableGet(nEq);
   if(GlobalVariableCheck(nLock))
      g_dailyLocked = (GlobalVariableGet(nLock) > 0.5);
   if(GlobalVariableCheck(nWk))
      g_weekendSleep = (GlobalVariableGet(nWk) > 0.5);
  }

void SavePersistedState()
  {
   GlobalVariableSet(GvName("SOD_EQ"),  g_startOfDayEquity);
   GlobalVariableSet(GvName("SOD_DAY"), (double)(long)g_currentDayStart);
   GlobalVariableSet(GvName("LOCKED"),  g_dailyLocked ? 1.0 : 0.0);
   GlobalVariableSet(GvName("WEEKEND"), g_weekendSleep ? 1.0 : 0.0);
  }

void UpdateChartComment()
  {
   const double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double ddPct = 0.0;
   if(g_startOfDayEquity > 0.0)
      ddPct = ((g_startOfDayEquity - equity) / g_startOfDayEquity) * 100.0;

   double spreadPts = 0.0;
   if(g_tickCache.ask > 0.0 && g_tickCache.bid > 0.0)
      spreadPts = (g_tickCache.ask - g_tickCache.bid) / _Point;

   string state = "TRADING";
   if(g_dailyLocked)
      state = "LOCKED (daily DD) — do 00:00";
   else if(g_weekendSleep)
      state = "WEEKEND SLEEP — do poniedzialku";
   else if(IsMidnightPause())
      state = "MIDNIGHT PAUSE (brak nowych zlecen)";
   else if(!IsSpreadOk())
      state = "SPREAD TOO WIDE";

   Comment(
      "Bi-directional Hedging Grid  |  ", _Symbol, "  |  ", EnumToString(_Period), "\n",
      "State: ", state, "\n",
      "GridStep: ", DoubleToString(GetGridStep(), g_digits),
      "   (", (GridMode == FIXED_POINTS ? "FIXED " + IntegerToString(FixedGridPoints) + " pts" : "ATR x " + DoubleToString(AtrMultiplier, 2)), ")\n",
      "Spread: ", DoubleToString(spreadPts, 1), " pts  /  max ", IntegerToString(MaxSpreadPoints),
      "   Point=", DoubleToString(_Point, 8), "  TickSize=", DoubleToString(g_tickSize, 8), "\n",
      "SOD Equity: ", DoubleToString(g_startOfDayEquity, 2),
      "   Equity: ", DoubleToString(equity, 2),
      "   DD: ", DoubleToString(ddPct, 2), "%  /  ", DoubleToString(MaxDailyDrawdownPercent, 2), "%\n",
      "BUY  [magic ", IntegerToString(MagicNumberBuy), "]:  n=", IntegerToString(g_buy.count),
      "  ", (g_buy.count >= 2 ? "BASKET" : "BASE"),
      "  vol=", DoubleToString(g_buy.volumeSum, 2),
      "  BE=", DoubleToString(g_buy.weightedAvg, g_digits),
      "  TPbaza=", DoubleToString(g_buy.baseTp, g_digits),
      "  TPkosz=", DoubleToString(g_buy.basketTp, g_digits),
      "  PnL=", DoubleToString(g_buy.pnl, 2),
      " / ", DoubleToString(BasketProfitTarget_USD, 2), "\n",
      "SELL [magic ", IntegerToString(MagicNumberSell), "]:  n=", IntegerToString(g_sell.count),
      "  ", (g_sell.count >= 2 ? "BASKET" : "BASE"),
      "  vol=", DoubleToString(g_sell.volumeSum, 2),
      "  BE=", DoubleToString(g_sell.weightedAvg, g_digits),
      "  TPbaza=", DoubleToString(g_sell.baseTp, g_digits),
      "  TPkosz=", DoubleToString(g_sell.basketTp, g_digits),
      "  PnL=", DoubleToString(g_sell.pnl, 2),
      " / ", DoubleToString(BasketProfitTarget_USD, 2)
   );
  }

//====================================================================
// WIZUALIZACJA — baza: linia TP; koszyk: BE + przerywany Basket TP
//====================================================================
void DeleteHLine(const string name)
  {
   if(ObjectFind(0, name) >= 0)
      ObjectDelete(0, name);
  }

void UpsertHLine(const string name, const double price, const color clr,
                 const ENUM_LINE_STYLE style, const int width, const string caption)
  {
   if(price <= 0.0)
     {
      DeleteHLine(name);
      return;
     }

   if(ObjectFind(0, name) < 0)
     {
      if(!ObjectCreate(0, name, OBJ_HLINE, 0, 0, price))
        {
         PrintFormat("%s: ObjectCreate %s FAIL err=%d", EA_TAG, name, GetLastError());
         return;
        }
      ObjectSetInteger(0, name, OBJPROP_BACK, false);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, false);
      ObjectSetInteger(0, name, OBJPROP_SELECTED, false);
      ObjectSetInteger(0, name, OBJPROP_RAY_RIGHT, true);
     }

   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_STYLE, style);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, width);
   ObjectSetString(0, name, OBJPROP_TEXT, caption);
   ObjectSetString(0, name, OBJPROP_TOOLTIP, caption);
   ObjectSetDouble(0, name, OBJPROP_PRICE, 0, price);
  }

void UpdateSideVisuals(const BasketState &b, const string baseName,
                       const string beName, const string tpName, const color clr)
  {
   if(b.count <= 0)
     {
      DeleteHLine(baseName);
      DeleteHLine(beName);
      DeleteHLine(tpName);
      return;
     }

   if(b.count == 1)
     {
      UpsertHLine(baseName, b.baseTp, clr, STYLE_SOLID, 1, b.name + " Base TP");
      DeleteHLine(beName);
      DeleteHLine(tpName);
      return;
     }

   DeleteHLine(baseName);
   UpsertHLine(beName, b.weightedAvg, clr, STYLE_SOLID, 2, b.name + " Break-Even");
   UpsertHLine(tpName, b.basketTp, clr, STYLE_DASH, 1, b.name + " Basket TP");
  }

void UpdateBasketVisuals()
  {
   UpdateSideVisuals(g_buy,
                     LINE_BASE_TP_BUY + "_" + _Symbol,
                     LINE_BASKET_BE_BUY + "_" + _Symbol,
                     LINE_BASKET_TP_BUY + "_" + _Symbol,
                     clrDodgerBlue);
   UpdateSideVisuals(g_sell,
                     LINE_BASE_TP_SELL + "_" + _Symbol,
                     LINE_BASKET_BE_SELL + "_" + _Symbol,
                     LINE_BASKET_TP_SELL + "_" + _Symbol,
                     clrCrimson);
   ChartRedraw(0);
  }

void DeleteBasketVisuals()
  {
   const string suffix = "_" + _Symbol;
   DeleteHLine(LINE_BASE_TP_BUY + suffix);
   DeleteHLine(LINE_BASE_TP_SELL + suffix);
   DeleteHLine(LINE_BASKET_BE_BUY + suffix);
   DeleteHLine(LINE_BASKET_BE_SELL + suffix);
   DeleteHLine(LINE_BASKET_TP_BUY + suffix);
   DeleteHLine(LINE_BASKET_TP_SELL + suffix);
   ChartRedraw(0);
  }

void StripBasketStops(const int magic, const ENUM_POSITION_TYPE ptype)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      const ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)
         continue;
      if((int)PositionGetInteger(POSITION_MAGIC) != magic)
         continue;
      if((ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) != ptype)
         continue;

      const double sl = PositionGetDouble(POSITION_SL);
      const double tp = PositionGetDouble(POSITION_TP);
      if(sl == 0.0 && tp == 0.0)
         continue;

      if(ApplyPositionStops(ticket, 0.0, 0.0))
         PrintFormat("%s: zdjeto SL/TP z ticket=%I64u (magic=%d, koszyk)", EA_TAG, ticket, magic);
     }
  }

void EnsureHybridStops()
  {
   RefreshBasketStats(g_buy);
   RefreshBasketStats(g_sell);

   if(g_buy.count >= 2)
      StripBasketStops(MagicNumberBuy, POSITION_TYPE_BUY);
   else if(g_buy.count == 1 && g_buy.lastTicket > 0 && PositionSelectByTicket(g_buy.lastTicket) &&
           PositionGetDouble(POSITION_TP) <= 0.0)
      ApplyPositionStops(g_buy.lastTicket, 0.0,
                         BaseTakeProfitPrice(ORDER_TYPE_BUY, g_buy.lastOpenPrice));

   if(g_sell.count >= 2)
      StripBasketStops(MagicNumberSell, POSITION_TYPE_SELL);
   else if(g_sell.count == 1 && g_sell.lastTicket > 0 && PositionSelectByTicket(g_sell.lastTicket) &&
           PositionGetDouble(POSITION_TP) <= 0.0)
      ApplyPositionStops(g_sell.lastTicket, 0.0,
                         BaseTakeProfitPrice(ORDER_TYPE_SELL, g_sell.lastOpenPrice));
  }

//+------------------------------------------------------------------+
