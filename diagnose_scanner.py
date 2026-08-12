from collections import Counter

from data import download_data, daily_to_weekly
from metrics_engine import MetricsEngine
from evidence.engine import EvidenceEngine
from background.qualification import PatternQualificationEngine
from debug.confidence_diagnostics import confidence_components, score_inputs
from scanner import ScannerEngine
from trend import TrendAnalyzer
from engine.columns import COL_WEEK, COL_CLOSE
from models import EvidenceCode


SYMBOL = "BHARTIARTL.NS"
TARGET_INDEX = 530
CONTEXT_WINDOW = 5
CONFIRMATION_WINDOW = 12
FORWARD_HORIZONS = (1, 2, 4, 8)

# Only an independent bullish event counts as confirmation.
# Supply-drying/no-supply observations do not confirm themselves.
BULLISH_CONFIRMATION_CODES = {
    EvidenceCode.SELLING_CLIMAX,
    EvidenceCode.TEST,
    EvidenceCode.SHAKEOUT,
    EvidenceCode.SPRING,
}


daily = download_data(SYMBOL)
weekly = daily_to_weekly(daily)
metrics = MetricsEngine().calculate(weekly)
scanner = ScannerEngine()
qualification_engine = PatternQualificationEngine()

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

no_supply_events = [
    item
    for result in point_history
    for item in result.evidence
    if item.code == EvidenceCode.NO_SUPPLY
]

no_supply_by_bar = Counter(item.bar_index for item in no_supply_events)


def evidence_codes_for_bar(bar_index: int) -> tuple[str, ...]:
    history_index = bar_index - scanner.MIN_REPLAY_BARS
    if history_index < 0 or history_index >= len(point_history):
        return ()

    return tuple(
        str(item.code)
        for item in point_history[history_index].evidence
        if item.bar_index == bar_index
    )


def no_supply_context(bar_index: int) -> dict:
    start = max(scanner.MIN_REPLAY_BARS, bar_index - CONTEXT_WINDOW)
    end = min(TARGET_INDEX, bar_index + CONTEXT_WINDOW)

    local_evidence = {
        index: evidence_codes_for_bar(index)
        for index in range(start, end + 1)
        if evidence_codes_for_bar(index)
    }

    close = float(metrics.iloc[bar_index][COL_CLOSE])
    forward_returns: dict[int, float | None] = {}
    for horizon in FORWARD_HORIZONS:
        future_index = bar_index + horizon
        future_close = (
            float(metrics.iloc[future_index][COL_CLOSE])
            if future_index < len(metrics)
            else None
        )
        forward_returns[horizon] = (
            (future_close / close) - 1.0
            if future_close is not None
            else None
        )

    trend = TrendAnalyzer().analyze(metrics.iloc[: bar_index + 1].copy())
    event = next(item for item in no_supply_events if item.bar_index == bar_index)

    first_bullish_vsa_confirmation = None
    first_structural_improvement = None
    first_supply_reappearance = None
    future_evidence: dict[int, tuple[str, ...]] = {}

    upper = min(
        bar_index + CONFIRMATION_WINDOW,
        len(point_history) + scanner.MIN_REPLAY_BARS - 1,
    )

    bullish_names = {str(code) for code in BULLISH_CONFIRMATION_CODES}
    supply_names = {
        str(EvidenceCode.INCREASING_SUPPLY),
        str(EvidenceCode.SUPPLY_COMING_IN),
        str(EvidenceCode.HIDDEN_SUPPLY),
        str(EvidenceCode.BUYING_CLIMAX),
        str(EvidenceCode.UPTHRUST),
    }

    for future_bar in range(bar_index + 1, upper + 1):
        codes = evidence_codes_for_bar(future_bar)
        if codes:
            future_evidence[future_bar] = codes

        if first_bullish_vsa_confirmation is None:
            bullish_codes = tuple(code for code in codes if code in bullish_names)
            if bullish_codes:
                first_bullish_vsa_confirmation = {
                    "bar_index": future_bar,
                    "codes": bullish_codes,
                }

        if first_structural_improvement is None and str(
            EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING
        ) in codes:
            first_structural_improvement = future_bar

        if first_supply_reappearance is None and any(
            code in supply_names for code in codes
        ):
            first_supply_reappearance = future_bar

    first_confirmation = first_bullish_vsa_confirmation
    if first_confirmation is None and first_structural_improvement is not None:
        first_confirmation = {
            "bar_index": first_structural_improvement,
            "codes": (str(EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING),),
        }

    return {
        "bar_index": bar_index,
        "week": str(metrics.iloc[bar_index][COL_WEEK]),
        "close": close,
        "no_supply_strength": event.strength,
        "no_supply_quality": event.quality,
        "no_supply_direction": str(event.direction),
        "trend_direction": str(trend.structure.direction),
        "trend_state": str(trend.structure.state),
        "nearby_evidence": local_evidence,
        "confirmation_window": CONFIRMATION_WINDOW,
        "first_confirmation": first_confirmation,
        "first_bullish_vsa_confirmation": first_bullish_vsa_confirmation,
        "first_structural_improvement": first_structural_improvement,
        "first_supply_reappearance": first_supply_reappearance,
        "future_evidence": future_evidence,
        "forward_returns": forward_returns,
    }


