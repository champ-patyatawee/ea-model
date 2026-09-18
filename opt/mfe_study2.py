import re, subprocess, statistics as st
import run_bt as R
DOCKER=R.DOCKER; M=R.M; C=R.CONTAINER
def run_fresh(d1,d2):
    subprocess.run([DOCKER,"exec",C,"bash","-c",f"rm -f '{M}/Tester/logs/'*.log"],check=False)
    R.run(R.build_ini(d1,d2,{},deposit=10000))
    out=subprocess.run([DOCKER,"exec",C,"bash","-c",
        f"iconv -f UTF-16LE -t UTF-8 '{M}/Tester/logs/'*.log 2>/dev/null | grep MFELOG"],
        capture_output=True,text=True)
    return out.stdout
rows=[]
for ln in run_fresh("2025.01.01","2026.07.01").splitlines():
    m=re.search(r"MFELOG PROF=(-?\d+) MFE_R=(-?[\d.]+) MAE_R=(-?[\d.]+) P/L=(-?[\d.]+)",ln)
    if m: rows.append((int(m.group(1)),float(m.group(2)),float(m.group(3)),float(m.group(4))))
open("mfelog2.txt","w").write("\n".join(str(r) for r in rows))
n=len(rows)
mfe=[r[1] for r in rows]; mae=[r[2] for r in rows]; pl=[r[3] for r in rows]
print("positions:",n)
print("mean MFE %.3f  mean MAE %.3f  edge(MFE-|MAE|) %+.3f"%(st.mean(mfe),st.mean(mae),st.mean(mfe)-abs(st.mean(mae))))
print("P(MFE>=1)=%.1f%%  P(MAE<=-1)=%.1f%%"%(100*sum(1 for x in mfe if x>=1)/n,100*sum(1 for x in mae if x<=-1)/n))
print("MFE deciles:",[round(x,2) for x in st.quantiles(mfe,n=10)])
print("MAE deciles:",[round(x,2) for x in st.quantiles(mae,n=10)])
los=[r for r in rows if r[3]<0]; win=[r for r in rows if r[3]>0]
print("winners",len(win),"losers",len(los))
if los:
    print("  losers mean MFE %.3f (reached +1R: %d/%d)"%(st.mean([r[1] for r in los]),sum(1 for r in los if r[1]>=1),len(los)))
if win:
    print("  winners mean MAE %.3f (dipped -1R: %d/%d)"%(st.mean([r[2] for r in win]),sum(1 for r in win if r[2]<=-1),len(win)))
