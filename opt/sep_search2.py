import run_bt as R
OFF={"InpUseRegimeFilter":"false","InpUseATRAdaptiveZone":"false","InpUseDualMode":"false",
     "InpUseHTFTrendFilter":"false","InpUseDailyDirLock":"false","InpRandomEntry":"false","InpFixedLot":0.02}
SEP=("2026.09.01","2026.09.19")
CASES=[
 ("react3.25",{"InpMinReactionScore":3.25}),
 ("react3.5",{"InpMinReactionScore":3.5}),
 ("react3.75",{"InpMinReactionScore":3.75}),
 ("react4.0",{"InpMinReactionScore":4.0}),
 ("react3.5+eff0.5",{"InpMinReactionScore":3.5,"InpFadeMinEfficiency":0.5}),
 ("react3.5+fib382618",{"InpMinReactionScore":3.5,"InpEntryFibMin":0.382,"InpEntryFibMax":0.618}),
 ("react3.5+sl1.5",{"InpMinReactionScore":3.5,"InpSL_ATR":1.5}),
 ("react3.5+tp1.5",{"InpMinReactionScore":3.5,"InpTP_R":1.5}),
]
for name,ov in CASES:
    p=dict(OFF); p.update(ov)
    R.run(R.build_ini(SEP[0],SEP[1],p,deposit=10000))
    m=R.parse(); print(name,{k:m.get(k) for k in ("net","pf","trades","dd_pct")},flush=True)
