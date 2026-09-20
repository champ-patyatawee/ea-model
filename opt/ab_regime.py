import run_bt as R
THR=[0.25,0.5,1.0,2.0]
PER=[("train","2025.01.01","2026.07.01"),("oos","2026.07.01","2026.09.18")]
for thr in THR:
    p={"InpUseRegimeFilter":"true","InpRegimeStrengthMin":thr}
    for tag,d1,d2 in PER:
        R.run(R.build_ini(d1,d2,p,deposit=10000))
        m=R.parse()
        print(f"thr{thr}",tag,{k:m.get(k) for k in ("net","pf","trades","dd_pct")},flush=True)
