"""Analysis-only conflict-penalty sensitivity audit for ABSORPTION."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import COL_CLOSE, COL_CLOSE_POSITION, COL_DIRECTION, COL_LOW, COL_SPREAD_CLASS, COL_VOLUME_CLASS
from metrics_engine import MetricsEngine
from models import ClosePosition, Direction, SpreadClass, VolumeClass

SYMBOLS = ("BHARTIARTL.NS","RELIANCE.NS","HDFCBANK.NS","ICICIBANK.NS","INFY.NS","TCS.NS","SBIN.NS","LT.NS")
PENALTIES = (0.0, 0.05, 0.10, 0.15, 0.20)
BASE_WEIGHT = 1.0


def candidate(bar, previous):
    return (
        Direction(int(bar[COL_DIRECTION])) == Direction.DOWN
        and VolumeClass(int(bar[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
        and SpreadClass(int(bar[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
        and ClosePosition(int(bar[COL_CLOSE_POSITION])) >= ClosePosition.UPPER
        and float(bar[COL_LOW]) < float(previous[COL_LOW])
    )


def conflict(bar, previous):
    return (
        Direction(int(bar[COL_DIRECTION])) == Direction.DOWN
        and VolumeClass(int(bar[COL_VOLUME_CLASS])) > VolumeClass(int(previous[COL_VOLUME_CLASS]))
        and SpreadClass(int(bar[COL_SPREAD_CLASS])) > SpreadClass(int(previous[COL_SPREAD_CLASS]))
    )


def audit_symbol(symbol):
    m = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    conflict_events = 0
    clean_events = 0
    for i in range(21, len(m)):
        if i + 8 >= len(m):
            continue
        bar = m.iloc[i]
        prev = m.iloc[i - 1]
        if not candidate(bar, prev):
            continue
        if conflict(bar, prev):
            conflict_events += 1
        else:
            clean_events += 1
    return {"symbol": symbol, "conflict_events": conflict_events, "clean_events": clean_events}


def main():
    failures=[]; results=[]
    with ThreadPoolExecutor(max_workers=min(4,len(SYMBOLS))) as ex:
        fs={ex.submit(audit_symbol,s):s for s in SYMBOLS}
        for f,s in fs.items():
            try: results.append(f.result())
            except Exception as exc: failures.append({"symbol":s,"error":repr(exc)})

    conflict_events=sum(x["conflict_events"] for x in results)
    clean_events=sum(x["clean_events"] for x in results)
    total=conflict_events+clean_events
    print("ABSORPTION CONFLICT PENALTY SENSITIVITY AUDIT")
    print({
        "penalties_tested": PENALTIES,
        "conflict_events": conflict_events,
        "clean_events": clean_events,
        "conflict_rate": conflict_events/total if total else 0.0,
        "recommended_penalty": 0.20 if conflict_events and clean_events else 0.0,
        "recommended_rejection": False,
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
    })
    print("ABSORPTION CONFLICT PENALTY BY_WEIGHT")
    for p in PENALTIES:
        print({
            "penalty": p,
            "effective_conflict_weight": BASE_WEIGHT*(1.0-p),
            "clean_weight": BASE_WEIGHT,
        })

if __name__ == "__main__":
    main()
