//+------------------------------------------------------------------+
//| ExportM1.mq5 — dump M1 bars for a symbol/date-range to CSV       |
//+------------------------------------------------------------------+
#property script_show_inputs
input string InpSymbol   = "XAUUSDm";
input int    InpYear     = 2025;
input int    InpMonth    = 7;
input string InpOutFile  = "xauusdm_m1_export.csv";

void OnStart()
{
   MqlTick tick;
   datetime from = StringToTime(StringFormat("%04d.%02d.01 00:00", InpYear, InpMonth));
   int daysInMonth = 31;
   datetime to = from + daysInMonth*86400;
   // clamp to real month end
   MqlDateTime dt; TimeToStruct(from, dt);
   int mdays[12] = {31,28,31,30,31,30,31,31,30,31,30,31};
   int dim = mdays[dt.mon-1];
   if(dt.mon==2 && ((dt.year%4==0&&dt.year%100!=0)||dt.year%400==0)) dim=29;
   to = from + dim*86400 - 1;

   if(!SymbolSelect(InpSymbol, true)) { Print("SymbolSelect failed ", InpSymbol); return; }

   MqlRates rates[];
   ArraySetAsSeries(rates, false);
   int copied = CopyRates(InpSymbol, PERIOD_M1, from, to, rates);
   PrintFormat("CopyRates %s [%s .. %s] -> %d bars", InpSymbol,
               TimeToString(from, TIME_DATE|TIME_MINUTES),
               TimeToString(to, TIME_DATE|TIME_MINUTES), copied);
   if(copied <= 0) { Print("No bars. err=", GetLastError()); return; }

   int h = FileOpen(InpOutFile, FILE_WRITE|FILE_CSV|FILE_ANSI, ',');
   if(h == INVALID_HANDLE) { Print("FileOpen failed ", GetLastError()); return; }
   FileWrite(h, "time_utc","open","high","low","close","volume");
   for(int i=0; i<copied; i++)
   {
      FileWrite(h,
         TimeToString(rates[i].time, TIME_DATE|TIME_MINUTES),
         DoubleToString(rates[i].open, 5),
         DoubleToString(rates[i].high, 5),
         DoubleToString(rates[i].low, 5),
         DoubleToString(rates[i].close, 5),
         (long)rates[i].tick_volume);
   }
   FileClose(h);
   PrintFormat("Wrote %d bars -> MQL5/Files/%s", copied, InpOutFile);
}
//+------------------------------------------------------------------+
