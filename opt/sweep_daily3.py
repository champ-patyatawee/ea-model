import statistics as st
import run_bt as R
LOTS=[0.02,0.03,0.04]
P=[("train","2025.01.01","2026.07.01"),("oos","2026.07.01","2026.09.18")]
def stats(d):
    v=sorted(d.values()); n=len(v)
    strk=best=0
    for k in sorted(d):
        if d[k]<0: strk+=1; best=max(best,strk)
        else: strk=0
    return dict(days=n,mean=round(st.mean(v),2),med=round(st.median(v),2),
        ge10=sum(1 for x in v if x>=10),ge20=sum(1 for x in v if x>=20),
        m50=sum(1 for x in v if x<=-50),m100=sum(1 for x in v if x<=-100),
        worst=round(min(v),2),best=round(max(v),2),strk=best)
print("lot|per|days|mean|med|>=10|>=20|<=-50|<=-100|worst|best|strk")
for lot in LOTS:
    for nm,d1,d2 in P:
        R.run(R.build_ini(d1,d2,{"InpFixedLot":lot},deposit=10000))
        s=stats(R.daily_pnl())
        print(f"{lot}|{nm}|{s['days']}|{s['mean']}|{s['med']}|{s['ge10']}|{s['ge20']}|{s['m50']}|{s['m100']}|{s['worst']}|{s['best']}|{s['strk']}",flush=True)
