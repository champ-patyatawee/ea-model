import run_bt as R
OFF={"InpUseRegimeFilter":"false","InpUseATRAdaptiveZone":"false","InpUseDualMode":"false",
     "InpUseHTFTrendFilter":"false","InpUseDailyDirLock":"false","InpRandomEntry":"false",
     "InpFixedLot":0.02,"InpMinReactionScore":2.5,"InpTP_R":1.5}
PER=[("train","2025.01.01","2026.07.01"),("oos","2026.07.01","2026.09.18")]
for cap in [0,2,3,4]:
    p=dict(OFF); p["InpMaxEntriesPerDirPerDay"]=cap
    for tag,d1,d2 in PER:
        R.run(R.build_ini(d1,d2,p,deposit=10000))
        m=R.parse()
        print(f"cap{cap}",tag,{k:m.get(k) for k in ("net","pf","trades","dd_pct")},flush=True)
