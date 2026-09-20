import run_bt as R
OFF={"InpUseRegimeFilter":"false","InpUseATRAdaptiveZone":"false","InpUseDualMode":"false",
     "InpUseHTFTrendFilter":"false","InpUseDailyDirLock":"false","InpRandomEntry":"false","InpFixedLot":0.02}
P=dict(OFF); P.update({"InpMinReactionScore":3.5,"InpTP_R":1.5})
for tag,d1,d2 in [("train","2025.01.01","2026.07.01"),("oos","2026.07.01","2026.09.18")]:
    R.run(R.build_ini(d1,d2,P,deposit=10000)); m=R.parse()
    print("react3.5+tp1.5",tag,{k:m.get(k) for k in ("net","pf","trades","dd_pct")},flush=True)
