import run_bt as R
BASE={"InpMinReactionScore":2.5,"InpTP_R":1.5,"InpFixedLot":0.02,
      "InpUseRegimeFilter":"false","InpUseATRAdaptiveZone":"false","InpUseDualMode":"false",
      "InpUseHTFTrendFilter":"false","InpUseDailyDirLock":"false","InpRandomEntry":"false"}
PER=[("train","2025.01.01","2026.07.01"),("oos","2026.07.01","2026.09.18")]
for name,ov in [("FADE(now)",{"InpFadeMode":"true"}),("INVERTED",{"InpFadeMode":"false"})]:
    p=dict(BASE); p.update(ov); p["InpMaxEntriesPerDirPerDay"]=3
    for tag,d1,d2 in PER:
        R.run(R.build_ini(d1,d2,p,deposit=10000))
        m=R.parse()
        print(name,tag,{k:m.get(k) for k in ("net","pf","trades","dd_pct")},flush=True)
