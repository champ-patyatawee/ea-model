import run_bt as R
CASES=[
 ("lockoff_train","2025.01.01","2026.07.01",{"InpUseDailyDirLock":"false"}),
 ("lock2_train","2025.01.01","2026.07.01",{"InpUseDailyDirLock":"true","InpMaxDirLossesPerDay":2}),
 ("lockoff_oos","2026.07.01","2026.09.18",{"InpUseDailyDirLock":"false"}),
 ("lock2_oos","2026.07.01","2026.09.18",{"InpUseDailyDirLock":"true","InpMaxDirLossesPerDay":2}),
]
for tag,d1,d2,p in CASES:
    R.run(R.build_ini(d1,d2,p,deposit=10000))
    m=R.parse()
    print(tag,{k:m.get(k) for k in ("net","pf","trades","dd_pct")},flush=True)
