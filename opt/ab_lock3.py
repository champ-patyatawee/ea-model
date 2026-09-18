import run_bt as R
P={"InpUseDailyDirLock":"true","InpMaxDirLossesPerDay":3}
for tag,d1,d2 in [("lock3_train","2025.01.01","2026.07.01"),("lock3_oos","2026.07.01","2026.09.18")]:
    R.run(R.build_ini(d1,d2,P,deposit=10000))
    m=R.parse()
    print(tag,{k:m.get(k) for k in ("net","pf","trades","dd_pct")},flush=True)
