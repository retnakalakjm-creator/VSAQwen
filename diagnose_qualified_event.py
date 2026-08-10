from data import download_data, daily_to_weekly
from metrics_engine import MetricsEngine
from trend import TrendAnalyzer
from evidence.engine import EvidenceEngine
from professional.scoring_engine import ProfessionalScoringEngine
from background.qualification import PatternQualificationEngine, PatternQualification
from models import EvidenceCategory


SYMBOL = "BHARTIARTL.NS"


def _evidence_details(items):
    return [
        {
            "bar_index": item.bar_index,
            "week": item.week_beginning,
            "code": str(item.code),
            "category": str(item.category),
            "direction": str(item.direction),
            "strength": item.strength,
            "weight": item.weight,
            "quality": item.quality,
            "test_index": item.test_index,
            "recovery_index": item.recovery_index,
        }
        for item in items
    ]


def _structural_evidence(result):
    return tuple(
        item
        for item in result.evidence
        if item.category == EvidenceCategory.TREND
        and str(item.code).startswith("structural_")
    )


def _historical_structural_evidence(history):
    return tuple(
        item
        for result in history
        for item in _structural_evidence(result)
    )


def _structural_swing_summary(structural_swings):
    summary = []

    for structural in structural_swings:
        swing = structural.swing
        summary.append({
            "bar_index": swing.bar_index,
            "confirmation_index": swing.confirmation_index,
            "week": swing.week_beginning,
            "type": str(swing.type),
            "price": swing.price,
            "label": (
                str(swing.label)
                if swing.label is not None
                else None
            ),
            "grade": str(structural.grade),
            "is_failed": structural.is_failed,
            "score": structural.evaluation.structure.score.overall,
        })

    return summary


def _qualifying_swing_summary(structural_swings, bar_indices):
    qualifying_indices = set(bar_indices)
    summary = []

    for structural in structural_swings:
        swing = structural.swing
        if swing.confirmation_index not in qualifying_indices:
            continue

        summary.append({
            "event_bar_index": swing.confirmation_index,
            "swing_bar_index": swing.bar_index,
            "confirmation_index": swing.confirmation_index,
            "week": swing.week_beginning,
            "type": str(swing.type),
            "price": swing.price,
            "label": (
                str(swing.label)
                if swing.label is not None
                else None
            ),
            "grade": str(structural.grade),
            "is_failed": structural.is_failed,
            "score": structural.evaluation.structure.score.overall,
        })

    return sorted(summary, key=lambda item: item["event_bar_index"])


daily = download_data(SYMBOL)
weekly = daily_to_weekly(daily)
metrics = MetricsEngine().calculate(weekly)

print()
print("=" * 70)
print("SEARCHING FOR ALL PERSISTENT STRUCTURAL QUALIFICATION CHANGES")
print("=" * 70)

history = []
qualification_engine = PatternQualificationEngine()
previous_qualification = PatternQualification.UNQUALIFIED
state_change_count = 0

for target_index in range(20, len(metrics)):
    replay_metrics = metrics.iloc[:target_index + 1].copy()

    trend = TrendAnalyzer().analyze(replay_metrics)
    structure = trend.structure
    structural_swings = list(structure.structural_swings)

    result = EvidenceEngine().collect(
        metrics=replay_metrics,
        trend=trend,
        structural_swings=structural_swings,
    )

    structural_evidence = _structural_evidence(result)

    if not structural_evidence:
        continue

    history.append(result)
    qualification = qualification_engine.evaluate(history)

    if qualification.qualification == previous_qualification:
        continue

    previous_qualification = qualification.qualification
    state_change_count += 1

    professional = ProfessionalScoringEngine().calculate(
        trend=trend,
        evidence=result,
    )
    scores = professional.scores
    event_week = structural_evidence[-1].week_beginning

    print()
    print("QUALIFICATION STATE CHANGE")
    print({
        "state_change": state_change_count,
        "bar_index": target_index,
        "week": event_week,
        "qualification": qualification.qualification,
        "actionable": qualification.is_actionable_evidence,
        "reason": qualification.reason,
        "qualifying_codes": [str(code) for code in qualification.evidence_codes],
        "qualifying_bar_indices": list(qualification.evidence_bar_indices),
        "trend_state": structure.state,
        "trend_direction": structure.direction,
        "trend_strength": structure.strength,
        "trend_confidence": structure.confidence,
        "swing_count": structure.swing_count,
        "evidence_count": result.count,
        "professional_strength": scores.strength,
        "professional_weakness": scores.weakness,
        "net_strength": scores.strength - scores.weakness,
        "net_pressure": scores.demand - scores.supply,
        "confidence": professional.confidence,
    })

    print()
    print("QUALIFYING EVENTS")
    historical_evidence = _historical_structural_evidence(history)

    for code, bar_index in zip(
        qualification.evidence_codes,
        qualification.evidence_bar_indices,
    ):
        event = next(
            (
                item
                for item in historical_evidence
                if item.bar_index == bar_index
                and item.code == code
            ),
            None,
        )

        if event is None:
            print({
                "bar_index": bar_index,
                "code": str(code),
                "status": "QUALIFYING EVENT NOT PRESENT IN REPLAY HISTORY",
            })
            continue

        print({
            "bar_index": event.bar_index,
            "week": event.week_beginning,
            "code": str(event.code),
            "direction": str(event.direction),
            "strength": event.strength,
            "weight": event.weight,
            "quality": event.quality,
        })

    print()
    print("PERSISTENCE")
    qualifying_bars = list(qualification.evidence_bar_indices)
    print({
        "qualifying_periods": len(qualifying_bars),
        "bar_indices": qualifying_bars,
        "spacing": [
            right - left
            for left, right in zip(qualifying_bars, qualifying_bars[1:])
        ],
        "minimum_spacing": qualification_engine.MIN_EVENT_SPACING_BARS,
        "qualification": qualification.qualification,
        "actionable": qualification.is_actionable_evidence,
    })

    print()
    print("CURRENT STRUCTURAL EVIDENCE")
    for item in _evidence_details(structural_evidence):
        print(item)

    if qualification.qualification == PatternQualification.UNQUALIFIED:
        continue

    print()
    print("QUALIFYING EVENT SWINGS")
    for swing in _qualifying_swing_summary(
        structural_swings,
        qualification.evidence_bar_indices,
    ):
        print(swing)

    print()
    print("STRUCTURAL HISTORY")
    for swing in _structural_swing_summary(structural_swings):
        print(swing)

print()
print("=" * 70)
print("QUALIFICATION SEARCH COMPLETE")
print("=" * 70)
print({
    "symbol": SYMBOL,
    "state_changes": state_change_count,
    "snapshots": len(metrics),
    "structural_replay_snapshots": len(history),
})
