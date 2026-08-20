"""Analysis-only decision-value audit for DEMAND_DRYING_UP."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from data import daily_to_weekly, download_data
from engine.columns import COL_CLOSE, COL_DIRECTION, COL_VOLUME_CLASS, COL_SPREAD_CLASS
from metrics_engine import MetricsEngine
from models import Direction, VolumeClass, SpreadClass
SYMBOLS=("BHARTIARTL.NS","RELIANCE.NS","HDFCBANK.NS","ICICIBANK.NS","INFY.NS","TCS.NS","SBIN.NS","LT.NS")
FORWARD_BARS=8

def _candidate(bar, previous):
    return (Direction(int(bar[COL_DIRECTION]))==Direction.UP and
            VolumeClass(int(bar[COL_VOLUME_CLASS])) < VolumeClass(int(previous[COL_VOLUME_CLASS])) and
            SpreadClass(int(bar[COL_SPREAD_CLASS])) < SpreadClass(int(previous[COL_SPREAD_CLASS])))

def _audit_symbol(symbol):
    m=MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    cand=[]; eligible=[]
    for i in range(21,len(m)):
        if i+FORWARD_BARS>=len(m): continue
        s=float(m.iloc[i][COL_CLOSE]); e=float(m.iloc[i+FORWARD_BARS][COL_CLOSE])
        if s==0: continue
        r=e/s-1
        eligible.append(r)
        if _candidate(m.iloc[i],m.iloc[i-1]): cand.append(r)
    def stats(rs):
        pos=sum(r>0 for r in rs); neg=sum(r<0 for r in rs); dec=pos+neg
        return len(rs),pos,neg,dec,pos/dec if dec else 0.0,sum(rs)/len(rs) if rs else 0.0
    return symbol,stats(cand),stats(eligible)

def main():
    failures=[]; results=[]
    with ThreadPoolExecutor(max_workers=4) as ex:
        fs={ex.submit(_audit_symbol,s):s for s in SYMBOLS}
        for f,s in fs.items():
            try: results.append(f.result())
            except Exception as e: failures.append({'symbol':s,'error':repr(e)})
    cn=sum(x[1][0] for x in results); cp=sum(x[1][1] for x in results); cneg=sum(x[1][2] for x in results)
    en=sum(x[2][0] for x in results); ep=sum(x[2][1] for x in results); eneg=sum(x[2][2] for x in results)
    cdec=cp+cneg; edec=ep+eneg
    cmean=sum(x[1][5]*x[1][0] for x in results)/cn if cn else 0.0
    emean=sum(x[2][5]*x[2][0] for x in results)/en if en else 0.0
    print('DEMAND DRYING UP DECISION VALUE AUDIT')
    print({'symbols_requested':len(SYMBOLS),'symbols_with_results':len(results),'candidate':{'events':cn,'positive':cp,'negative':cneg,'decisive':cdec,'positive_decisive_rate':cp/cdec if cdec else 0.0,'mean_return':cmean},'eligible_market':{'events':en,'positive':ep,'negative':eneg,'decisive':edec,'positive_decisive_rate':ep/edec if edec else 0.0,'mean_return':emean},'positive_decisive_rate_lift':(cp/cdec if cdec else 0.0)-(ep/edec if edec else 0.0),'mean_return_lift':cmean-emean,'candidate_share_of_eligible':cn/en if en else 0.0,'failures':failures,'status':'PASS' if not failures else 'FAIL'})
if __name__=='__main__': main()
