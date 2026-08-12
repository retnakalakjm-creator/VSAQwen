from collections import Counter

from data import download_data, daily_to_weekly
from metrics_engine import MetricsEngine
from evidence.engine import EvidenceEngine
from background.qualification import PatternQualificationEngine
from debug.confidence_diagnostics import confidence_components, score_inputs
from scanner import ScannerEngine
from trend import TrendAnalyzer
from engine.columns import COL_WEEK
from models import EvidenceCode


SYMBOL = "BHARTIARTL.NS"
TARGET_INDEX = 530


daily = download_data(SYMBOL)
weekly = daily_to_weekly(daily)
metrics = MetricsEngine().calculate(weekly)
scanner = ScannerEngine()
qualification_engine = PatternQualificationEngine()


# ---------------------------------------------------------
# Point-in-time chronological replay for qualification only
# ---------------------------------------------------------
point_history: list = []

for index in range(scanner.MIN_REPLAY_BARS, TARGET_INDEX + 1):
    replay_metrics = metrics.iloc[: index + 1].copy()
    replay_trend = TrendAnalyzer().analyze(replay_metrics)
    replay_structural_swings = list(replay_trend.structure.structural_swings)

    point_history.append(
        EvidenceEngine().collect(
            metrics=replay_metrics,
            trend=replay_trend,
            structural_swings=replay_structural_swings,
        )
    )

if not point_history:
    raise RuntimeError("No point-in-time replay snapshots were produced")

qualification = qualification_engine.evaluate(point_history)


# ---------------------------------------------------------
# Historical NO_SUPPLY distribution
# ---------------------------------------------------------
# This is deliberately based on point-in-time snapshots, so an event is counted
# only on the bar where it was actually observable.
no_supply_events = [
    item
    for result in point_history
    for item in result.evidence
    if item.code == EvidenceCode.NO_SUPPLY
]

no_supply_by_bar = Counter(
    item.bar_index
    for item in no_supply_events
)


# ---------------------------------------------------------
# Production current-bar decision
# ---------------------------------------------------------
# Do not manually reconstruct this candidate. Use the exact production
# ScannerEngine path so the diagnostic cannot accidentally score historical
# evidence as if it were current.
current_candidate = scanner.scan_to_index(metrics, TARGET_INDEX)


target_week = metrics.iloc[TARGET_INDEX][COL_WEEK]

print()
print("=" * 70)
print("SCANNER DIAGNOSTIC - PRODUCTION CURRENT BAR")
print("=" * 70)
print("DIAGNOSTIC_VERSION = production-current-bar-v2-no-supply-distribution")

print()
print("TARGET")
print({
    "symbol": SYMBOL,
    "bar_index": TARGET_INDEX,
    "week": str(target_week),
})

print()
print("QUALIFICATION HISTORY")
print({
    "qualification": qualification.qualification,
    "actionable_evidence": qualification.is_actionable_evidence,
    "reason": qualification.reason,
    "qualifying_codes": [str(code) for code in qualification.evidence_codes],
    "qualifying_bar_indices": list(qualification.evidence_bar_indices),
})

print()
print("HISTORICAL NO_SUPPLY DISTRIBUTION")
print({
    "count": len(no_supply_events),
    "unique_bars": len(no_supply_by_bar),
    "bar_indices": sorted(no_supply_by_bar),
    "events_per_bar": dict(sorted(no_supply_by_bar.items())),
})

print()
print("CURRENT BAR - PRODUCTION SCANNER PATH")
print({
    "qualification": current_candidate.qualification,
    "actionable": current_candidate.actionable,
    "reason": current_candidate.reason,
})

print()
print("CURRENT BAR EVIDENCE")
print({
    "target_bar_evidence_codes": current_candidate.target_bar_evidence_codes,
    "campaign_evidence_codes": current_candidate.campaign_evidence_codes,
    "qualifying_evidence_codes": current_candidate.qualifying_evidence_codes,
    "scoring_evidence_codes": current_candidate.scoring_evidence_codes,
    "scoring_bar_index": current_candidate.scoring_bar_index,
    "scoring_evidence_age": current_candidate.scoring_evidence_age,
    "used_fallback_evidence": current_candidate.used_fallback_evidence,
})

scores = current_candidate.professional.scores

print()
print("CURRENT PROFESSIONAL SCORE INPUTS")
print(score_inputs(scores))

print()
print("CURRENT CONFIDENCE DECOMPOSITION")
print(confidence_components(scores))

print()
print("CURRENT SCORE")
print({
    "professional_strength": current_candidate.professional.strength,
    "professional_weakness": current_candidate.professional.weakness,
    "net_strength": current_candidate.net_strength,
    "net_pressure": current_candidate.net_pressure,
    "confidence": current_candidate.confidence,
    "base_score": current_candidate.base_score,
})

print()
print("SCOPE SEPARATION CHECK")
print({
    "qualification_source": "chronological replay",
    "qualification_bars": list(qualification.evidence_bar_indices),
    "scoring_source": "production scan_to_index",
    "scoring_bar_index": current_candidate.scoring_bar_index,
    "current_target_bar": TARGET_INDEX,
    "historical_qualification_used_for_scoring": False,
})

print()
print("=" * 70)
