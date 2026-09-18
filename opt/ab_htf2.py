import run_bt as R
P={"InpUseHTFTrendFilter":"true"}
for tag,d1,d2 in [("htfTRUE_train","2025.01.01","2026.07.01"),
                  ("htfTRUE_oos","2026.07.01","2026.09.18")]:
    R.run(R.build_ini(d1,d2,P,deposit=10000))
    m=R.parse()
    print(tag,{k:m.get(k) for k in ("net","pf","trades","dd_pct")},flush=True)
