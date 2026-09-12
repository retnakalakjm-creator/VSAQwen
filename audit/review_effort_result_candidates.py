"""Review Effort/Result audit consensus candidates.

This module is audit/report only. It ranks consensus rows that are already
produced by the Effort/Result decision-value audit and summarizes which cohorts
should enter manual calibration-design review. It does not change detector
activation, scoring, ranking, actionability, scanner state, persistence, or any
broker/order behavior.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from audit.audit_effort_result_decision_value import (
    CONSENSUS_CANDIDATE,
    CONSENSUS_INCONSISTENT_DIRECTION,
    CONSENSUS_INSUFFICIENT_SAMPLE,
    CONSENSUS_OBSERVATION_ONLY,
    audit,
)

REPORT_TYPE = "effort_result_candidate_review"
REPORT_SCHEMA_VERSION = 1

EFFORT_RESULT_REVIEW_SCOPES = frozenset(
    {
        "effort_result_event",
        "effort_result_event_plus_relationship",
        "effort_result_relationship",
        "effort_result_relationship_plus_event",
    }
)

CONSENSUS_STATUS_ORDER = {
    CONSENSUS_CANDIDATE: 0,
    CONSENSUS_INCONSISTENT_DIRECTION: 1,
    CONSENSUS_INSUFFICIENT_SAMPLE: 2,
    CONSENSUS_OBSERVATION_ONLY: 3,
}

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2, "blocked": 3}


def build_candidate_review_report(
    report: Mapping[str, Any],
    *,
    max_candidates: int | None = None,
) -> dict[str, object]:
    """Build a manual-review report from an Effort/Result audit report.

    A candidate in this report is permission for manual calibration-design
    review only. Production scoring, ranking, actionability, and detector
    activation remain denied and require a separate production PR.
    """

    if max_candidates is not None and max_candidates <= 0:
        raise ValueError("max_candidates must be positive when provided")

    rows = [
        _review_row(row)
        for row in report.get("readiness_consensus", []) or []
        if _is_effort_result_review_scope(row)
    ]
    all_candidates = [
        row for row in rows if row["consensus"] == CONSENSUS_CANDIDATE
    ]
    blocked_rows = [row for row in rows if row["consensus"] != CONSENSUS_CANDIDATE]

    all_candidates.sort(key=_candidate_sort_key)
    blocked_rows.sort(key=_blocked_sort_key)
    candidates = (
        all_candidates[:max_candidates]
        if max_candidates is not None
        else all_candidates
    )

    return {
        "report_type": REPORT_TYPE,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "source": report.get("source"),
        "rows": int(report.get("rows", 0)),
        "outcome_rows": int(report.get("outcome_rows", 0)),
        "horizons": _int_list(report.get("horizons", [])),
        "thresholds": report.get("thresholds", {}),
        "total_consensus_rows": len(rows),
        "total_candidate_count": len(all_candidates),
        "candidate_count": len(candidates),
        "blocked_count": len(blocked_rows),
        "calibration_design_candidates": candidates,
        "blocked_or_observation_only": blocked_rows,
        "audit_only": True,
        "may_change_scoring": False,
        "may_change_ranking": False,
        "may_change_actionability": False,
        "may_activate_detector": False,
        "requires_manual_case_review": True,
        "requires_separate_production_pr": True,
    }


def _is_effort_result_review_scope(row: Mapping[str, Any]) -> bool:
    return row.get("scope") in EFFORT_RESULT_REVIEW_SCOPES


def _review_row(row: Mapping[str, Any]) -> dict[str, object]:
    candidate_horizons = _int_list(row.get("candidate_horizons", []))
    horizons_seen = _int_list(row.get("horizons_seen", []))
    consensus = str(row.get("consensus", ""))
    candidate_bars = int(row.get("candidate_bars", 0))

    return {
        "scope": str(row.get("scope", "")),
        "condition": str(row.get("condition", "")),
        "consensus": consensus,
        "priority": _review_priority(
            consensus=consensus,
            candidate_direction=str(row.get("candidate_direction", "")),
            candidate_horizons=candidate_horizons,
            candidate_bars=candidate_bars,
        ),
        "candidate_direction": str(row.get("candidate_direction", "")),
        "candidate_horizons": candidate_horizons,
        "candidate_horizon_count": len(candidate_horizons),
        "horizons_seen": horizons_seen,
        "candidate_bars": candidate_bars,
        "reason": str(row.get("reason", "")),
        "may_change_scoring": False,
        "may_change_ranking": False,
        "may_change_actionability": False,
        "may_activate_detector": False,
        "requires_manual_case_review": True,
        "requires_separate_production_pr": True,
    }


def _review_priority(
    *,
    consensus: str,
    candidate_direction: str,
    candidate_horizons: list[int],
    candidate_bars: int,
) -> str:
    if consensus != CONSENSUS_CANDIDATE:
        return "blocked"
    if (
        candidate_direction in {"positive", "negative"}
        and len(candidate_horizons) >= 3
        and candidate_bars >= 100
    ):
        return "high"
    if len(candidate_horizons) >= 2:
        return "medium"
    return "low"


def _candidate_sort_key(row: Mapping[str, Any]) -> tuple[int, int, int, str, str]:
    return (
        PRIORITY_ORDER.get(str(row.get("priority")), 99),
        -int(row.get("candidate_horizon_count", 0)),
        -int(row.get("candidate_bars", 0)),
        str(row.get("scope", "")),
        str(row.get("condition", "")),
    )


def _blocked_sort_key(row: Mapping[str, Any]) -> tuple[int, int, str, str]:
    return (
        CONSENSUS_STATUS_ORDER.get(str(row.get("consensus")), 99),
        -int(row.get("candidate_bars", 0)),
        str(row.get("scope", "")),
        str(row.get("condition", "")),
    )


def _int_list(value: object) -> list[int]:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        return []
    return sorted({int(item) for item in value})


def _parse_horizons(value: str) -> tuple[int, ...]:
    horizons = tuple(int(part.strip()) for part in value.split(",") if part.strip())
    if not horizons:
        raise ValueError("at least one horizon is required")
    return horizons


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Review Effort/Result audit consensus candidates."
    )
    parser.add_argument("path", type=Path)
    parser.add_argument("--horizons", default="1,2,4")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-candidates", type=int)
    parser.add_argument("--min-readiness-bars", type=int, default=10)
    parser.add_argument("--min-readiness-abs-delta", type=float, default=0.005)
    parser.add_argument("--min-consensus-horizons", type=int, default=2)
    parser.add_argument("--min-consensus-candidate-bars", type=int, default=20)
    args = parser.parse_args()

    audit_report = audit(
        args.path,
        horizons=_parse_horizons(args.horizons),
        min_readiness_bars=args.min_readiness_bars,
        min_readiness_abs_delta=args.min_readiness_abs_delta,
        min_consensus_horizons=args.min_consensus_horizons,
        min_consensus_candidate_bars=args.min_consensus_candidate_bars,
    )
    review_report = build_candidate_review_report(
        audit_report,
        max_candidates=args.max_candidates,
    )
    rendered = json.dumps(review_report, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
