import run_bt as R
CASES=[
 ("base",      {}),
 ("B_atrzone", {"InpUseATRAdaptiveZone":"true","InpATRZoneShift":0.10}),
 ("C_dual",    {"InpUseDualMode":"true"}),
 ("BC",        {"InpUseATRAdaptiveZone":"true","InpATRZoneShift":0.10,"InpUseDualMode":"true"}),
]
PER=[("train","2025.01.01","2026.07.01"),("oos","2026.07.01","2026.09.18")]
for name,p in CASES:
    for tag,d1,d2 in PER:
        R.run(R.build_ini(d1,d2,p,deposit=10000))
        m=R.parse()
        print(name,tag,{k:m.get(k) for k in ("net","pf","trades","dd_pct")},flush=True)
