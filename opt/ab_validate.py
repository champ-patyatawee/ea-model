import run_bt as R
OFF={"InpUseRegimeFilter":"false","InpUseATRAdaptiveZone":"false","InpUseDualMode":"false",
     "InpUseHTFTrendFilter":"false","InpUseDailyDirLock":"false","InpRandomEntry":"false","InpFixedLot":0.02}
CASES=[
 ("react3.5",{"InpMinReactionScore":3.5}),
 ("dirlock2",{"InpUseDailyDirLock":"true","InpMaxDirLossesPerDay":2}),
 ("react3.5+dirlock2",{"InpMinReactionScore":3.5,"InpUseDailyDirLock":"true","InpMaxDirLossesPerDay":2}),
]
PER=[("Sep","2026.09.01","2026.09.19"),("train","2025.01.01","2026.07.01"),("oos","2026.07.01","2026.09.18")]
for name,ov in CASES:
    p=dict(OFF); p.update(ov)
    for tag,d1,d2 in PER:
        R.run(R.build_ini(d1,d2,p,deposit=10000))
        m=R.parse(); print(name,tag,{k:m.get(k) for k in ("net","pf","trades","dd_pct")},flush=True)
