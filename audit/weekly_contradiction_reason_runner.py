"""Historical runner for WF7B contradiction-reason decomposition.

This command reuses the read-only WF7A historical counterfactual report and
classifies each unique legacy-actionable week by an exclusive shadow reason.
It also emits episode-start cohorts so persistent multi-week conflicts do not
receive repeated weight merely because they last several bars.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from audit.weekly_actionability_counterfactual_runner import (
    run_weekly_actionability_counterfactual_study,
)
from weekly_contradiction_reason_audit import (
    WeeklyContradictionReasonAuditEngine,
    WeeklyContradictionReasonAuditReport,
    WeeklyContradictionReasonMetrics,
)


DEFAULT_WF7B_OUTPUT_DIR = Path("reports/weekly-foundation/wf7b-latest")


@dataclass(frozen=True, slots=True)
class WeeklyContradictionReasonBundlePaths:
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


def run_weekly_contradiction_reason_study(
    symbols: Sequence[str],
    *,
    horizons_weeks: Sequence[int] = (5, 10, 15),
    out_of_sample_start_week: str | None = None,
) -> WeeklyContradictionReasonAuditReport:
    wf7a = run_weekly_actionability_counterfactual_study(
        symbols,
        horizons_weeks=horizons_weeks,
        out_of_sample_start_week=out_of_sample_start_week,
    )
    return WeeklyContradictionReasonAuditEngine.audit(counterfactual_report=wf7a)


def _enum_text(value: object) -> str:
    return str(getattr(value, "value", value))


def _metrics_columns(metrics: WeeklyContradictionReasonMetrics, prefix: str = "") -> dict[str, object]:
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


def _outcome_columns(outcomes: tuple[object, ...]) -> dict[str, object]:
    row: dict[str, object] = {}
    for outcome in outcomes:
        horizon = getattr(outcome, "horizon_weeks")
        prefix = f"h{horizon}_"
        row[f"{prefix}available_weeks"] = getattr(outcome, "available_weeks")
        row[f"{prefix}complete"] = getattr(outcome, "complete")
        row[f"{prefix}close_return_pct"] = getattr(outcome, "close_return_pct")
        row[f"{prefix}mfe_pct"] = getattr(outcome, "maximum_favorable_excursion_pct")
        row[f"{prefix}mae_pct"] = getattr(outcome, "maximum_adverse_excursion_pct")
    return row


def write_weekly_contradiction_reason_bundle(
    report: WeeklyContradictionReasonAuditReport,
    output_dir: str | Path,
) -> WeeklyContradictionReasonBundlePaths:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = WeeklyContradictionReasonBundlePaths(
        summary_json=root / "wf7b_contradiction_reason_summary.json",
        observations_csv=root / "wf7b_contradiction_reason_observations.csv",
        summaries_csv=root / "wf7b_contradiction_reason_summaries.csv",
        leave_one_symbol_out_csv=root / "wf7b_contradiction_reason_leave_one_symbol_out.csv",
    )

    reason_counts: dict[str, dict[str, int]] = {}
    for reason in sorted({item.reason_class for item in report.observations}, key=_enum_text):
        items = tuple(item for item in report.observations if item.reason_class is reason)
        reason_counts[_enum_text(reason)] = {
            "bar_observations": len(items),
            "episodes": sum(item.episode_start for item in items),
        }

    paths.summary_json.write_text(
        json.dumps(
            {
                "symbols": list(report.symbols),
                "symbol_count": len(report.symbols),
                "horizons_weeks": list(report.horizons_weeks),
                "unique_legacy_actionable_observations": len(report.observations),
                "reason_counts": reason_counts,
                "summary_rows": len(report.summaries),
                "leave_one_symbol_out_rows": len(report.leave_one_symbol_out),
                "is_actionable": False,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    observation_rows: list[dict[str, object]] = []
    for item in report.observations:
        row: dict[str, object] = {
            "symbol": item.symbol,
            "week": item.week,
            "bar_index": item.bar_index,
            "partition": _enum_text(item.partition),
            "legacy_direction": _enum_text(item.legacy_direction),
            "shadow_state": _enum_text(item.shadow_state),
            "shadow_direction": _enum_text(item.shadow_direction),
            "reason_class": _enum_text(item.reason_class),
            "source_reasons": "|".join(_enum_text(reason) for reason in item.source_reasons),
            "episode_id": item.episode_id,
            "episode_start": item.episode_start,
            "episode_length_so_far": item.episode_length_so_far,
        }
        row.update(_outcome_columns(item.outcomes))
        observation_rows.append(row)
    pd.DataFrame(observation_rows).to_csv(paths.observations_csv, index=False)

    summary_rows: list[dict[str, object]] = []
    for item in report.summaries:
        row = {
            "reason_class": _enum_text(item.reason_class),
            "sample_unit": _enum_text(item.sample_unit),
            "horizon_weeks": item.horizon_weeks,
            "partition": _enum_text(item.partition),
        }
        row.update(_metrics_columns(item.metrics))
        summary_rows.append(row)
    pd.DataFrame(summary_rows).to_csv(paths.summaries_csv, index=False)

    loso_rows: list[dict[str, object]] = []
    for item in report.leave_one_symbol_out:
        row = {
            "reason_class": _enum_text(item.reason_class),
            "sample_unit": _enum_text(item.sample_unit),
            "horizon_weeks": item.horizon_weeks,
            "held_out_symbol": item.held_out_symbol,
            "held_out_minus_other_mean_close_pct": item.held_out_minus_other_mean_close_pct,
        }
        row.update(_metrics_columns(item.held_out, "held_out_"))
        row.update(_metrics_columns(item.other_symbols, "other_symbols_"))
        loso_rows.append(row)
    pd.DataFrame(loso_rows).to_csv(paths.leave_one_symbol_out_csv, index=False)
    return paths


def _parse_csv_strings(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _parse_csv_ints(value: str) -> tuple[int, ...]:
    return tuple(int(item) for item in _parse_csv_strings(value))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run read-only WF7B contradiction reason and episode decomposition."
    )
    parser.add_argument("--symbols", required=True, help="Comma-separated symbols.")
    parser.add_argument("--horizons", default="5,10,15")
    parser.add_argument("--out-of-sample-start-week", default=None)
    parser.add_argument("--output-dir", default=str(DEFAULT_WF7B_OUTPUT_DIR))
    args = parser.parse_args(argv)

    report = run_weekly_contradiction_reason_study(
        _parse_csv_strings(args.symbols),
        horizons_weeks=_parse_csv_ints(args.horizons),
        out_of_sample_start_week=args.out_of_sample_start_week,
    )
    paths = write_weekly_contradiction_reason_bundle(report, args.output_dir)
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
    "DEFAULT_WF7B_OUTPUT_DIR",
    "WeeklyContradictionReasonBundlePaths",
    "run_weekly_contradiction_reason_study",
    "write_weekly_contradiction_reason_bundle",
]
