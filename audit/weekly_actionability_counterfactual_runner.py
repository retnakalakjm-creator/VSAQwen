"""Historical runner for the WF7A legacy-actionability counterfactual audit.

This command reuses the WF1-WF6 weekly-foundation historical study and then
simulates transparent *withholding* policies on legacy-actionable weeks.  It is
analysis-only: no production scanner decision is changed.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from audit.weekly_foundation_runner import run_weekly_foundation_historical_study
from weekly_actionability_counterfactual import (
    WeeklyActionabilityCounterfactualEngine,
    WeeklyActionabilityCounterfactualInput,
    WeeklyActionabilityCounterfactualReport,
    WeeklyCounterfactualCohortMetrics,
)


DEFAULT_COUNTERFACTUAL_OUTPUT_DIR = Path("reports/weekly-foundation/wf7a-latest")


@dataclass(frozen=True, slots=True)
class WeeklyCounterfactualBundlePaths:
    summary_json: Path
    observations_csv: Path
    summaries_csv: Path
    leave_one_symbol_out_csv: Path

    def as_dict(self) -> dict[str, str]:
        return {
            "summary_json": str(self.summary_json),
            "observations_csv": str(self.observations_csv),
            "summaries_csv": str(self.summaries_csv),
            "leave_one_symbol_out_csv": str(self.leave_one_symbol_out_csv),
        }


def run_weekly_actionability_counterfactual_study(
    symbols: Sequence[str],
    *,
    horizons_weeks: Sequence[int] = WeeklyActionabilityCounterfactualEngine.DEFAULT_HORIZONS,
    out_of_sample_start_week: str | None = None,
) -> WeeklyActionabilityCounterfactualReport:
    """Run the existing historical stack, then evaluate WF7A suppression policies."""

    foundation = run_weekly_foundation_historical_study(
        symbols,
        horizons_weeks=horizons_weeks,
        out_of_sample_start_week=out_of_sample_start_week,
    )
    datasets = tuple(
        WeeklyActionabilityCounterfactualInput(
            symbol=item.symbol,
            audits=item.audits,
            prices=item.prices,
            out_of_sample_start_bar_index=item.out_of_sample_start_bar_index,
        )
        for item in foundation.symbol_results
    )
    return WeeklyActionabilityCounterfactualEngine.audit(
        datasets=datasets,
        horizons_weeks=horizons_weeks,
    )


def _enum_text(value: object) -> str:
    return str(getattr(value, "value", value))


def _cohort_columns(
    cohort: WeeklyCounterfactualCohortMetrics,
    prefix: str,
) -> dict[str, object]:
    return {
        f"{prefix}_observation_count": cohort.observation_count,
        f"{prefix}_complete_outcome_count": cohort.complete_outcome_count,
        f"{prefix}_mean_close_return_pct": cohort.mean_close_return_pct,
        f"{prefix}_median_close_return_pct": cohort.median_close_return_pct,
        f"{prefix}_mean_mfe_pct": cohort.mean_mfe_pct,
        f"{prefix}_mean_mae_pct": cohort.mean_mae_pct,
        f"{prefix}_positive_close_return_count": cohort.positive_close_return_count,
        f"{prefix}_non_positive_close_return_count": cohort.non_positive_close_return_count,
    }


def _observations_frame(report: WeeklyActionabilityCounterfactualReport) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for item in report.observations:
        row: dict[str, object] = {
            "symbol": item.symbol,
            "week": item.week,
            "bar_index": item.bar_index,
            "policy": _enum_text(item.policy),
            "partition": _enum_text(item.partition),
            "legacy_direction": _enum_text(item.legacy_direction),
            "shadow_state": _enum_text(item.shadow_state),
            "shadow_direction": _enum_text(item.shadow_direction),
            "disposition": _enum_text(item.disposition),
            "reasons": "|".join(_enum_text(reason) for reason in item.reasons),
        }
        for outcome in item.outcomes:
            prefix = f"outcome_{outcome.horizon_weeks}w"
            row[f"{prefix}_complete"] = outcome.complete
            row[f"{prefix}_available_weeks"] = outcome.available_weeks
            row[f"{prefix}_close_return_pct"] = outcome.close_return_pct
            row[f"{prefix}_mfe_pct"] = outcome.maximum_favorable_excursion_pct
            row[f"{prefix}_mae_pct"] = outcome.maximum_adverse_excursion_pct
        rows.append(row)
    return pd.DataFrame(rows)


def _summaries_frame(report: WeeklyActionabilityCounterfactualReport) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for item in report.summaries:
        row: dict[str, object] = {
            "policy": _enum_text(item.policy),
            "horizon_weeks": item.horizon_weeks,
            "partition": _enum_text(item.partition),
            "retained_minus_baseline_mean_close_pct": (
                item.retained_minus_baseline_mean_close_pct
            ),
            "retained_minus_suppressed_mean_close_pct": (
                item.retained_minus_suppressed_mean_close_pct
            ),
            "retained_minus_suppressed_mean_mfe_pct": (
                item.retained_minus_suppressed_mean_mfe_pct
            ),
            "retained_minus_suppressed_mean_mae_pct": (
                item.retained_minus_suppressed_mean_mae_pct
            ),
        }
        row.update(_cohort_columns(item.baseline, "baseline"))
        row.update(_cohort_columns(item.retained, "retained"))
        row.update(_cohort_columns(item.suppressed, "suppressed"))
        rows.append(row)
    return pd.DataFrame(rows)


def _leave_one_symbol_out_frame(
    report: WeeklyActionabilityCounterfactualReport,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for item in report.leave_one_symbol_out:
        row: dict[str, object] = {
            "policy": _enum_text(item.policy),
            "horizon_weeks": item.horizon_weeks,
            "held_out_symbol": item.held_out_symbol,
            "held_out_retained_minus_suppressed_mean_close_pct": (
                item.held_out_retained_minus_suppressed_mean_close_pct
            ),
            "other_symbols_retained_minus_suppressed_mean_close_pct": (
                item.other_symbols_retained_minus_suppressed_mean_close_pct
            ),
        }
        row.update(_cohort_columns(item.held_out_retained, "held_out_retained"))
        row.update(_cohort_columns(item.held_out_suppressed, "held_out_suppressed"))
        row.update(_cohort_columns(item.other_symbols_retained, "other_symbols_retained"))
        row.update(_cohort_columns(item.other_symbols_suppressed, "other_symbols_suppressed"))
        rows.append(row)
    return pd.DataFrame(rows)


def write_weekly_actionability_counterfactual_bundle(
    report: WeeklyActionabilityCounterfactualReport,
    output_dir: str | Path,
) -> WeeklyCounterfactualBundlePaths:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    paths = WeeklyCounterfactualBundlePaths(
        summary_json=destination / "wf7a_counterfactual_summary.json",
        observations_csv=destination / "wf7a_counterfactual_observations.csv",
        summaries_csv=destination / "wf7a_counterfactual_summaries.csv",
        leave_one_symbol_out_csv=destination / "wf7a_counterfactual_leave_one_symbol_out.csv",
    )

    policy_counts: dict[str, dict[str, int]] = {}
    for policy in sorted({item.policy for item in report.observations}, key=str):
        items = tuple(item for item in report.observations if item.policy is policy)
        policy_counts[_enum_text(policy)] = {
            "legacy_actionable_observations": len(items),
            "retained": sum(not item.suppressed for item in items),
            "suppressed": sum(item.suppressed for item in items),
        }

    payload = {
        "symbols": list(report.symbols),
        "symbol_count": len(report.symbols),
        "horizons_weeks": list(report.horizons_weeks),
        "policy_counts": policy_counts,
        "summary_rows": len(report.summaries),
        "leave_one_symbol_out_rows": len(report.leave_one_symbol_out),
        "is_actionable": False,
    }
    paths.summary_json.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    _observations_frame(report).to_csv(paths.observations_csv, index=False)
    _summaries_frame(report).to_csv(paths.summaries_csv, index=False)
    _leave_one_symbol_out_frame(report).to_csv(paths.leave_one_symbol_out_csv, index=False)
    return paths


def _parse_csv_strings(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _parse_csv_ints(value: str) -> tuple[int, ...]:
    return tuple(int(item) for item in _parse_csv_strings(value))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the read-only WF7A legacy-actionability contradiction counterfactual. "
            "No production actionability is changed."
        )
    )
    parser.add_argument("--symbols", required=True, help="Comma-separated symbols.")
    parser.add_argument(
        "--horizons",
        default="5,10,15",
        help="Comma-separated forward horizons in weeks.",
    )
    parser.add_argument(
        "--out-of-sample-start-week",
        default=None,
        help="Optional ISO date/week used as the caller-defined OOS boundary.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_COUNTERFACTUAL_OUTPUT_DIR),
        help="Destination for WF7A JSON/CSV artifacts.",
    )
    args = parser.parse_args(argv)

    report = run_weekly_actionability_counterfactual_study(
        _parse_csv_strings(args.symbols),
        horizons_weeks=_parse_csv_ints(args.horizons),
        out_of_sample_start_week=args.out_of_sample_start_week,
    )
    paths = write_weekly_actionability_counterfactual_bundle(report, args.output_dir)
    print(
        json.dumps(
            {
                "symbols": list(report.symbols),
                "horizons_weeks": list(report.horizons_weeks),
                "observation_rows": len(report.observations),
                "summary_rows": len(report.summaries),
                "leave_one_symbol_out_rows": len(report.leave_one_symbol_out),
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
    "DEFAULT_COUNTERFACTUAL_OUTPUT_DIR",
    "WeeklyCounterfactualBundlePaths",
    "run_weekly_actionability_counterfactual_study",
    "write_weekly_actionability_counterfactual_bundle",
]
