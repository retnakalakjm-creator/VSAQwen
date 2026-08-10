from data import download_data, daily_to_weekly
from metrics_engine import MetricsEngine
from evidence.engine import EvidenceEngine
from professional.scoring_engine import ProfessionalScoringEngine
from background.qualification import PatternQualificationEngine
from scanner import ScannerCandidate, rank_candidates, ScannerEngine
from trend import TrendAnalyzer
from engine.columns import COL_WEEK


SYMBOL = "BHARTIARTL.NS"
TARGET_INDEX = 520


daily = download_data(SYMBOL)
weekly = daily_to_weekly(daily)
metrics = MetricsEngine().calculate(weekly)
scanner = ScannerEngine()
qualification_engine = PatternQualificationEngine()


# ---------------------------------------------------------
# Point-in-time chronological replay through target
# ---------------------------------------------------------
point_history: list = []

for index in range(scanner.MIN_REPLAY_BARS, TARGET_INDEX + 1):
    replay_metrics = metrics.iloc[: index + 1].copy()
    trend = TrendAnalyzer().analyze(replay_metrics)
    structural_swings = list(trend.structure.structural_swings)

    result = EvidenceEngine().collect(
        metrics=replay_metrics,
        trend=trend,
        structural_swings=structural_swings,
    )

    point_history.append(result)

if not point_history:
    raise RuntimeError("No point-in-time replay snapshots were produced")

point_result = point_history[-1]
point_trend = TrendAnalyzer().analyze(
    metrics.iloc[: TARGET_INDEX + 1].copy()
)
point_qualification = qualification_engine.evaluate(point_history)
point_professional = ProfessionalScoringEngine().calculate(
    trend=point_trend,
    evidence=point_result,
)

point_candidate = ScannerCandidate(
    evidence=point_result,
    professional=point_professional,
    qualification_result=point_qualification,
)


# ---------------------------------------------------------
# Historical validation replay
# ---------------------------------------------------------
# Full validation data is supplied to evidence collection, but
# qualification still uses only the chronological point-in-time history.

historical_result = EvidenceEngine().collect(
    metrics=metrics.iloc[: TARGET_INDEX + 1].copy(),
    trend=point_trend,
    structural_swings=list(point_trend.structure.structural_swings),
    validation_metrics=metrics,
)

historical_professional = ProfessionalScoringEngine().calculate(
    trend=point_trend,
    evidence=historical_result,
)

historical_qualification = qualification_engine.evaluate(point_history)

historical_candidate = ScannerCandidate(
    evidence=historical_result,
    professional=historical_professional,
    qualification_result=historical_qualification,
)


# ---------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------

def _candidate_details(candidate: ScannerCandidate) -> dict:
    return {
        "qualification": candidate.qualification,
        "actionable": candidate.actionable,
        "reason": candidate.reason,
        "codes": list(candidate.evidence_codes),
        "base_score": candidate.base_score,
        "net_strength": candidate.net_strength,
        "net_pressure": candidate.net_pressure,
        "confidence": candidate.confidence,
    }


target_week = metrics.iloc[TARGET_INDEX][COL_WEEK]

print()
print("=" * 70)
print("SCANNER RANKING DIAGNOSTIC")
print("=" * 70)
print("DIAGNOSTIC_VERSION = direct-target-ranking-v1")

print()
print("TARGET")
print({
    "symbol": SYMBOL,
    "bar_index": TARGET_INDEX,
    "week": str(target_week),
})

print()
print("POINT-IN-TIME")
print(_candidate_details(point_candidate))

print()
print("HISTORICAL VALIDATION")
print(_candidate_details(historical_candidate))

print()
print("QUALIFICATION COMPARISON")
print({
    "point_in_time": point_candidate.qualification,
    "historical": historical_candidate.qualification,
    "same": (
        point_candidate.qualification
        == historical_candidate.qualification
    ),
})

print()
print("EVIDENCE DIFFERENCE")
print({
    "point_in_time_codes": list(point_candidate.evidence_codes),
    "historical_codes": list(historical_candidate.evidence_codes),
    "same": (
        point_candidate.evidence_codes
        == historical_candidate.evidence_codes
    ),
})

print()
print("RANK KEY")
print({
    "point_in_time": (
        int(point_candidate.actionable),
        point_candidate.base_score,
    ),
    "historical": (
        int(historical_candidate.actionable),
        historical_candidate.base_score,
    ),
})

ranked = rank_candidates([
    point_candidate,
    historical_candidate,
])

print()
print("RANKED ORDER")
for index, candidate in enumerate(ranked, start=1):
    print(
        index,
        {
            "qualification": candidate.qualification,
            "actionable": candidate.actionable,
            "base_score": candidate.base_score,
        },
    )

print()
print("=" * 70)
