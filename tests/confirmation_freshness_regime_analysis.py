from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from background.qualification import PatternQualification
from data import daily_to_weekly, download_data
from evidence.engine import EvidenceEngine
from metrics_engine import MetricsEngine
from scanner import ScannerEngine
from trend import TrendAnalyzer

from tests.decision_outcome_audit import CONFIRMATION_ONLY_CODES, mask_confirmation_only
from tests.decision_outcome_labeling import label_outcome


def _direction(candidate) -> int | None:
    if candidate.qualification is PatternQualification.PERSISTENT_BULLISH:
        return 1
    if candidate.qualification is PatternQualification.PERSISTENT_BEARISH:
        return -1
    return None


def analyze(csv_path: str, *, refresh: bool = False) -> list[dict]:
    source = pd.read_csv(csv_path)
    rows: list[dict] = []
    for symbol, group in source.groupby("symbol"):
        daily = download_data(symbol, refresh=refresh)
        weekly = daily_to_weekly(daily)
        metrics = MetricsEngine().calculate(weekly)
        scanner = ScannerEngine()
        wanted = {int(value) for value in group["bar_index"]}
        history = []

        for index in range(scanner.MIN_REPLAY_BARS, len(metrics)):
            replay = metrics.iloc[: index + 1].copy()
            trend = TrendAnalyzer().analyze(replay)
            evidence = EvidenceEngine().collect(
                metrics=replay,
                trend=trend,
                structural_swings=list(trend.structure.structural_swings),
            )
            history.append(evidence)

            if index not in wanted:
                continue

            match = group.loc[group["bar_index"] == index]
            if match.empty:
                continue
            horizon = int(match["horizon"].iloc[0])

            baseline = scanner.evaluate(
                trend=trend,
                evidence=evidence,
                history=history,
                bar_index=index,
                week=scanner._week_at(metrics, index),
            )
            masked = scanner.evaluate(
                trend=trend,
                evidence=mask_confirmation_only(evidence),
                history=history,
                bar_index=index,
                week=scanner._week_at(metrics, index),
            )
            direction = _direction(baseline)
            if direction is None:
                continue

            outcome = label_outcome(metrics, signal_index=index, direction=direction, horizon=horizon)
            confirmation_items = [item for item in evidence.evidence if item.code in CONFIRMATION_ONLY_CODES]
            codes = tuple(str(item.code) for item in confirmation_items)
            ages = [
                index - int(item.bar_index)
                for item in confirmation_items
                if getattr(item, "bar_index", None) is not None
            ]
            rows.append({
                "symbol": symbol,
                "bar_index": index,
                "week": str(weekly.iloc[index]["week_beginning"]),
                "change": f"{baseline.actionable}->{masked.actionable}",
                "confirmation_only_codes": ",".join(codes),
                "confirmation_age": min(ages) if ages else None,
                "trend_direction": str(trend.structure.direction),
                "trend_state": str(trend.structure.state),
                "professional_score": baseline.base_score,
                "net_pressure": baseline.net_pressure,
                "forward_return": outcome.forward_return,
                "mfe": outcome.maximum_favorable_excursion,
                "mae": outcome.maximum_adverse_excursion,
            })
    return rows


def summarize(rows: list[dict]) -> list[dict]:
    buckets: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for row in rows:
        for code in filter(None, row["confirmation_only_codes"].split(",")):
            buckets[(code, row["change"], str(row["trend_state"]))].append(row)

    output: list[dict] = []
    for (code, change, trend_state), cases in sorted(buckets.items()):
        returns = [r["forward_return"] for r in cases if r["forward_return"] is not None]
        mfes = [r["mfe"] for r in cases if r["mfe"] is not None]
        maes = [r["mae"] for r in cases if r["mae"] is not None]
        ages = [r["confirmation_age"] for r in cases if r["confirmation_age"] is not None]
        output.append({
            "code": code,
            "change": change,
            "trend_state": trend_state,
            "cases": len(cases),
            "mean_age": sum(ages) / len(ages) if ages else None,
            "current_or_recent": sum(age <= 1 for age in ages),
            "mean_return": sum(returns) / len(returns) if returns else None,
            "mean_mfe": sum(mfes) / len(mfes) if mfes else None,
            "mean_mae": sum(maes) / len(maes) if maes else None,
        })
    return output
