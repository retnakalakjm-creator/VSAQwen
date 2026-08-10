from data import download_data, daily_to_weekly
from metrics_engine import MetricsEngine
from evidence.engine import EvidenceEngine
from professional.scoring_engine import ProfessionalScoringEngine
from background.qualification import PatternQualificationEngine
from scanner import ScannerCandidate, ScannerEngine, rank_candidates
from models import TrendResult
from trend import TrendAnalyzer
from engine.columns import COL_WEEK


SYMBOL = "BHARTIARTL.NS"
TARGET_INDEX = 530


daily = download_data(SYMBOL)
weekly = daily_to_weekly(daily)
metrics = MetricsEngine().calculate(weekly)
scanner = ScannerEngine()
qualification_engine = PatternQualificationEngine()


# ---------------------------------------------------------
# Point-in-time chronological replay
# ---------------------------------------------------------
# Each snapshot is built only from bars available at that point.
# Structural progression is therefore recorded only when the
# corresponding structural swing is actually confirmed.

point_history: list = []

for index in range(scanner.MIN_REPLAY_BARS, TARGET_INDEX + 1):
    replay_metrics = metrics.iloc[: index + 1].copy()
    replay_trend = TrendAnalyzer().analyze(replay_metrics)
    replay_structural_swings = list(
        replay_trend.structure.structural_swings
    )

    replay_result = EvidenceEngine().collect(
        metrics=replay_metrics,
        trend=replay_trend,
        structural_swings=replay_structural_swings,
    )

    point_history.append(replay_result)

if not point_history:
    raise RuntimeError("No point-in-time replay snapshots were produced")

point_in_time_result = point_history[-1]
point_in_time_trend = TrendAnalyzer().analyze(
    metrics.iloc[: TARGET_INDEX + 1].copy()
)

point_qualification = qualification_engine.evaluate(point_history)
point_professional = ProfessionalScoringEngine().calculate(
    trend=point_in_time_trend,
    evidence=point_in_time_result,
)

point_in_time_candidate = ScannerCandidate(
    evidence=point_in_time_result,
    professional=point_professional,
    qualification_result=point_qualification,
)


# ---------------------------------------------------------
# Historical validation replay
# ---------------------------------------------------------
# Validation metrics may contain future bars, but qualification MUST
# still use the chronological point-in-time history above.

replay_metrics = metrics.iloc[: TARGET_INDEX + 1].copy()
replay_structure = point_in_time_trend.structure
replay_trend = TrendResult(structure=replay_structure)

historical_result = EvidenceEngine().collect(
    metrics=replay_metrics,
    trend=replay_trend,
    structural_swings=list(replay_structure.structural_swings),
    validation_metrics=metrics,
)

historical_score = ProfessionalScoringEngine().calculate(
    trend=replay_trend,
    evidence=historical_result,
)

historical_qualification = qualification_engine.evaluate(point_history)

historical_candidate = ScannerCandidate(
    evidence=historical_result,
    professional=historical_score,
    qualification_result=historical_qualification,
)


# ---------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------

print()
print("=" * 70)
print("SCANNER DIAGNOSTIC - CHRONOLOGICAL REPLAY")
print("=" * 70)
print("DIAGNOSTIC_VERSION = chronological-qualification-v3")


target_week = replay_metrics.iloc[-1][COL_WEEK]

print()
print("TARGET")
print({
    "symbol": SYMBOL,
    "bar_index": TARGET_INDEX,
    "week": str(target_week),
})


print()
print("CHRONOLOGICAL QUALIFICATION HISTORY")

structural_history = [
    item
    for result in point_history
    for item in result.evidence
    if item.code in {
        item.code.__class__.STRUCTURAL_PROGRESSION_IMPROVING,
        item.code.__class__.STRUCTURAL_PROGRESSION_WEAKENING,
    }
]

for item in structural_history:
    print({
        "bar_index": item.bar_index,
        "week": item.week_beginning,
        "code": str(item.code),
        "direction": str(item.direction),
        "strength": item.strength,
        "weight": item.weight,
        "quality": item.quality,
    })

print({
    "snapshots": len(point_history),
    "structural_events": len(structural_history),
    "qualification": point_qualification.qualification,
    "actionable": point_qualification.is_actionable_evidence,
    "reason": point_qualification.reason,
    "qualifying_codes": [
        str(code) for code in point_qualification.evidence_codes
    ],
    "qualifying_bar_indices": list(
        point_qualification.evidence_bar_indices
    ),
})


def _candidate_details(candidate: ScannerCandidate) -> dict:
    return {
        "qualification": candidate.qualification,
        "actionable": candidate.actionable,
        "reason": candidate.reason,
        "professional_strength": candidate.professional.strength,
        "professional_weakness": candidate.professional.weakness,
        "net_strength": candidate.net_strength,
        "net_pressure": candidate.net_pressure,
        "confidence": candidate.confidence,
        "base_score": candidate.base_score,
        "evidence_codes": list(candidate.evidence_codes),
    }


print()
print("HISTORICAL VALIDATION REPLAY")
print(_candidate_details(historical_candidate))

print()
print("POINT-IN-TIME REPLAY")
print(_candidate_details(point_in_time_candidate))

print()
print("EVIDENCE DIFFERENCE")
print({
    "historical_codes": list(historical_candidate.evidence_codes),
    "point_in_time_codes": list(point_in_time_candidate.evidence_codes),
})

print()
print("RANK KEY")
print({
    "historical": (
        int(historical_candidate.actionable),
        historical_candidate.base_score,
    ),
    "point_in_time": (
        int(point_in_time_candidate.actionable),
        point_in_time_candidate.base_score,
    ),
})

ranked = rank_candidates([
    historical_candidate,
    point_in_time_candidate,
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
