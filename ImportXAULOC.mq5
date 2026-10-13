//+------------------------------------------------------------------+
//| ImportXAULOC.mq5 - build a custom symbol from our own M1 CSV      |
//| Lets the Strategy Tester run without broker history.              |
//+------------------------------------------------------------------+
#property strict

input string InpSymbol = "XAULOC";        // custom symbol name
input string InpFile   = "xaum1.csv";     // MQL5/Files/<name>
input string InpLog    = "import_log.txt";

int  g_log = INVALID_HANDLE;
void Log(string s)
  {
   if(g_log == INVALID_HANDLE)
      g_log = FileOpen(InpLog, FILE_WRITE | FILE_READ | FILE_TXT | FILE_ANSI);
   if(g_log == INVALID_HANDLE)
      return;
   FileSeek(g_log, 0, SEEK_END);
   FileWrite(g_log, s);
   FileFlush(g_log);
  }

void OnStart()
  {
   g_log = FileOpen(InpLog, FILE_WRITE | FILE_TXT | FILE_ANSI);
   Log("START " + InpFile);
   if(g_log != INVALID_HANDLE) { FileClose(g_log); g_log = INVALID_HANDLE; }

   string name = InpSymbol;

   if(!CustomSymbolCreate(name, "Custom", "XAUUSDm"))
      Log("CustomSymbolCreate: not created (may already exist), err=" + IntegerToString(GetLastError()));

   //--- XAUUSD contract properties: 100 oz per lot, 3 digits
   CustomSymbolSetInteger(name, SYMBOL_DIGITS, 3);
   CustomSymbolSetDouble (name, SYMBOL_POINT, 0.001);
   CustomSymbolSetInteger(name, SYMBOL_TRADE_CALC_MODE, SYMBOL_CALC_MODE_CFD);
   CustomSymbolSetDouble (name, SYMBOL_TRADE_CONTRACT_SIZE, 100.0);
   CustomSymbolSetDouble (name, SYMBOL_TRADE_TICK_SIZE, 0.001);
   CustomSymbolSetDouble (name, SYMBOL_TRADE_TICK_VALUE, 0.1);
   CustomSymbolSetDouble (name, SYMBOL_VOLUME_MIN, 0.01);
   CustomSymbolSetDouble (name, SYMBOL_VOLUME_STEP, 0.01);
   CustomSymbolSetDouble (name, SYMBOL_VOLUME_MAX, 50.0);
   CustomSymbolSetInteger(name, SYMBOL_TRADE_MODE, SYMBOL_TRADE_MODE_FULL);
   CustomSymbolSetInteger(name, SYMBOL_TRADE_EXEMODE, SYMBOL_TRADE_EXECUTION_INSTANT);
   CustomSymbolSetString (name, SYMBOL_CURRENCY_BASE, "XAU");
   CustomSymbolSetString (name, SYMBOL_CURRENCY_PROFIT, "USD");
   CustomSymbolSetString (name, SYMBOL_CURRENCY_MARGIN, "USD");
   CustomSymbolSetInteger(name, SYMBOL_SPREAD_FLOAT, 1);
   CustomSymbolSetInteger(name, SYMBOL_SPREAD, 30);

   if(!SymbolSelect(name, true))
      Print("SymbolSelect failed, err=", GetLastError());

   int h = FileOpen(InpFile, FILE_READ | FILE_CSV | FILE_ANSI, ',');
   if(h == INVALID_HANDLE)
     {
      Print("FileOpen failed: ", InpFile, " err=", GetLastError());
      return;
     }

   FileReadString(h);   // skip header

   MqlRates rates[];
   int cap = 20000;
   ArrayResize(rates, cap);
   int n = 0; long total = 0;

   while(!FileIsEnding(h))
     {
      string ts = FileReadString(h);
      if(StringLen(ts) < 10)
         break;
      string so = FileReadString(h);
      string sh = FileReadString(h);
      string sl = FileReadString(h);
      string sc = FileReadString(h);
      string sv = FileReadString(h);

      datetime t = StringToTime(ts);
      if(t <= 0)
         continue;

      if(n >= cap)
        {
         CustomRatesUpdate(name, rates, n);
         total += n;
         n = 0;
        }
      rates[n].time        = t;
      rates[n].open        = StringToDouble(so);
      rates[n].high        = StringToDouble(sh);
      rates[n].low         = StringToDouble(sl);
      rates[n].close       = StringToDouble(sc);
      rates[n].tick_volume = (long)StringToInteger(sv);
      rates[n].real_volume = 0;
      rates[n].spread      = 30;
      n++;
     }

   if(n > 0)
     {
      ArrayResize(rates, n);
      if(CustomRatesUpdate(name, rates, n) <= 0)
         Print("CustomRatesUpdate(last) failed, err=", GetLastError());
      total += n;
     }
   FileClose(h);

   Print("IMPORT DONE symbol=", name, " bars=", total);
  }
//+------------------------------------------------------------------+
