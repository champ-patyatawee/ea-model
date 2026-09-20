import run_bt as R
CASES=[
 ("B_nopartial",   {"InpUsePartial":"false"}),
 ("C_pureTPSL",    {"InpUsePartial":"false","InpUseBreakEven":"false","InpUseTrailing":"false"}),
 ("D_latepart",    {"InpPartialR":1.5,"InpBreakEvenR":1.5,"InpTrailStartR":2.0}),
 ("E_noBE",        {"InpUseBreakEven":"false"}),
]
PER=[("train","2025.01.01","2026.07.01"),("oos","2026.07.01","2026.09.18")]
for name,p in CASES:
    for tag,d1,d2 in PER:
        R.run(R.build_ini(d1,d2,p,deposit=10000))
        m=R.parse()
        print(name,tag,{k:m.get(k) for k in ("net","pf","trades","payoff","dd_pct")},flush=True)
