"""WF7C1 reproducible opposite-supported-thesis historical audit."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from audit.weekly_input_reproducibility_runner import (
    ReproducibleWeeklyFoundationStudy,
    run_reproducible_weekly_foundation_study,
)
from weekly_actionability_counterfactual import (
    WeeklyActionabilityCounterfactualEngine,
    WeeklyActionabilityCounterfactualInput,
)
from weekly_audit_input_reproducibility import (
    WeeklyAuditInputComparison,
    WeeklyAuditInputFingerprint,
    compare_weekly_audit_inputs,
)
from weekly_contradiction_reason_audit import WeeklyContradictionReasonAuditEngine
from weekly_opposite_supported_thesis_audit import (
    WeeklyOppositeMatchedSummary,
    WeeklyOppositeMetrics,
    WeeklyOppositeRegime,
    WeeklyOppositeSupportedObservation,
    WeeklyOppositeSupportedThesisAuditEngine,
    WeeklyOppositeSupportedThesisAuditReport,
)


DEFAULT_WF7C1_OUTPUT_DIR = Path("reports/weekly-foundation/wf7c1-latest")
DEFAULT_WF7C0_BASELINE_MANIFEST = Path(
    "reports/weekly-foundation/wf7c0-study-01/weekly_input_fingerprints.json"
)


@dataclass(frozen=True, slots=True)
class ReproducibleWeeklyOppositeSupportedStudy:
    report: WeeklyOppositeSupportedThesisAuditReport
    input_fingerprints: tuple[WeeklyAuditInputFingerprint, ...]
    fingerprint_comparison: WeeklyAuditInputComparison

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class WeeklyOppositeSupportedBundlePaths:
    summary_json: Path
    observations_csv: Path
    regime_summaries_csv: Path
    symbol_balanced_csv: Path
    matched_pairs_csv: Path
    matched_summaries_csv: Path
    unmatched_treatments_csv: Path
    input_fingerprints_csv: Path

    def as_dict(self) -> dict[str, str]:
        return {key: str(value) for key, value in asdict(self).items()}


def _enum_text(value: object) -> str:
    return str(getattr(value, "value", value))


def load_weekly_input_fingerprint_manifest(
    path: str | Path,
) -> tuple[WeeklyAuditInputFingerprint, ...]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    raw = payload.get("fingerprints")
    if not isinstance(raw, list) or not raw:
        raise ValueError("fingerprint manifest must contain a non-empty 'fingerprints' list")

    result: list[WeeklyAuditInputFingerprint] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("fingerprint manifest entries must be objects")
        result.append(
            WeeklyAuditInputFingerprint(
                symbol=str(item["symbol"]).strip().upper(),
                version=str(item["version"]),
                row_count=int(item["row_count"]),
                first_week=item.get("first_week"),
                last_week=item.get("last_week"),
                sha256=str(item["sha256"]),
                columns=tuple(str(column) for column in item["columns"]),
            )
        )
    return tuple(result)


def _comparison_error(comparison: WeeklyAuditInputComparison) -> str:
    parts: list[str] = []
    if comparison.missing_from_left:
        parts.append(f"missing_from_expected={comparison.missing_from_left}")
    if comparison.missing_from_right:
        parts.append(f"missing_from_current={comparison.missing_from_right}")
    if comparison.mismatches:
        parts.append(
            "mismatches="
            + repr(tuple((item.symbol, item.fields) for item in comparison.mismatches))
        )
    return "; ".join(parts) or "unknown fingerprint mismatch"


def run_reproducible_weekly_opposite_supported_study(
    symbols: Sequence[str] | Iterable[str],
    *,
    expected_fingerprints: Sequence[WeeklyAuditInputFingerprint],
    horizons_weeks: Iterable[int] = (5, 10, 15),
    out_of_sample_start_week: str | None = None,
) -> ReproducibleWeeklyOppositeSupportedStudy:
    """Run WF7C1 only when the completed-week inputs match the WF7C0 baseline."""

    reproducible: ReproducibleWeeklyFoundationStudy = (
        run_reproducible_weekly_foundation_study(
            symbols,
            horizons_weeks=horizons_weeks,
            out_of_sample_start_week=out_of_sample_start_week,
        )
    )
    comparison = compare_weekly_audit_inputs(
        tuple(expected_fingerprints),
        reproducible.input_fingerprints,
    )
    if not comparison.matches:
        raise ValueError(
            "WF7C1 input fingerprint mismatch; rerun WF7C0 before comparing logic: "
            + _comparison_error(comparison)
        )

    datasets = tuple(
        WeeklyActionabilityCounterfactualInput(
            symbol=item.symbol,
            audits=item.audits,
            prices=item.prices,
            out_of_sample_start_bar_index=item.out_of_sample_start_bar_index,
        )
        for item in reproducible.foundation.symbol_results
    )
    wf7a = WeeklyActionabilityCounterfactualEngine.audit(
        datasets=datasets,
        horizons_weeks=tuple(reproducible.foundation.horizons_weeks),
    )
    wf7b = WeeklyContradictionReasonAuditEngine.audit(counterfactual_report=wf7a)

    regimes: dict[tuple[str, int], WeeklyOppositeRegime] = {}
    for symbol_result in reproducible.foundation.symbol_results:
        for audit in symbol_result.audits:
            if audit.bar_index is None:
                continue
            regimes[(audit.symbol, audit.bar_index)] = WeeklyOppositeRegime(
                trend_direction=audit.trend_direction,
                trend_state=audit.trend_state,
                structural_pattern=audit.structural_pattern,
            )

    report = WeeklyOppositeSupportedThesisAuditEngine.audit(
        reason_report=wf7b,
        regimes=regimes,
    )
    return ReproducibleWeeklyOppositeSupportedStudy(
        report=report,
        input_fingerprints=reproducible.input_fingerprints,
        fingerprint_comparison=comparison,
    )


def _metrics_columns(metrics: WeeklyOppositeMetrics, prefix: str = "") -> dict[str, object]:
    return {
        f"{prefix}observation_count": metrics.observation_count,
        f"{prefix}complete_outcome_count": metrics.complete_outcome_count,
        f"{prefix}mean_close_return_pct": metrics.mean_close_return_pct,
        f"{prefix}median_close_return_pct": metrics.median_close_return_pct,
        f"{prefix}mean_mfe_pct": metrics.mean_mfe_pct,
        f"{prefix}mean_mae_pct": metrics.mean_mae_pct,
        f"{prefix}positive_close_return_count": metrics.positive_close_return_count,
        f"{prefix}non_positive_close_return_count": metrics.non_positive_close_return_count,
    }


def _outcome_columns(
    item: WeeklyOppositeSupportedObservation,
    prefix: str,
) -> dict[str, object]:
    row: dict[str, object] = {}
    for outcome in item.outcomes:
        stem = f"{prefix}_{outcome.horizon_weeks}w"
        row[f"{stem}_complete"] = outcome.complete
        row[f"{stem}_available_weeks"] = outcome.available_weeks
        row[f"{stem}_close_return_pct"] = outcome.close_return_pct
        row[f"{stem}_mfe_pct"] = outcome.maximum_favorable_excursion_pct
        row[f"{stem}_mae_pct"] = outcome.maximum_adverse_excursion_pct
    return row


def _observation_row(item: WeeklyOppositeSupportedObservation) -> dict[str, object]:
    row: dict[str, object] = {
        "symbol": item.symbol,
        "week": item.week,
        "bar_index": item.bar_index,
        "partition": _enum_text(item.partition),
        "legacy_direction": _enum_text(item.legacy_direction),
        "shadow_direction": _enum_text(item.shadow_direction),
        "reason_class": _enum_text(item.reason_class),
        "episode_id": item.episode_id,
        "trend_direction": _enum_text(item.regime.trend_direction),
        "trend_state": _enum_text(item.regime.trend_state),
        "structural_pattern": _enum_text(item.regime.structural_pattern),
        "is_opposite_supported": item.is_opposite_supported,
    }
    row.update(_outcome_columns(item, "outcome"))
    return row


def _matched_summary_row(item: WeeklyOppositeMatchedSummary) -> dict[str, object]:
    return {
        "horizon_weeks": item.horizon_weeks,
        "partition": _enum_text(item.partition),
        "legacy_direction": _enum_text(item.legacy_direction),
        "pair_count": item.pair_count,
        "complete_pair_count": item.complete_pair_count,
        "symbol_count": item.symbol_count,
        "treatment_mean_close_return_pct": item.treatment_mean_close_return_pct,
        "control_mean_close_return_pct": item.control_mean_close_return_pct,
        "mean_paired_close_delta_pct": item.mean_paired_close_delta_pct,
        "median_paired_close_delta_pct": item.median_paired_close_delta_pct,
        "symbol_balanced_mean_paired_close_delta_pct": (
            item.symbol_balanced_mean_paired_close_delta_pct
        ),
        "treatment_mean_mfe_pct": item.treatment_mean_mfe_pct,
        "control_mean_mfe_pct": item.control_mean_mfe_pct,
        "mean_paired_mfe_delta_pct": item.mean_paired_mfe_delta_pct,
        "treatment_mean_mae_pct": item.treatment_mean_mae_pct,
        "control_mean_mae_pct": item.control_mean_mae_pct,
        "mean_paired_mae_delta_pct": item.mean_paired_mae_delta_pct,
        "positive_paired_close_delta_count": item.positive_paired_close_delta_count,
        "non_positive_paired_close_delta_count": (
            item.non_positive_paired_close_delta_count
        ),
    }


def write_weekly_opposite_supported_bundle(
    study: ReproducibleWeeklyOppositeSupportedStudy,
    output_dir: str | Path = DEFAULT_WF7C1_OUTPUT_DIR,
) -> WeeklyOppositeSupportedBundlePaths:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = WeeklyOppositeSupportedBundlePaths(
        summary_json=root / "wf7c1_opposite_supported_summary.json",
        observations_csv=root / "wf7c1_opposite_supported_observations.csv",
        regime_summaries_csv=root / "wf7c1_opposite_supported_regime_summaries.csv",
        symbol_balanced_csv=root / "wf7c1_opposite_supported_symbol_balanced.csv",
        matched_pairs_csv=root / "wf7c1_opposite_supported_matched_pairs.csv",
        matched_summaries_csv=root / "wf7c1_opposite_supported_matched_summaries.csv",
        unmatched_treatments_csv=root / "wf7c1_opposite_supported_unmatched.csv",
        input_fingerprints_csv=root / "wf7c1_input_fingerprints.csv",
    )
    report = study.report
    treatments = tuple(item for item in report.observations if item.is_opposite_supported)
    payload = {
        "symbols": list(report.symbols),
        "symbol_count": len(report.symbols),
        "horizons_weeks": list(report.horizons_weeks),
        "episode_start_observations": len(report.observations),
        "opposite_supported_episodes": len(treatments),
        "matched_pairs": len(report.matched_pairs),
        "unmatched_treatments": len(report.unmatched_treatments),
        "fingerprint_match": study.fingerprint_comparison.matches,
        "is_actionable": False,
    }
    paths.summary_json.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    pd.DataFrame([_observation_row(item) for item in report.observations]).to_csv(
        paths.observations_csv,
        index=False,
    )

    regime_rows: list[dict[str, object]] = []
    for item in report.regime_summaries:
        row = {
            "horizon_weeks": item.horizon_weeks,
            "partition": _enum_text(item.partition),
            "legacy_direction": _enum_text(item.legacy_direction),
            "trend_direction": _enum_text(item.trend_direction),
            "trend_state": _enum_text(item.trend_state),
            "structural_pattern": _enum_text(item.structural_pattern),
        }
        row.update(_metrics_columns(item.metrics))
        regime_rows.append(row)
    pd.DataFrame(regime_rows).to_csv(paths.regime_summaries_csv, index=False)

    pd.DataFrame(
        [
            {
                "horizon_weeks": item.horizon_weeks,
                "partition": _enum_text(item.partition),
                "legacy_direction": _enum_text(item.legacy_direction),
                "symbol_count": item.symbol_count,
                "observation_count": item.observation_count,
                "complete_outcome_count": item.complete_outcome_count,
                "equal_weight_mean_close_return_pct": (
                    item.equal_weight_mean_close_return_pct
                ),
                "equal_weight_mean_mfe_pct": item.equal_weight_mean_mfe_pct,
                "equal_weight_mean_mae_pct": item.equal_weight_mean_mae_pct,
            }
            for item in report.symbol_balanced_summaries
        ]
    ).to_csv(paths.symbol_balanced_csv, index=False)

    pair_rows: list[dict[str, object]] = []
    for pair in report.matched_pairs:
        row = {
            "symbol": pair.treatment.symbol,
            "partition": _enum_text(pair.treatment.partition),
            "legacy_direction": _enum_text(pair.treatment.legacy_direction),
            "trend_direction": _enum_text(pair.treatment.regime.trend_direction),
            "trend_state": _enum_text(pair.treatment.regime.trend_state),
            "structural_pattern": _enum_text(pair.treatment.regime.structural_pattern),
            "treatment_week": pair.treatment.week,
            "treatment_bar_index": pair.treatment.bar_index,
            "treatment_episode_id": pair.treatment.episode_id,
            "control_week": pair.control.week,
            "control_bar_index": pair.control.bar_index,
            "control_episode_id": pair.control.episode_id,
            "control_reason_class": _enum_text(pair.control.reason_class),
            "bar_distance": pair.bar_distance,
        }
        row.update(_outcome_columns(pair.treatment, "treatment"))
        row.update(_outcome_columns(pair.control, "control"))
        for horizon in report.horizons_weeks:
            treatment = next(
                (
                    outcome
                    for outcome in pair.treatment.outcomes
                    if outcome.horizon_weeks == horizon
                ),
                None,
            )
            control = next(
                (
                    outcome
                    for outcome in pair.control.outcomes
                    if outcome.horizon_weeks == horizon
                ),
                None,
            )
            if (
                treatment is not None
                and control is not None
                and treatment.complete
                and control.complete
                and treatment.close_return_pct is not None
                and control.close_return_pct is not None
            ):
                row[f"paired_{horizon}w_close_delta_pct"] = (
                    treatment.close_return_pct - control.close_return_pct
                )
            else:
                row[f"paired_{horizon}w_close_delta_pct"] = None
        pair_rows.append(row)
    pd.DataFrame(pair_rows).to_csv(paths.matched_pairs_csv, index=False)

    pd.DataFrame(
        [_matched_summary_row(item) for item in report.matched_summaries]
    ).to_csv(paths.matched_summaries_csv, index=False)

    pd.DataFrame(
        [_observation_row(item) for item in report.unmatched_treatments]
    ).to_csv(paths.unmatched_treatments_csv, index=False)

    pd.DataFrame([asdict(item) for item in study.input_fingerprints]).to_csv(
        paths.input_fingerprints_csv,
        index=False,
    )
    return paths


def _parse_csv_strings(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _parse_csv_ints(value: str) -> tuple[int, ...]:
    return tuple(int(item) for item in _parse_csv_strings(value))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run reproducibility-gated WF7C1 opposite-supported-thesis audit. "
            "No production actionability is changed."
        )
    )
    parser.add_argument("--symbols", required=True, help="Comma-separated symbols.")
    parser.add_argument("--horizons", default="5,10,15")
    parser.add_argument("--out-of-sample-start-week", default=None)
    parser.add_argument(
        "--expected-input-fingerprints",
        default=str(DEFAULT_WF7C0_BASELINE_MANIFEST),
        help="WF7C0 JSON fingerprint manifest that the current run must exactly match.",
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_WF7C1_OUTPUT_DIR))
    args = parser.parse_args(argv)

    expected = load_weekly_input_fingerprint_manifest(args.expected_input_fingerprints)
    study = run_reproducible_weekly_opposite_supported_study(
        _parse_csv_strings(args.symbols),
        expected_fingerprints=expected,
        horizons_weeks=_parse_csv_ints(args.horizons),
        out_of_sample_start_week=args.out_of_sample_start_week,
    )
    paths = write_weekly_opposite_supported_bundle(study, args.output_dir)
    print(
        json.dumps(
            {
                "symbols": list(study.report.symbols),
                "horizons_weeks": list(study.report.horizons_weeks),
                "opposite_supported_episodes": sum(
                    item.is_opposite_supported for item in study.report.observations
                ),
                "matched_pairs": len(study.report.matched_pairs),
                "unmatched_treatments": len(study.report.unmatched_treatments),
                "fingerprint_match": study.fingerprint_comparison.matches,
                "is_actionable": False,
                "output_paths": paths.as_dict(),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DEFAULT_WF7C0_BASELINE_MANIFEST",
    "DEFAULT_WF7C1_OUTPUT_DIR",
    "ReproducibleWeeklyOppositeSupportedStudy",
    "WeeklyOppositeSupportedBundlePaths",
    "load_weekly_input_fingerprint_manifest",
    "run_reproducible_weekly_opposite_supported_study",
    "write_weekly_opposite_supported_bundle",
]
