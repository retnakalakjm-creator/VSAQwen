"""Historical execution harness for the WF1-WF6 weekly foundation audit stack.

This module is analysis-only.  It materializes the already-implemented weekly
shadow/audit layers on real completed weekly history so WF7 production changes
can be based on observed historical evidence rather than architecture intuition.

Default path:

    download_data
      -> daily_to_weekly
      -> completed_weekly_only
      -> MetricsEngine
      -> HistoricalScannerRunner
      -> WF1 decision-gate audit
      -> WF2/WF3/WF4/WF5 replay comparison
      -> WF6 evidence-promotion audit

Nothing in this module mutates scanner state, qualification, ranking,
actionability, WeeklySetup, daily entry, alerts, or orders.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from data import completed_weekly_only, daily_to_weekly, download_data
from engine.columns import COL_CLOSE, COL_HIGH, COL_LOW, COL_WEEK
from historical_scanner import HistoricalScannerRunner
from metrics_engine import MetricsEngine
from scanner import ScannerCandidate, ScannerEngine
from support_resistance.zones import derive_weekly_structural_zones
from weekly_decision_audit import (
    WeeklyDecisionGateAuditRecord,
    WeeklyDecisionGateAuditor,
)
from weekly_evidence_promotion_audit import (
    WeeklyEvidenceCohortMetrics,
    WeeklyEvidencePromotionAuditEngine,
    WeeklyEvidencePromotionAuditReport,
    WeeklyEvidencePromotionInput,
)
from weekly_replay_comparison import (
    DirectionalForwardOutcome,
    WeeklyReplayBucket,
    WeeklyReplayComparisonEngine,
    WeeklyReplayComparisonReport,
    WeeklyReplayPriceBar,
)


DEFAULT_STUDY_HORIZONS = WeeklyReplayComparisonEngine.DEFAULT_HORIZONS
DEFAULT_STUDY_OUTPUT_DIR = Path("reports/weekly-foundation/latest")

DailyLoader = Callable[[str], pd.DataFrame]
WeeklyTransformer = Callable[[pd.DataFrame], pd.DataFrame]
MetricsCalculator = Callable[[pd.DataFrame], pd.DataFrame]
ScannerFactory = Callable[[], Any]


@dataclass(frozen=True, slots=True)
class WeeklyFoundationSymbolStudy:
    """Fully materialized point-in-time weekly audit history for one symbol."""

    symbol: str
    daily_bars: int
    weekly_bars: int
    metric_bars: int
    audits: tuple[WeeklyDecisionGateAuditRecord, ...]
    prices: tuple[WeeklyReplayPriceBar, ...]
    replay: WeeklyReplayComparisonReport
    out_of_sample_start_bar_index: int | None = None

    @property
    def audited_bars(self) -> int:
        return len(self.audits)

    @property
    def evidence_promotion_input(self) -> WeeklyEvidencePromotionInput:
        return WeeklyEvidencePromotionInput(
            symbol=self.symbol,
            audits=self.audits,
            prices=self.prices,
            out_of_sample_start_bar_index=self.out_of_sample_start_bar_index,
        )


@dataclass(frozen=True, slots=True)
class WeeklyFoundationStudyResult:
    """Multi-symbol WF1-WF6 study output with no production authority."""

    symbols: tuple[str, ...]
    horizons_weeks: tuple[int, ...]
    location_distance_thresholds_pct: tuple[float, ...]
    symbol_results: tuple[WeeklyFoundationSymbolStudy, ...]
    evidence_promotion: WeeklyEvidencePromotionAuditReport

    @property
    def is_actionable(self) -> bool:
        return False

    @property
    def audited_bars(self) -> int:
        return sum(item.audited_bars for item in self.symbol_results)

    def summary(self) -> dict[str, object]:
        bucket_counts = {
            bucket.value: sum(
                count.count
                for symbol_result in self.symbol_results
                for count in symbol_result.replay.bucket_counts
                if count.bucket is bucket
            )
            for bucket in WeeklyReplayBucket
        }
        return {
            "symbols": list(self.symbols),
            "symbol_count": len(self.symbols),
            "horizons_weeks": list(self.horizons_weeks),
            "location_distance_thresholds_pct": list(
                self.location_distance_thresholds_pct
            ),
            "audited_bars": self.audited_bars,
            "replay_bucket_counts": bucket_counts,
            "promotion_observations": len(self.evidence_promotion.observations),
            "promotion_summaries": len(self.evidence_promotion.summaries),
            "location_sensitivity_rows": len(
                self.evidence_promotion.location_sensitivity
            ),
            "leave_one_symbol_out_rows": len(
                self.evidence_promotion.leave_one_symbol_out
            ),
            "is_actionable": False,
        }


@dataclass(frozen=True, slots=True)
class WeeklyFoundationStudyBundlePaths:
    """Files written by :func:`write_weekly_foundation_study_bundle`."""

    summary_json: Path
    replay_records_csv: Path
    promotion_observations_csv: Path
    promotion_summaries_csv: Path
    location_sensitivity_csv: Path
    leave_one_symbol_out_csv: Path

    def as_dict(self) -> dict[str, str]:
        return {
            "summary_json": str(self.summary_json),
            "replay_records_csv": str(self.replay_records_csv),
            "promotion_observations_csv": str(self.promotion_observations_csv),
            "promotion_summaries_csv": str(self.promotion_summaries_csv),
            "location_sensitivity_csv": str(self.location_sensitivity_csv),
            "leave_one_symbol_out_csv": str(self.leave_one_symbol_out_csv),
        }


def _normalize_symbol(symbol: str) -> str:
    normalized = str(symbol).strip().upper()
    if not normalized:
        raise ValueError("symbol cannot be blank")
    return normalized


def _normalize_symbols(symbols: Sequence[str] | Iterable[str]) -> tuple[str, ...]:
    normalized = tuple(_normalize_symbol(item) for item in symbols)
    if not normalized:
        raise ValueError("symbols must contain at least one symbol")
    if len(set(normalized)) != len(normalized):
        raise ValueError("symbols must be unique")
    return normalized


def _normalize_horizons(horizons: Iterable[int]) -> tuple[int, ...]:
    normalized = tuple(sorted(set(int(item) for item in horizons)))
    if not normalized or any(item <= 0 for item in normalized):
        raise ValueError("horizons must contain positive week counts")
    return normalized


def _normalize_thresholds(thresholds: Iterable[float]) -> tuple[float, ...]:
    normalized = tuple(sorted(set(float(item) for item in thresholds)))
    if any(item < 0.0 for item in normalized):
        raise ValueError("location distance thresholds must be non-negative")
    return normalized


def _default_weekly_transformer(daily: pd.DataFrame) -> pd.DataFrame:
    return completed_weekly_only(daily_to_weekly(daily))


def _default_metrics_calculator(weekly: pd.DataFrame) -> pd.DataFrame:
    return MetricsEngine().calculate(weekly)


def _candidate_map(
    scanner: Any,
    metrics: pd.DataFrame,
    target_indices: tuple[int, ...],
) -> dict[int, ScannerCandidate]:
    scan_to_indices = getattr(scanner, "scan_to_indices", None)
    if callable(scan_to_indices):
        return dict(scan_to_indices(metrics, target_indices))

    candidates = scanner.scan(metrics)
    result = {
        int(candidate.bar_index): candidate
        for candidate in candidates
        if candidate.bar_index is not None
        and int(candidate.bar_index) in target_indices
    }
    return result


def _price_bar(
    metrics: pd.DataFrame,
    *,
    bar_index: int,
    week: str | None,
) -> WeeklyReplayPriceBar:
    row = metrics.iloc[bar_index]
    return WeeklyReplayPriceBar(
        week=week,
        bar_index=bar_index,
        high=float(row[COL_HIGH]),
        low=float(row[COL_LOW]),
        close=float(row[COL_CLOSE]),
    )


def _resolve_out_of_sample_start(
    audits: tuple[WeeklyDecisionGateAuditRecord, ...],
    out_of_sample_start_week: str | None,
) -> int | None:
    if out_of_sample_start_week is None:
        return None

    target = pd.Timestamp(out_of_sample_start_week)
    for audit in audits:
        if audit.week is None:
            continue
        if pd.Timestamp(audit.week) >= target:
            assert audit.bar_index is not None
            return audit.bar_index
    raise ValueError(
        "out_of_sample_start_week is after the available audited history: "
        f"{out_of_sample_start_week}"
    )


def build_weekly_foundation_symbol_study_from_metrics(
    *,
    symbol: str,
    metrics: pd.DataFrame,
    horizons_weeks: Iterable[int] = DEFAULT_STUDY_HORIZONS,
    out_of_sample_start_week: str | None = None,
    scanner_factory: ScannerFactory = HistoricalScannerRunner,
    daily_bars: int = 0,
    weekly_bars: int | None = None,
) -> WeeklyFoundationSymbolStudy:
    """Materialize WF1-WF5 for one already-calculated weekly metrics frame.

    The scanner is run once across all replay targets. Each candidate is then
    projected through WF1 with support/resistance zones derived only from
    structural swings confirmed by that candidate bar. WF5 is built from those
    frozen records. Future outcomes never feed back into the decision state.
    """

    normalized_symbol = _normalize_symbol(symbol)
    horizons = _normalize_horizons(horizons_weeks)

    required = {COL_WEEK, COL_HIGH, COL_LOW, COL_CLOSE}
    missing = required.difference(metrics.columns)
    if missing:
        raise ValueError(f"metrics missing required columns: {sorted(missing)}")
    if len(metrics) <= ScannerEngine.MIN_REPLAY_BARS:
        raise ValueError("not enough weekly metric bars for foundation study")

    target_indices = tuple(range(ScannerEngine.MIN_REPLAY_BARS, len(metrics)))
    candidates = _candidate_map(scanner_factory(), metrics, target_indices)
    missing_candidates = tuple(index for index in target_indices if index not in candidates)
    if missing_candidates:
        raise ValueError(
            "scanner did not return a candidate for every requested replay bar: "
            f"{missing_candidates[:5]}"
        )

    audits: list[WeeklyDecisionGateAuditRecord] = []
    prices: list[WeeklyReplayPriceBar] = []

    for bar_index in target_indices:
        candidate = candidates[bar_index]
        if candidate.bar_index != bar_index:
            raise ValueError("scanner candidate bar_index does not match replay target")

        context = candidate.evidence.context
        zones = derive_weekly_structural_zones(
            getattr(context, "structural_swings", ()),
            as_of_bar_index=bar_index,
        )
        audit = WeeklyDecisionGateAuditor.audit(
            symbol=normalized_symbol,
            candidate=candidate,
            support_zone=None if zones.support is None else zones.support.zone,
            resistance_zone=(
                None if zones.resistance is None else zones.resistance.zone
            ),
        )
        audits.append(audit)
        prices.append(
            _price_bar(
                metrics,
                bar_index=bar_index,
                week=audit.week,
            )
        )

    audit_history = tuple(audits)
    price_history = tuple(prices)
    split_index = _resolve_out_of_sample_start(
        audit_history,
        out_of_sample_start_week,
    )
    replay = WeeklyReplayComparisonEngine.compare(
        audits=audit_history,
        prices=price_history,
        horizons_weeks=horizons,
    )

    return WeeklyFoundationSymbolStudy(
        symbol=normalized_symbol,
        daily_bars=int(daily_bars),
        weekly_bars=len(metrics) if weekly_bars is None else int(weekly_bars),
        metric_bars=len(metrics),
        audits=audit_history,
        prices=price_history,
        replay=replay,
        out_of_sample_start_bar_index=split_index,
    )


def run_weekly_foundation_symbol_study(
    symbol: str,
    *,
    horizons_weeks: Iterable[int] = DEFAULT_STUDY_HORIZONS,
    out_of_sample_start_week: str | None = None,
    daily_loader: DailyLoader = download_data,
    weekly_transformer: WeeklyTransformer | None = None,
    metrics_calculator: MetricsCalculator | None = None,
    scanner_factory: ScannerFactory = HistoricalScannerRunner,
) -> WeeklyFoundationSymbolStudy:
    """Run the complete read-only weekly foundation study for one symbol."""

    normalized_symbol = _normalize_symbol(symbol)
    transform = weekly_transformer or _default_weekly_transformer
    calculate = metrics_calculator or _default_metrics_calculator

    daily = daily_loader(normalized_symbol)
    weekly = transform(daily)
    metrics = calculate(weekly)

    return build_weekly_foundation_symbol_study_from_metrics(
        symbol=normalized_symbol,
        metrics=metrics,
        horizons_weeks=horizons_weeks,
        out_of_sample_start_week=out_of_sample_start_week,
        scanner_factory=scanner_factory,
        daily_bars=len(daily),
        weekly_bars=len(weekly),
    )


def run_weekly_foundation_historical_study(
    symbols: Sequence[str] | Iterable[str],
    *,
    horizons_weeks: Iterable[int] = DEFAULT_STUDY_HORIZONS,
    location_distance_thresholds_pct: Iterable[float] = (),
    out_of_sample_start_week: str | None = None,
    daily_loader: DailyLoader = download_data,
    weekly_transformer: WeeklyTransformer | None = None,
    metrics_calculator: MetricsCalculator | None = None,
    scanner_factory: ScannerFactory = HistoricalScannerRunner,
) -> WeeklyFoundationStudyResult:
    """Run WF1-WF6 across a symbol universe without changing production state."""

    normalized_symbols = _normalize_symbols(symbols)
    horizons = _normalize_horizons(horizons_weeks)
    thresholds = _normalize_thresholds(location_distance_thresholds_pct)

    symbol_results = tuple(
        run_weekly_foundation_symbol_study(
            symbol,
            horizons_weeks=horizons,
            out_of_sample_start_week=out_of_sample_start_week,
            daily_loader=daily_loader,
            weekly_transformer=weekly_transformer,
            metrics_calculator=metrics_calculator,
            scanner_factory=scanner_factory,
        )
        for symbol in normalized_symbols
    )

    promotion = WeeklyEvidencePromotionAuditEngine.audit(
        datasets=tuple(item.evidence_promotion_input for item in symbol_results),
        horizons_weeks=horizons,
        location_distance_thresholds_pct=thresholds,
    )

    return WeeklyFoundationStudyResult(
        symbols=normalized_symbols,
        horizons_weeks=horizons,
        location_distance_thresholds_pct=thresholds,
        symbol_results=symbol_results,
        evidence_promotion=promotion,
    )


def _enum_text(value: object) -> str:
    return str(getattr(value, "value", value))


def _outcome_columns(
    outcomes: tuple[DirectionalForwardOutcome, ...],
    prefix: str,
) -> dict[str, object]:
    result: dict[str, object] = {}
    for outcome in outcomes:
        horizon = outcome.horizon_weeks
        result[f"{prefix}_{horizon}w_complete"] = outcome.complete
        result[f"{prefix}_{horizon}w_available_weeks"] = outcome.available_weeks
        result[f"{prefix}_{horizon}w_close_return_pct"] = outcome.close_return_pct
        result[f"{prefix}_{horizon}w_mfe_pct"] = (
            outcome.maximum_favorable_excursion_pct
        )
        result[f"{prefix}_{horizon}w_mae_pct"] = (
            outcome.maximum_adverse_excursion_pct
        )
    return result


def _cohort_columns(
    cohort: WeeklyEvidenceCohortMetrics,
    prefix: str,
) -> dict[str, object]:
    result: dict[str, object] = {
        f"{prefix}_observation_count": cohort.observation_count,
        f"{prefix}_complete_outcome_count": cohort.complete_outcome_count,
        f"{prefix}_mean_close_return_pct": cohort.mean_close_return_pct,
        f"{prefix}_median_close_return_pct": cohort.median_close_return_pct,
        f"{prefix}_mean_mfe_pct": cohort.mean_mfe_pct,
        f"{prefix}_mean_mae_pct": cohort.mean_mae_pct,
        f"{prefix}_structural_confirmation_first_count": (
            cohort.structural_confirmation_first_count
        ),
        f"{prefix}_structural_invalidation_first_count": (
            cohort.structural_invalidation_first_count
        ),
        f"{prefix}_structural_neither_count": cohort.structural_neither_count,
    }
    for bucket_count in cohort.bucket_counts:
        result[f"{prefix}_bucket_{bucket_count.bucket.value}"] = bucket_count.count
    return result


def _replay_records_frame(result: WeeklyFoundationStudyResult) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for symbol_result in result.symbol_results:
        for record in symbol_result.replay.records:
            row: dict[str, object] = {
                "symbol": record.symbol,
                "week": record.week,
                "bar_index": record.bar_index,
                "legacy_qualification": _enum_text(record.legacy_qualification),
                "legacy_actionable": record.legacy_actionable,
                "legacy_direction": _enum_text(record.legacy_direction),
                "legacy_gate_blockers": ";".join(
                    _enum_text(item) for item in record.legacy_gate_blockers
                ),
                "shadow_state": _enum_text(record.shadow_state),
                "shadow_basis": _enum_text(record.shadow_basis),
                "shadow_direction": _enum_text(record.shadow_direction),
                "shadow_supported": record.shadow_supported,
                "contradiction_state": _enum_text(record.contradiction_state),
                "bucket": record.bucket.value,
                "direction_agreement": record.direction_agreement.value,
            }
            row.update(_outcome_columns(record.legacy_forward_outcomes, "legacy"))
            row.update(_outcome_columns(record.shadow_forward_outcomes, "shadow"))
            rows.append(row)
    return pd.DataFrame(rows)


def _promotion_observations_frame(result: WeeklyFoundationStudyResult) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for observation in result.evidence_promotion.observations:
        row: dict[str, object] = {
            "symbol": observation.symbol,
            "week": observation.week,
            "bar_index": observation.bar_index,
            "direction": _enum_text(observation.direction),
            "candidate": observation.candidate.value,
            "evidence_code": (
                None
                if observation.evidence_code is None
                else _enum_text(observation.evidence_code)
            ),
            "eligible": observation.eligible,
            "present": observation.present,
            "evidence_codes": ";".join(
                _enum_text(item) for item in observation.evidence_codes
            ),
            "partition": observation.partition.value,
            "trend_direction": _enum_text(observation.regime.trend_direction),
            "trend_state": _enum_text(observation.regime.trend_state),
            "structural_pattern": _enum_text(observation.regime.structural_pattern),
            "legacy_actionable": observation.legacy_actionable,
            "shadow_state": _enum_text(observation.shadow_state),
            "bucket": observation.bucket.value,
            "legacy_gate_blockers": ";".join(
                _enum_text(item) for item in observation.legacy_gate_blockers
            ),
            "contradiction_state": _enum_text(observation.contradiction_state),
            "prior_aligned_evidence_count": observation.prior_aligned_evidence_count,
            "location_relation": observation.location_relation.value,
            "location_distance_pct": observation.location_distance_pct,
            "structural_outcome": observation.structural_outcome.value,
        }
        row.update(_outcome_columns(observation.outcomes, "outcome"))
        rows.append(row)
    return pd.DataFrame(rows)


def _promotion_summaries_frame(result: WeeklyFoundationStudyResult) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for summary in result.evidence_promotion.summaries:
        row: dict[str, object] = {
            "candidate": summary.candidate.value,
            "evidence_code": (
                None if summary.evidence_code is None else _enum_text(summary.evidence_code)
            ),
            "direction": _enum_text(summary.direction),
            "horizon_weeks": summary.horizon_weeks,
            "partition": summary.partition.value,
            "regime_trend_direction": (
                None
                if summary.regime is None
                else _enum_text(summary.regime.trend_direction)
            ),
            "regime_trend_state": (
                None
                if summary.regime is None
                else _enum_text(summary.regime.trend_state)
            ),
            "regime_structural_pattern": (
                None
                if summary.regime is None
                else _enum_text(summary.regime.structural_pattern)
            ),
            "mean_close_return_delta_pct": summary.mean_close_return_delta_pct,
            "median_close_return_delta_pct": summary.median_close_return_delta_pct,
            "mean_mfe_delta_pct": summary.mean_mfe_delta_pct,
            "mean_mae_delta_pct": summary.mean_mae_delta_pct,
        }
        row.update(_cohort_columns(summary.present, "present"))
        row.update(_cohort_columns(summary.absent, "absent"))
        rows.append(row)
    return pd.DataFrame(rows)


def _location_sensitivity_frame(result: WeeklyFoundationStudyResult) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for summary in result.evidence_promotion.location_sensitivity:
        row: dict[str, object] = {
            "direction": _enum_text(summary.direction),
            "horizon_weeks": summary.horizon_weeks,
            "threshold_pct": summary.threshold_pct,
            "mean_close_return_delta_pct": summary.mean_close_return_delta_pct,
            "mean_mfe_delta_pct": summary.mean_mfe_delta_pct,
            "mean_mae_delta_pct": summary.mean_mae_delta_pct,
        }
        row.update(_cohort_columns(summary.supportive_near_zone, "near"))
        row.update(_cohort_columns(summary.other_eligible_location, "other"))
        rows.append(row)
    return pd.DataFrame(rows)


def _leave_one_symbol_out_frame(result: WeeklyFoundationStudyResult) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for summary in result.evidence_promotion.leave_one_symbol_out:
        row: dict[str, object] = {
            "candidate": summary.candidate.value,
            "evidence_code": (
                None if summary.evidence_code is None else _enum_text(summary.evidence_code)
            ),
            "direction": _enum_text(summary.direction),
            "horizon_weeks": summary.horizon_weeks,
            "held_out_symbol": summary.held_out_symbol,
            "held_out_mean_close_delta_pct": summary.held_out_mean_close_delta_pct,
            "other_symbols_mean_close_delta_pct": (
                summary.other_symbols_mean_close_delta_pct
            ),
        }
        row.update(_cohort_columns(summary.held_out_present, "held_present"))
        row.update(_cohort_columns(summary.held_out_absent, "held_absent"))
        row.update(_cohort_columns(summary.other_symbols_present, "other_present"))
        row.update(_cohort_columns(summary.other_symbols_absent, "other_absent"))
        rows.append(row)
    return pd.DataFrame(rows)


def write_weekly_foundation_study_bundle(
    result: WeeklyFoundationStudyResult,
    output_dir: str | Path = DEFAULT_STUDY_OUTPUT_DIR,
) -> WeeklyFoundationStudyBundlePaths:
    """Write transparent CSV/JSON research artifacts for manual WF7 review."""

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)

    paths = WeeklyFoundationStudyBundlePaths(
        summary_json=destination / "weekly_foundation_summary.json",
        replay_records_csv=destination / "weekly_replay_records.csv",
        promotion_observations_csv=destination / "weekly_promotion_observations.csv",
        promotion_summaries_csv=destination / "weekly_promotion_summaries.csv",
        location_sensitivity_csv=destination / "weekly_location_sensitivity.csv",
        leave_one_symbol_out_csv=destination / "weekly_leave_one_symbol_out.csv",
    )

    paths.summary_json.write_text(
        json.dumps(result.summary(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    _replay_records_frame(result).to_csv(paths.replay_records_csv, index=False)
    _promotion_observations_frame(result).to_csv(
        paths.promotion_observations_csv,
        index=False,
    )
    _promotion_summaries_frame(result).to_csv(
        paths.promotion_summaries_csv,
        index=False,
    )
    _location_sensitivity_frame(result).to_csv(
        paths.location_sensitivity_csv,
        index=False,
    )
    _leave_one_symbol_out_frame(result).to_csv(
        paths.leave_one_symbol_out_csv,
        index=False,
    )
    return paths


def _parse_csv_strings(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _parse_csv_ints(value: str) -> tuple[int, ...]:
    return tuple(int(item) for item in _parse_csv_strings(value))


def _parse_csv_floats(value: str) -> tuple[float, ...]:
    return tuple(float(item) for item in _parse_csv_strings(value))


def main(argv: Sequence[str] | None = None) -> int:
    """Run a real historical WF1-WF6 study from the command line."""

    parser = argparse.ArgumentParser(
        description=(
            "Run the read-only ProVSA weekly-foundation historical study. "
            "This command does not change production actionability."
        )
    )
    parser.add_argument(
        "--symbols",
        required=True,
        help="Comma-separated symbols, for example LT.NS,RELIANCE.NS",
    )
    parser.add_argument(
        "--horizons",
        default="5,10,15",
        help="Comma-separated forward horizons in weeks.",
    )
    parser.add_argument(
        "--out-of-sample-start-week",
        default=None,
        help="Optional ISO date/week applied as the caller-defined OOS boundary.",
    )
    parser.add_argument(
        "--location-thresholds-pct",
        default="",
        help=(
            "Optional comma-separated support/resistance distance thresholds. "
            "No threshold is assumed when omitted."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_STUDY_OUTPUT_DIR),
        help="Destination directory for JSON/CSV study artifacts.",
    )
    args = parser.parse_args(argv)

    result = run_weekly_foundation_historical_study(
        _parse_csv_strings(args.symbols),
        horizons_weeks=_parse_csv_ints(args.horizons),
        location_distance_thresholds_pct=_parse_csv_floats(
            args.location_thresholds_pct
        ),
        out_of_sample_start_week=args.out_of_sample_start_week,
    )
    paths = write_weekly_foundation_study_bundle(result, args.output_dir)
    payload = result.summary()
    payload["output_paths"] = paths.as_dict()
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DEFAULT_STUDY_HORIZONS",
    "DEFAULT_STUDY_OUTPUT_DIR",
    "WeeklyFoundationStudyBundlePaths",
    "WeeklyFoundationStudyResult",
    "WeeklyFoundationSymbolStudy",
    "build_weekly_foundation_symbol_study_from_metrics",
    "run_weekly_foundation_historical_study",
    "run_weekly_foundation_symbol_study",
    "write_weekly_foundation_study_bundle",
]
