import sys, collections
import run_bt as R
d1,d2 = sys.argv[1], sys.argv[2]
import json,os
P=json.loads(os.environ.get("MT5_PARAMS","{}"))
DEP=float(os.environ.get("MT5_DEPOSIT","10000"))
R.run(R.build_ini(d1,d2,P,deposit=DEP))
# position-level per day
import re,html
s=open('report.htm',encoding='utf-16').read()
rows=[]; h=None
for r in re.findall(r'<tr[^>]*>(.*?)</tr>',s,flags=re.S|re.I):
    c=[html.unescape(re.sub(r'<[^>]+>','',x)).strip() for x in re.findall(r'<td[^>]*>(.*?)</td>',r,flags=re.S|re.I)]
    if c and c[0]=='Time' and 'Deal' in c: h=c; continue
    if h and c and c[0][:2]=='20' and len(c)>=len(h): rows.append(dict(zip(h,c)))
def f(x):
    try: return float(x.replace(' ','').replace('\u00a0','').replace('\u202f',''))
    except: return 0.0
pos=[]; cur=None
for d in rows:
    if d.get('Direction')=='in': cur={'in':d,'outs':[]}; pos.append(cur)
    elif d.get('Direction')=='out' and cur is not None: cur['outs'].append(d)
day=collections.OrderedDict()
for t in pos:
    dt=t['in']['Time'][:10]
    p=sum(f(o['Profit']) for o in t['outs'])
    if t['in'].get('Type')=='buy': side='LONG '
    else: side='SHORT'
    day.setdefault(dt,[]).append((side,p))
print(f"{'date':12}{'#':>5}{'win':>5}{'loss':>6}{'net$':>10}{'cum$':>10}")
cum=0.0
for d in sorted(day):
    v=day[d]; net=sum(x[1] for x in v); cum+=net
    print(f"{d:12}{len(v):>5}{sum(1 for x in v if x[1]>0):>5}{sum(1 for x in v if x[1]<0):>6}{net:>10.2f}{cum:>10.2f}   "+" ".join(f"{s.strip()}{p:+.1f}" for s,p in v))
print("TOTAL",round(sum(sum(x[1] for x in v) for v in day.values()),2),"| positions",sum(len(v) for v in day.values()))
