//+------------------------------------------------------------------+
//| ImpulseProbeEA.mq5 -- research probe, NOT a trading EA            |
//|                                                                  |
//| Purpose: answer question 1 of the brief ("what is an impulse     |
//| candle that has a real edge, and how do we prove it?") with      |
//| measurement instead of belief.                                   |
//|                                                                  |
//| OnInit() copies the whole M5 history, then writes one CSV row    |
//| per bar with the bar geometry and the forward excursion.         |
//| Nothing is traded. OnInit returns INIT_FAILED so the tester      |
//| stops immediately after the dump.                                |
//|                                                                  |
//| Entry model recorded here: signal on bar i close, execution at   |
//| bar i+1 open. All forward numbers are (price - entry) so a       |
//| positive value means "price went up after the signal".           |
//+------------------------------------------------------------------+
#property strict
#property version "2.00"

// v2: the dump now happens in OnDeinit, because in OnInit the tester's rate
// cache only holds the first loaded block (v1 wrote 2023 rows while the run
// was 2024-2026). By OnDeinit the whole tested range is in the cache.

input string InpFile     = "impulse_probe.csv";
input int    InpATRPeriod = 14;
input int    InpRegimePeriod = 100;  // second ATR for the volatility-regime ratio
input int    InpHorizons  = 32;      // widest forward horizon in bars

int hset[] = {1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48};

int OnInit()
{
   PrintFormat("PROBE v2 init: bars now=%d", Bars(_Symbol, PERIOD_M5));
   return(INIT_SUCCEEDED);
}

void OnTick() {}

void OnDeinit(const int reason)
{
   int nb = Bars(_Symbol, PERIOD_M5);
   if(nb < 1000)
   {
      PrintFormat("PROBE: not enough history, Bars()=%d reason=%d", nb, reason);
      return;
   }

   MqlRates r[];
   int copied = CopyRates(_Symbol, PERIOD_M5, 0, nb, r);
   if(copied < 1000)
   {
      PrintFormat("PROBE: CopyRates returned %d", copied);
      return;
   }

   double tickVal  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double csize    = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   int    digits   = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double spread   = (double)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) * SymbolInfoDouble(_Symbol, SYMBOL_POINT);

   int fh = FileOpen(InpFile, FILE_WRITE | FILE_TXT | FILE_ANSI);
   if(fh == INVALID_HANDLE)
   {
      PrintFormat("PROBE: FileOpen failed err=%d", GetLastError());
      return;
   }

   FileWriteString(fh, StringFormat("### symbol=%s contract=%.4f tickval=%.6f ticksize=%.6f digits=%d spread=%.5f bars=%d first=%s last=%s\n",
                                    _Symbol, csize, tickVal, tickSize, digits, spread, copied,
                                    TimeToString(r[0].time, TIME_DATE | TIME_MINUTES),
                                    TimeToString(r[copied-1].time, TIME_DATE | TIME_MINUTES)));

   string hdr = "idx,time,dow,hour,open,high,low,close,range,atr14,atr100,range_atr,rng_atr100,body,body_ratio,dir,close_pos,gap";
   for(int k = 0; k < ArraySize(hset); k++)
      hdr += StringFormat(",ret%d,mfe%d,mae%d", hset[k], hset[k], hset[k]);
   hdr += "\n";
   FileWriteString(fh, hdr);

   double tr[];
   ArrayResize(tr, copied);
   for(int i = 0; i < copied; i++)
   {
      double prevClose = (i > 0 ? r[i-1].close : r[i].open);
      double a = r[i].high - r[i].low;
      double b = MathAbs(r[i].high - prevClose);
      double c = MathAbs(r[i].low  - prevClose);
      tr[i] = MathMax(a, MathMax(b, c));
   }

   double atr[], atrL[]; ArrayResize(atr, copied); ArrayResize(atrL, copied);
   double sum = 0.0, sumL = 0.0;
   for(int i = 0; i < copied; i++)
   {
      sum  += tr[i];
      sumL += tr[i];
      if(i >= InpATRPeriod)   sum  -= tr[i - InpATRPeriod];
      if(i >= InpRegimePeriod) sumL -= tr[i - InpRegimePeriod];
      int n  = (i + 1 < InpATRPeriod    ? i + 1 : InpATRPeriod);
      int nL = (i + 1 < InpRegimePeriod ? i + 1 : InpRegimePeriod);
      atr[i]  = (n  > 0 ? sum  / n  : 0.0);
      atrL[i] = (nL > 0 ? sumL / nL : 0.0);
   }

   int maxH = hset[ArraySize(hset)-1];
   int written = 0;
   for(int i = InpRegimePeriod + 2; i < copied - maxH - 2; i++)
   {
      double rng  = r[i].high - r[i].low;
      double body = MathAbs(r[i].close - r[i].open);
      double dir  = (r[i].close >= r[i].open ? 1.0 : -1.0);
      double entry = r[i+1].open;
      MqlDateTime dt; TimeToStruct(r[i].time, dt);
      double closePos = (rng > 0 ? (r[i].close - r[i].low) / rng : 0.5);
      double gap = r[i].open - r[i-1].close;

      string line = StringFormat("%d,%s,%d,%d,%.5f,%.5f,%.5f,%.5f,%.5f,%.5f,%.5f,%.4f,%.4f,%.5f,%.4f,%.0f,%.4f,%.5f",
                                 i,
                                 TimeToString(r[i].time, TIME_DATE | TIME_MINUTES),
                                 dt.day_of_week, dt.hour,
                                 r[i].open, r[i].high, r[i].low, r[i].close,
                                 rng, atr[i], atrL[i],
                                 (atr[i] > 0 ? rng / atr[i] : 0.0),
                                 (atrL[i] > 0 ? rng / atrL[i] : 0.0),
                                 body,
                                 (rng > 0 ? body / rng : 0.0),
                                 dir, closePos, gap);

      for(int k = 0; k < ArraySize(hset); k++)
      {
         int h = hset[k];
         double mfe = -1e18, mae = 1e18;
         for(int j = 1; j <= h; j++)
         {
            double hi = r[i+j].high - entry;
            double lo = r[i+j].low  - entry;
            if(hi > mfe) mfe = hi;
            if(lo < mae) mae = lo;
         }
         double ret = r[i+h].close - entry;
         line += StringFormat(",%.5f,%.5f,%.5f", ret, mfe, mae);
      }
      line += "\n";
      FileWriteString(fh, line);
      written++;
   }

   FileClose(fh);
   PrintFormat("PROBE: wrote %d rows to %s (bars=%d, atr period=%d)", written, InpFile, copied, InpATRPeriod);
}
