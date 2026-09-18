import run_bt as R
R.run(R.build_ini("2026.09.01","2026.09.19",{},deposit=10000))
trades=[]
cur=None
for d in R.parse_deals():
    if d[0][:7]!="2026.09": continue
    trades.append(d)
# group by day
import collections
day=collections.OrderedDict()
for date,p in trades:
    day.setdefault(date,[]).append(p)
print(f"{'date':12} {'trades':>6} {'win':>4} {'loss':>5} {'net$':>9} {'cum$':>9}")
cum=0.0
for d in sorted(day):
    v=day[d]; net=sum(v); cum+=net
    print(f"{d:12} {len(v):>6} {sum(1 for x in v if x>0):>4} {sum(1 for x in v if x<0):>5} {net:>9.2f} {cum:>9.2f}")
print("TOTAL", round(sum(sum(v) for v in day.values()),2), "trades", len(trades))
