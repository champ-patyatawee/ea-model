//+------------------------------------------------------------------+
//| WarmHistory.mq5 - force MT5 to download history for a symbol      |
//| CopyRates() makes the terminal pull the real bars from the broker |
//| and store them, so the Strategy Tester can use them afterwards.   |
//+------------------------------------------------------------------+
#property strict

input string InpSymbol = "XAUUSDm";
input int    InpFromY  = 2026;
input int    InpFromM  = 6;
input int    InpToY    = 2026;
input int    InpToM    = 10;

void Log(string s)
  {
   int h = FileOpen("warm_log.txt", FILE_WRITE | FILE_READ | FILE_TXT | FILE_ANSI);
   if(h == INVALID_HANDLE)
      return;
   FileSeek(h, 0, SEEK_END);
   FileWrite(h, s);
   FileFlush(h);
   FileClose(h);
  }

void OnStart()
  {
   int h = FileOpen("warm_log.txt", FILE_WRITE | FILE_TXT | FILE_ANSI);
   if(h != INVALID_HANDLE)
     {
      FileWrite(h, "WARM START " + InpSymbol);
      FileClose(h);
     }

   string sym = InpSymbol;
   SymbolSelect(sym, true);

   datetime from = StringToTime(StringFormat("%04d.%02d.01", InpFromY, InpFromM));
   datetime to   = StringToTime(StringFormat("%04d.%02d.01", InpToY,  InpToM));

   ENUM_TIMEFRAMES tfs[2];
   tfs[0] = PERIOD_M1;
   tfs[1] = PERIOD_M5;

   for(int i = 0; i < 2; i++)
     {
      long total = 0;
      int  chunks = 0;
      datetime t = from;
      while(t < to)
        {
         MqlRates r[];
         int got = -1;
         for(int a = 0; a < 3 && got < 0; a++)      // retry: first call triggers the download
           {
            got = CopyRates(sym, tfs[i], t, t + 7 * 86400, r);
            if(got < 0)
               Sleep(500);
           }
         if(got > 0)
           {
            total += got;
            chunks++;
           }
         t += 7 * 86400;
        }
      Log(StringFormat("WARM %s bars=%d chunks=%d", EnumToString(tfs[i]), (int)total, chunks));
     }

   Log("WARM DONE");
  }
//+------------------------------------------------------------------+
