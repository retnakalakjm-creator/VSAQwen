from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config
from data import daily_to_weekly, download_data
from debug.diagnose_shakeout_outcomes_recovery_anchor import inspect_symbol as validated_inspect_symbol
from engine.columns import COL_CLOSE, COL_WEEK
from evidence.engine import EvidenceEngine
from evidence.evidence_registry import build_evidence
from model.evidence_result_model import EvidenceResult
from models import EvidenceCategory, EvidenceCode, EvidenceDirection, Evidence
from professional.scoring_engine import ProfessionalScoringEngine
from trend import TrendAnalyzer

DEFAULT_SYMBOLS = (
    "BHARTIARTL.NS",
    "RELIANCE.NS",
    "HDFCBANK.NS",
    "ICICIBANK.NS",
    "INFY.NS",
    "TCS.NS",
    "SBIN.NS",
    "LT.NS",
)
WEIGHTS = (0.50, 0.60, 0.70, 0.80, 0.90, 1.00)
CONFIG_LOCK = Lock()
EPS = 1e-12


def professional_advantage(*, trend, evidence: EvidenceResult) -> float:
    scores = ProfessionalScoringEngine().calculate(
        trend=trend,
        evidence=evidence,
    ).scores
    return float(scores.strength - scores.weakness)


def make_shakeout(event: dict, weight: float) -> Evidence:
    return Evidence(
        code=EvidenceCode.SHAKEOUT,
        category=EvidenceCategory.DEMAND,
        direction=EvidenceDirection.BULLISH,
        strength=max(0.0, min(float(event["quality"]), 1.0)),
        weight=float(weight),
        observation="Shakeout",
        description="Validated recovery-anchored SHAKEOUT counterfactual for weight calibration.",
        bar_index=int(event["recovery_bar_index"]),
        week_beginning=str(event["recovery_week"]),
    )


def evaluate(event: dict, metrics, weight: float) -> float:
    recovery_index = int(event["recovery_bar_index"])
    replay = metrics.iloc[: recovery_index + 1].copy()
    trend = TrendAnalyzer().analyze(replay)
    structural_swings = tuple(trend.structure.structural_swings)
    evidence = EvidenceEngine().collect(
        metrics=replay,
        trend=trend,
        structural_swings=structural_swings,
    )

    base_items = tuple(
        item for item in evidence.evidence
        if item.code is not EvidenceCode.SHAKEOUT
    )
    synthetic = make_shakeout(event, weight)
    counterfactual = EvidenceResult(
        context=evidence.context,
        evidence=base_items + (synthetic,),
    )

    original_weights = config.DEMAND_EVIDENCE_WEIGHTS
    with CONFIG_LOCK:
        try:
            patched = dict(original_weights)
            patched[EvidenceCode.SHAKEOUT] = float(weight)
            config.DEMAND_EVIDENCE_WEIGHTS = patched
            return professional_advantage(
                trend=trend,
                evidence=counterfactual,
            )
        finally:
            config.DEMAND_EVIDENCE_WEIGHTS = original_weights


def baseline(event: dict, metrics) -> float:
    recovery_index = int(event["recovery_bar_index"])
    replay = metrics.iloc[: recovery_index + 1].copy()
    trend = TrendAnalyzer().analyze(replay)
    structural_swings = tuple(trend.structure.structural_swings)
    evidence = EvidenceEngine().collect(
        metrics=replay,
        trend=trend,
        structural_swings=structural_swings,
    )
    base_items = tuple(
        item for item in evidence.evidence
        if item.code is not EvidenceCode.SHAKEOUT
    )
    return professional_advantage(
        trend=trend,
        evidence=EvidenceResult(
            context=evidence.context,
            evidence=base_items,
        ),
    )


def classify(event: dict, delta: float) -> str:
    if abs(delta) <= EPS:
        return "UNCHANGED"
    if event["outcome"] == "POSITIVE_8_BAR":
        return "BENEFICIAL" if delta > 0 else "HARMFUL"
    if event["outcome"] == "NEGATIVE_8_BAR":
        return "HARMFUL" if delta > 0 else "BENEFICIAL"
    return "NEUTRAL"


def inspect_symbol(symbol: str) -> list[dict]:
    validated = validated_inspect_symbol(symbol)
    if not validated:
        return []

    daily = download_data(symbol)
    weekly = daily_to_weekly(daily)
    # validated_inspect_symbol already determines the exact 18-event population;
    # this metrics dataframe is used only for counterfactual scoring at those anchors.
    from metrics_engine import MetricsEngine
    metrics = MetricsEngine().calculate(weekly)

    rows: list[dict] = []
    for event in validated:
        recovery_index = int(event["recovery_bar_index"])
        base = baseline(event, metrics)
        deltas: dict[str, float] = {}
        classifications: dict[str, str] = {}
        for weight in WEIGHTS:
            score = evaluate(event, metrics, weight)
            delta = score - base
            key = f"{weight:.2f}"
            deltas[key] = delta
            classifications[key] = classify(event, delta)

        current_close = float(weekly.iloc[recovery_index][COL_CLOSE])
        future_close = float(weekly.iloc[recovery_index + 8][COL_CLOSE])
        forward_return = (future_close - current_close) / current_close

        rows.append({
            **event,
            "forward_return": forward_return,
            "baseline_advantage": base,
            "deltas": deltas,
            "classifications": classifications,
        })
    return rows


def stats(rows: list[dict], key: str) -> dict:
    beneficial = harmful = unchanged = neutral = 0
    deltas = []
    for row in rows:
        cls = row["classifications"][key]
        if cls == "BENEFICIAL":
            beneficial += 1
        elif cls == "HARMFUL":
            harmful += 1
        elif cls == "UNCHANGED":
            unchanged += 1
        else:
            neutral += 1
        deltas.append(row["deltas"][key])

    return {
        "beneficial_changes": beneficial,
        "harmful_changes": harmful,
        "unchanged": unchanged,
        "neutral": neutral,
        "net_benefit": beneficial - harmful,
        "benefit_harm_ratio": beneficial / harmful if harmful else float("inf"),
        "mean_advantage_delta": sum(deltas) / len(deltas) if deltas else 0.0,
        "decision_relevant_change_rate": (beneficial + harmful) / len(rows) if rows else 0.0,
    }


def main() -> None:
    symbols = tuple(sys.argv[1:]) or DEFAULT_SYMBOLS
    all_rows: list[dict] = []
    failures: list[dict] = []

    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {executor.submit(inspect_symbol, symbol): symbol for symbol in symbols}
        for future, symbol in futures.items():
            try:
                all_rows.extend(future.result())
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})

    print("SHAKEOUT RECOVERY-ANCHOR WEIGHT CALIBRATION SUMMARY")
    print({
        "events": len(all_rows),
        "symbols_with_events": len({r['symbol'] for r in all_rows}),
        "failures": failures,
    })

    for weight in WEIGHTS:
        key = f"{weight:.2f}"
        print({"weight": weight, **stats(all_rows, key)})

    print("SHAKEOUT RECOVERY-ANCHOR WEIGHT CALIBRATION LEAVE_ONE_OUT")
    for excluded in symbols:
        rows = [r for r in all_rows if r["symbol"] != excluded]
        print({
            "excluded_symbol": excluded,
            "events": len(rows),
            "weights": [
                {"weight": weight, **stats(rows, f"{weight:.2f}")}
                for weight in WEIGHTS
            ],
        })

    print("SHAKEOUT RECOVERY-ANCHOR WEIGHT CALIBRATION EVENTS")
    for row in all_rows:
        print(row)


if __name__ == "__main__":
    main()