no_supply_contexts = [no_supply_context(index) for index in sorted(no_supply_by_bar)]
current_candidate = scanner.scan_to_index(metrics, TARGET_INDEX)
target_week = metrics.iloc[TARGET_INDEX][COL_WEEK]

print("\n" + "=" * 70)
print("SCANNER DIAGNOSTIC - NO_SUPPLY CONFIRMATION BEHAVIOR")
print("=" * 70)
print("DIAGNOSTIC_VERSION = production-current-bar-v5-no-supply-distinct-confirmation")

print("\nTARGET")
print({"symbol": SYMBOL, "bar_index": TARGET_INDEX, "week": str(target_week)})

print("\nQUALIFICATION HISTORY")
print({
    "qualification": qualification.qualification,
    "actionable_evidence": qualification.is_actionable_evidence,
    "reason": qualification.reason,
    "qualifying_codes": [str(code) for code in qualification.evidence_codes],
    "qualifying_bar_indices": list(qualification.evidence_bar_indices),
})

print("\nHISTORICAL NO_SUPPLY DISTRIBUTION")
print({
    "count": len(no_supply_events),
    "unique_bars": len(no_supply_by_bar),
    "bar_indices": sorted(no_supply_by_bar),
    "events_per_bar": dict(sorted(no_supply_by_bar.items())),
})

print("\nNO_SUPPLY CONFIRMATION BEHAVIOR")
for context in no_supply_contexts:
    print(context)

confirmed = [context for context in no_supply_contexts if context["first_confirmation"] is not None]
print("\nNO_SUPPLY CONFIRMATION SUMMARY")
print({
    "no_supply_count": len(no_supply_contexts),
    "confirmed_count": len(confirmed),
    "unconfirmed_count": len(no_supply_contexts) - len(confirmed),
    "confirmed_bars": [item["bar_index"] for item in confirmed],
    "confirmation_bars": {
        item["bar_index"]: item["first_confirmation"]["bar_index"]
        for item in confirmed
    },
    "supply_reappearance_bars": {
        item["bar_index"]: item["first_supply_reappearance"]
        for item in no_supply_contexts
    },
})

print("\nCURRENT BAR - PRODUCTION SCANNER PATH")
print({
    "qualification": current_candidate.qualification,
    "actionable": current_candidate.actionable,
    "reason": current_candidate.reason,
})

print("\nCURRENT BAR EVIDENCE")
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
print("\nCURRENT PROFESSIONAL SCORE INPUTS")
print(score_inputs(scores))
print("\nCURRENT CONFIDENCE DECOMPOSITION")
print(confidence_components(scores))
print("\nCURRENT SCORE")
print({
    "professional_strength": current_candidate.professional.strength,
    "professional_weakness": current_candidate.professional.weakness,
    "net_strength": current_candidate.net_strength,
    "net_pressure": current_candidate.net_pressure,
    "confidence": current_candidate.confidence,
    "base_score": current_candidate.base_score,
})

print("\nSCOPE SEPARATION CHECK")
print({
    "qualification_source": "chronological replay",
    "qualification_bars": list(qualification.evidence_bar_indices),
    "scoring_source": "production scan_to_index",
    "scoring_bar_index": current_candidate.scoring_bar_index,
    "current_target_bar": TARGET_INDEX,
    "historical_qualification_used_for_scoring": False,
})
print("\n" + "=" * 70)
