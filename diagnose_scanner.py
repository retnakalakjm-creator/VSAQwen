from data import download_data, daily_to_weekly
from metrics_engine import MetricsEngine
from evidence.engine import EvidenceEngine
from background.qualification import PatternQualificationEngine
from debug.confidence_diagnostics import confidence_components, score_inputs
from scanner import ScannerEngine, rank_candidates
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
# Chronological qualification replay
# ---------------------------------------------------------
# This history exists ONLY to validate persistence qualification.
# It must never be passed into the current-bar professional scorer.
point_history: list = []

for index in range(scanner.MIN_REPLAY_BARS, TARGET_INDEX + 1):
    replay_metrics = metrics.iloc[: index + 1].copy()
    replay_trend = TrendAnalyzer().analyze(replay_metrics)
    replay_structural_swings = list(replay_trend.structure.structural_swings)

    replay_result = EvidenceEngine().collect(
        metrics=replay_metrics,
        trend=replay_trend,
        structural_swings=replay_structural_swings,
    )

    point_history.append(replay_result)

if not point_history:
    raise RuntimeError("No point-in-time replay snapshots were produced")

point_qualification = qualification_engine.evaluate(point_history)


# ---------------------------------------------------------
# Production point-in-time candidate
# ---------------------------------------------------------
# This is the ONLY candidate used for current-bar scoring and actionability.
# scan_to_index() owns the complete production decision path.
point_in_time_candidate = scanner.scan_to_index(
    metrics,
    TARGET_INDEX,
)


# ---------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------

print()
print("=" * 70)
print("SCANNER DIAGNOSTIC - CHRONOLOGICAL QUALIFICATION + CURRENT BAR")
print("=" * 70)
print("DIAGNOSTIC_VERSION = chronological-qualification-v7-separated-scopes")

target_week = metrics.iloc[TARGET_INDEX][COL_WEEK]

print()
print("TARGET")
print({
    "symbol": SYMBOL,
    "bar_index": TARGET_INDEX,
    "week": str(target_week),
})


# ---------------------------------------------------------
# 1. Historical qualification only
# ---------------------------------------------------------
print()
print("QUALIFICATION HISTORY - VALIDATION ONLY")

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
    "actionable_evidence": point_qualification.is_actionable_evidence,
    "reason": point_qualification.reason,
    "qualifying_codes": [str(code) for code in point_qualification.evidence_codes],
    "qualifying_bar_indices": list(point_qualification.evidence_bar_indices),
})


# ---------------------------------------------------------
# 2. Current-bar production decision
# ---------------------------------------------------------
print()
print("CURRENT BAR - PRODUCTION SCANNER PATH")

scores = point_in_time_candidate.professional.scores

print({
    "qualification": point_in_time_candidate.qualification,
    "actionable": point_in_time_candidate.actionable,
    "reason": point_in_time_candidate.reason,
})

print()
print("CURRENT BAR EVIDENCE")
print({
    "target_bar_evidence_codes": point_in_time_candidate.target_bar_evidence_codes,
    "campaign_evidence_codes": point_in_time_candidate.campaign_evidence_codes,
    "qualifying_evidence_codes": point_in_time_candidate.qualifying_evidence_codes,
    "scoring_evidence_codes": point_in_time_candidate.scoring_evidence_codes,
    "scoring_bar_index": point_in_time_candidate.scoring_bar_index,
})

print()
print("CURRENT PROFESSIONAL SCORE INPUTS")
print(score_inputs(scores))

print()
print("CURRENT CONFIDENCE DECOMPOSITION")
print(confidence_components(scores))

print()
print("CURRENT SCORE")
print({
    "professional_strength": point_in_time_candidate.professional.strength,
    "professional_weakness": point_in_time_candidate.professional.weakness,
    "net_strength": point_in_time_candidate.net_strength,
    "net_pressure": point_in_time_candidate.net_pressure,
    "confidence": point_in_time_candidate.confidence,
    "base_score": point_in_time_candidate.base_score,
})


# ---------------------------------------------------------
# 3. Explicit separation check
# ---------------------------------------------------------
print()
print("SCOPE SEPARATION CHECK")
print({
    "qualification_source": "chronological replay",
    "qualification_bars": list(point_qualification.evidence_bar_indices),
    "scoring_source": "production scan_to_index",
    "scoring_bar_index": point_in_time_candidate.scoring_bar_index,
    "current_target_bar": TARGET_INDEX,
    "historical_qualification_used_for_scoring": False,
})


# ---------------------------------------------------------
# 4. Final decision and rank
# ---------------------------------------------------------
print()
print("FINAL DECISION")
print({
    "actionable": point_in_time_candidate.actionable,
    "qualification": point_in_time_candidate.qualification,
    "base_score": point_in_time_candidate.base_score,
    "confidence": point_in_time_candidate.confidence,
    "reason": point_in_time_candidate.reason,
})

ranked = rank_candidates([point_in_time_candidate])

print()
print("RANKED ORDER")
for index, candidate in enumerate(ranked, start=1):
    print(
        index,
        {
            "qualification": candidate.qualification,
            "actionable": candidate.actionable,
            "base_score": candidate.base_score,
            "confidence": candidate.confidence,
            "scoring_bar_index": candidate.scoring_bar_index,
        },
    )

print()
print("=" * 70)
