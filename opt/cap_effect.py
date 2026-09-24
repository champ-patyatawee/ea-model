import re,html,collections,json,os
import run_bt as R
OFF={"InpUseRegimeFilter":"false","InpUseATRAdaptiveZone":"false","InpUseDualMode":"false",
     "InpUseHTFTrendFilter":"false","InpUseDailyDirLock":"false","InpRandomEntry":"false",
     "InpFixedLot":0.02,"InpMinReactionScore":2.5,"InpTP_R":1.5}
def parse_days():
    s=open(R.HOST+"/report.htm",encoding="utf-16").read()
    rows=[];h=None
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>",s,flags=re.S|re.I):
        c=[html.unescape(re.sub(r"<[^>]+>","",x)).strip() for x in re.findall(r"<td[^>]*>(.*?)</td>",r,flags=re.S|re.I)]
        if c and c[0]=="Time" and "Deal" in c: h=c; continue
        if h and c and c[0][:2]=="20" and len(c)>=len(h): rows.append(dict(zip(h,c)))
    pos=[];cur=None
    for d in rows:
        if d.get("Direction")=="in": cur={"in":d,"outs":[]}; pos.append(cur)
        elif d.get("Direction")=="out" and cur is not None: cur["outs"].append(d)
    def f(x):
        try: return float(x.replace(" ","").replace("\u00a0","").replace("\u202f",""))
        except: return 0.0
    day=collections.defaultdict(lambda:{"net":0.0,"n":0,"nL":0,"nS":0,"L":0.0,"S":0.0})
    for t in pos:
        p=sum(f(o["Profit"]) for o in t["outs"]); d=t["in"]["Time"][:10]; side=t["in"].get("Type")
        dd=day[d]; dd["net"]+=p; dd["n"]+=1
        if side=="buy": dd["nL"]+=1; dd["L"]+=p
        else: dd["nS"]+=1; dd["S"]+=p
    return day
res={}
for cap in [0,3,4]:
    p=dict(OFF); p["InpMaxEntriesPerDirPerDay"]=cap
    R.run(R.build_ini("2025.01.01","2026.09.24",p,deposit=10000))
    res[cap]=parse_days()
    print("cap",cap,"days",len(res[cap]),flush=True)
json.dump(res,open("cap_days.json","w"))
for cap in [0,3,4]:
    d=res[cap]; vals=sorted((v["net"] for v in d.values()))
    tot=sum(vals); worst=sum(vals[:10]); n50=sum(1 for x in vals if x<=-50); n80=sum(1 for x in vals if x<=-80)
    # max one-sided day loss
    onels=min(v["L"] for v in d.values()); onesh=min(v["S"] for v in d.values())
    print(f"cap{cap}: total={tot:7.0f} 10worst={worst:7.0f} days<=-50:{n50} <=-80:{n80} "
          f"worstDay={vals[0]:.0f} maxLongLoss={onels:.0f} maxShortLoss={onesh:.0f}")
