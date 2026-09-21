from __future__ import annotations

import json

import pandas as pd

from audit.daily_event_confirmation_semantics import (
    build_confirmation_contract_rows,
    build_detector_confirmation_semantics_audit,
    write_detector_confirmation_semantics_audit,
)
from audit.daily_event_detector_correction_design import (
    build_detector_correction_design_audit,
)


def _confirmation_names_by_code() -> dict[str, tuple[str, ...]]:
    rows = build_confirmation_contract_rows()
    result: dict[str, list[tuple[int, str]]] = {}
    for row in rows:
        if row.requirement_kind != "CONFIRMATION":
            continue
        result.setdefault(row.code, []).append(
            (row.ordinal, row.requirement_name)
        )
    return {
        code: tuple(
            name for _, name in sorted(items)
        )
        for code, items in result.items()
    }


def _observation(
    *,
    code: str,
    bar_index: int,
    passed: tuple[str, ...],
    all_names: tuple[str, ...],
) -> dict[str, object]:
    passed_set = set(passed)
    failed = tuple(
        name for name in all_names if name not in passed_set
    )
    return {
        "symbol": "AAA.NS",
        "bar_index": bar_index,
        "session": f"2026-01-{bar_index:02d}T00:00:00",
        "code": code,
        "confirmation_count": len(all_names),
        "passed_confirmation_count": len(passed),
        "passed_confirmations": "|".join(passed),
        "failed_confirmations": "|".join(failed),
        "survives_any": bool(passed),
        "survives_strict_majority": (
            len(passed) * 2 > len(all_names)
        ),
        "survives_all": len(passed) == len(all_names),
    }


def _write_source_chain(tmp_path):
    l3_dir = tmp_path / "l3"
    l4b_dir = tmp_path / "l4b"
    l3_dir.mkdir()

    names = _confirmation_names_by_code()
    rows: list[dict[str, object]] = []
    index = 1
    for code in sorted(names):
        if code == "no_supply":
            continue
        event_index = 1 if code == "upthrust" else index
        rows.append(
            _observation(
                code=code,
                bar_index=event_index,
                passed=names[code],
                all_names=names[code],
            )
        )
        index += 1

    no_supply = names["no_supply"]
    rows.extend(
        (
            _observation(
                code="no_supply",
                bar_index=index,
                passed=("Weak Spread",),
                all_names=no_supply,
            ),
            _observation(
                code="no_supply",
                bar_index=index + 1,
                passed=("Weak Spread", "Volume Decreasing"),
                all_names=no_supply,
            ),
            _observation(
                code="no_supply",
                bar_index=index + 2,
                passed=("Weak Spread", "Weak Selling Result"),
                all_names=no_supply,
            ),
            _observation(
                code="no_supply",
                bar_index=index + 3,
                passed=no_supply,
                all_names=no_supply,
            ),
        )
    )

    observations = pd.DataFrame(rows)
    observations.to_csv(
        l3_dir / "daily_confirmation_observations.csv",
        index=False,
    )
    event_count = len(observations)
    summary = {
        "audit_id": "daily-event-confirmation-counterfactual-v1",
        "requested_symbol_count": 1,
        "succeeded_symbol_count": 1,
        "failed_symbol_count": 0,
        "baseline_event_count": event_count,
        "captured_event_count": event_count,
        "physical_observation_count": event_count,
        "duplicate_observation_count": 0,
        "identity_mismatch_count": 0,
        "bar_index_mismatch_count": 0,
        "source_lineage": {
            "snapshot_manifest_sha256": "a" * 64,
            "l1_summary_sha256": "b" * 64,
            "l1_emissions_sha256": "c" * 64,
            "l2_summary_sha256": "d" * 64,
        },
        "is_actionable": False,
    }
    (
        l3_dir / "daily_confirmation_counterfactual_summary.json"
    ).write_text(json.dumps(summary), encoding="utf-8")

    l4b = build_detector_confirmation_semantics_audit(l3_dir)
    write_detector_confirmation_semantics_audit(l4b, l4b_dir)
    return l3_dir, l4b_dir


def test_design_audit_detects_exact_three_contract_findings(
    tmp_path,
) -> None:
    l3_dir, l4b_dir = _write_source_chain(tmp_path)

    audit = build_detector_correction_design_audit(
        semantics_dir=l4b_dir,
        confirmation_dir=l3_dir,
    )

    assert audit.finding_count == 2
    assert audit.mandatory_collision_pair_count == 0
    assert audit.gate_candidate_count == 0
    assert audit.collision_projection_row_count == 0
    assert audit.correction_candidate_count == 3

    by_type = {item.issue_type: item for item in audit.findings}
    assert "IDENTICAL_MANDATORY_CONTRACT" not in by_type

    environment = by_type[
        "ENVIRONMENT_LABEL_PREDICATE_POLARITY_MISMATCH"
    ]
    assert environment.codes == ("no_supply",)
    assert environment.requirement_name == "Bullish Environment"
    assert environment.passed_expression == "ctx.is_bearish_environment()"

    redundant = by_type[
        "REDUNDANT_CONFIRMATION_IMPLIED_BY_MANDATORY"
    ]
    assert redundant.codes == ("no_supply",)
    assert redundant.requirement_name == "Weak Spread"
    assert redundant.related_requirement_name == "Narrow Spread"


def test_collision_design_is_empty_after_bc_ut_production_fix(
    tmp_path,
) -> None:
    l3_dir, l4b_dir = _write_source_chain(tmp_path)
    audit = build_detector_correction_design_audit(
        semantics_dir=l4b_dir,
        confirmation_dir=l3_dir,
    )

    assert audit.mandatory_collision_pair_count == 0
    assert audit.gate_candidates == ()
    assert audit.collision_rows == ()


def test_no_supply_candidates_separate_metadata_from_replay(
    tmp_path,
) -> None:
    l3_dir, l4b_dir = _write_source_chain(tmp_path)
    audit = build_detector_correction_design_audit(
        semantics_dir=l4b_dir,
        confirmation_dir=l3_dir,
    )

    by_id = {
        item.candidate_id: item
        for item in audit.correction_candidates
    }

    rename = by_id["no-supply-align-label-to-bearish-predicate"]
    assert rename.requires_replay is False
    assert rename.changes_current_emissions is False
    assert rename.current_event_count == 4
    assert rename.projected_event_count == 4

    predicate = by_id["no-supply-align-predicate-to-bullish-label"]
    assert predicate.requires_replay is True
    assert predicate.changes_current_emissions is None
    assert predicate.projected_event_count is None

    remove = by_id["no-supply-remove-redundant-weak-spread"]
    assert remove.requires_replay is False
    assert remove.changes_current_emissions is False
    assert remove.current_event_count == 4
    assert remove.projected_event_count == 4
    assert remove.projected_any_count == 3
    assert remove.projected_strict_majority_count == 1
    assert remove.projected_all_count == 1
