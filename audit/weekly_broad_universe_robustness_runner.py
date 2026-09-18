"""WF7C2 broad-universe robustness harness for the read-only WF7C1 study.

The runner preserves fail-fast behavior by default.  Large research universes
may explicitly opt into per-symbol continuation, in which case every skipped
symbol is written to a failure ledger.  Successful symbols are fingerprinted and retained as frozen research snapshots.
Those exact snapshots become the input contract for aggregate WF7C1 analysis, so
the broad-universe path does not refresh market data or rerun the historical scanner.

Nothing here changes production qualification, scoring, ranking, WeeklySetup,
daily entry, alerts, execution, or orders.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Iterable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from audit.weekly_input_reproducibility_runner import (
    ReproducibleWeeklyFoundationSymbolSnapshot,
    combine_reproducible_weekly_foundation_snapshots,
    run_reproducible_weekly_foundation_symbol_snapshot,
)
from audit.weekly_opposite_supported_thesis_runner import (
    ReproducibleWeeklyOppositeSupportedStudy,
    load_weekly_input_fingerprint_manifest,
    run_reproducible_weekly_opposite_supported_study,
    write_weekly_opposite_supported_bundle,
)
from weekly_audit_input_reproducibility import (
    WeeklyAuditInputFingerprint,
    compare_weekly_audit_inputs,
)


DEFAULT_WF7C2_OUTPUT_DIR = Path("reports/weekly-foundation/wf7c2-latest")

PreflightOne = Callable[[str], WeeklyAuditInputFingerprint]
AnalysisRunner = Callable[..., ReproducibleWeeklyOppositeSupportedStudy]


@dataclass(frozen=True, slots=True)
class WeeklyBroadUniverseSymbolFailure:
    symbol: str
    stage: str
    error_type: str
    message: str


@dataclass(frozen=True, slots=True)
class WeeklyBroadUniversePreflight:
    requested_symbols: tuple[str, ...]
    successful_symbols: tuple[str, ...]
    input_fingerprints: tuple[WeeklyAuditInputFingerprint, ...]
    failures: tuple[WeeklyBroadUniverseSymbolFailure, ...]
    external_baseline_used: bool
    continue_on_symbol_error: bool

    @property
    def failed_symbols(self) -> tuple[str, ...]:
        return tuple(item.symbol for item in self.failures)


@dataclass(frozen=True, slots=True)
class WeeklyBroadUniverseRobustnessStudy:
    preflight: WeeklyBroadUniversePreflight
    analysis: ReproducibleWeeklyOppositeSupportedStudy
    frozen_preflight_snapshot_used: bool = False

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class WeeklyBroadUniverseBundlePaths:
    summary_json: Path
    failure_ledger_csv: Path
    preflight_fingerprints_json: Path
    preflight_fingerprints_csv: Path

    def as_dict(self) -> dict[str, str]:
        return {key: str(value) for key, value in asdict(self).items()}


class _FingerprintGateError(ValueError):
    pass


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


def _comparison_error(expected: WeeklyAuditInputFingerprint, observed: WeeklyAuditInputFingerprint) -> str:
    comparison = compare_weekly_audit_inputs((expected,), (observed,))
    if comparison.matches:
        return ""
    if comparison.missing_from_left or comparison.missing_from_right:
        return (
            f"missing_from_expected={comparison.missing_from_left}; "
            f"missing_from_current={comparison.missing_from_right}"
        )
    return repr(tuple((item.symbol, item.fields) for item in comparison.mismatches))


def preflight_weekly_research_universe(
    symbols: Sequence[str] | Iterable[str],
    *,
    preflight_one: PreflightOne,
    expected_fingerprints: Sequence[WeeklyAuditInputFingerprint] | None = None,
    continue_on_symbol_error: bool = False,
) -> WeeklyBroadUniversePreflight:
    """Validate each research symbol without silently shrinking the universe.

    Fail-fast remains the default.  With ``continue_on_symbol_error=True`` the
    caller explicitly authorizes per-symbol continuation and receives an exact
    failure ledger.  Global input errors such as duplicate expected fingerprint
    symbols still fail immediately.
    """

    requested = _normalize_symbols(symbols)
    expected_items = tuple(expected_fingerprints or ())
    expected_by_symbol = {item.symbol: item for item in expected_items}
    if len(expected_by_symbol) != len(expected_items):
        raise ValueError("expected fingerprint manifest requires unique symbols")

    successful: list[str] = []
    observed_fingerprints: list[WeeklyAuditInputFingerprint] = []
    failures: list[WeeklyBroadUniverseSymbolFailure] = []

    for symbol in requested:
        stage = "preflight"
        try:
            observed = preflight_one(symbol)
            if observed.symbol != symbol:
                raise ValueError(
                    f"preflight fingerprint symbol mismatch: expected {symbol}, "
                    f"observed {observed.symbol}"
                )

            if expected_fingerprints is not None:
                stage = "fingerprint_gate"
                expected = expected_by_symbol.get(symbol)
                if expected is None:
                    raise _FingerprintGateError(
                        f"{symbol} is missing from the expected fingerprint manifest"
                    )
                mismatch = _comparison_error(expected, observed)
                if mismatch:
                    raise _FingerprintGateError(
                        f"{symbol} input fingerprint mismatch: {mismatch}"
                    )

            successful.append(symbol)
            observed_fingerprints.append(observed)
        except Exception as exc:
            if not continue_on_symbol_error:
                raise
            failures.append(
                WeeklyBroadUniverseSymbolFailure(
                    symbol=symbol,
                    stage=stage,
                    error_type=type(exc).__name__,
                    message=str(exc),
                )
            )

    if not successful:
        raise ValueError("no symbols survived WF7C2 preflight")

    return WeeklyBroadUniversePreflight(
        requested_symbols=requested,
        successful_symbols=tuple(successful),
        input_fingerprints=tuple(observed_fingerprints),
        failures=tuple(failures),
        external_baseline_used=expected_fingerprints is not None,
        continue_on_symbol_error=continue_on_symbol_error,
    )


def run_weekly_broad_universe_robustness_study(
    symbols: Sequence[str] | Iterable[str],
    *,
    horizons_weeks: Iterable[int] = (5, 10, 15),
    out_of_sample_start_week: str | None = None,
    expected_fingerprints: Sequence[WeeklyAuditInputFingerprint] | None = None,
    continue_on_symbol_error: bool = False,
    preflight_one: PreflightOne | None = None,
    analysis_runner: AnalysisRunner = run_reproducible_weekly_opposite_supported_study,
) -> WeeklyBroadUniverseRobustnessStudy:
    """Run WF7C1 on the explicitly surviving frozen preflight universe.

    The default path materializes each symbol exactly once, captures the exact
    completed-week fingerprint, and retains the resulting historical audit
    object. Aggregate WF7C1 then consumes those same frozen objects rather than
    refreshing market data or rerunning the expensive historical scanner.
    Custom injected preflight callbacks retain the legacy test/extension path.
    """

    horizons = _normalize_horizons(horizons_weeks)
    frozen_by_symbol: dict[str, ReproducibleWeeklyFoundationSymbolSnapshot] = {}

    if preflight_one is None:
        def run_one(symbol: str) -> WeeklyAuditInputFingerprint:
            snapshot = run_reproducible_weekly_foundation_symbol_snapshot(
                symbol,
                horizons_weeks=horizons,
                out_of_sample_start_week=out_of_sample_start_week,
            )
            frozen_by_symbol[symbol] = snapshot
            return snapshot.input_fingerprint
        preflight_callback = run_one
    else:
        preflight_callback = preflight_one

    preflight = preflight_weekly_research_universe(
        symbols,
        preflight_one=preflight_callback,
        expected_fingerprints=expected_fingerprints,
        continue_on_symbol_error=continue_on_symbol_error,
    )

    frozen_snapshot = None
    if preflight_one is None:
        frozen_snapshot = combine_reproducible_weekly_foundation_snapshots(
            tuple(frozen_by_symbol[symbol] for symbol in preflight.successful_symbols)
        )

    analysis_kwargs: dict[str, Any] = {
        "expected_fingerprints": preflight.input_fingerprints,
        "horizons_weeks": horizons,
        "out_of_sample_start_week": out_of_sample_start_week,
    }
    if frozen_snapshot is not None:
        analysis_kwargs["foundation_snapshot"] = frozen_snapshot

    analysis = analysis_runner(
        preflight.successful_symbols,
        **analysis_kwargs,
    )
    if not analysis.fingerprint_comparison.matches:
        raise RuntimeError("WF7C2 aggregate analysis did not match preflight fingerprints")

    return WeeklyBroadUniverseRobustnessStudy(
        preflight=preflight,
        analysis=analysis,
        frozen_preflight_snapshot_used=frozen_snapshot is not None,
    )


def write_weekly_broad_universe_bundle(
    study: WeeklyBroadUniverseRobustnessStudy,
    output_dir: str | Path = DEFAULT_WF7C2_OUTPUT_DIR,
) -> WeeklyBroadUniverseBundlePaths:
    """Write WF7C2 ledger/manifest plus the unchanged WF7C1 artifact bundle."""

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    write_weekly_opposite_supported_bundle(study.analysis, root)

    paths = WeeklyBroadUniverseBundlePaths(
        summary_json=root / "wf7c2_broad_universe_summary.json",
        failure_ledger_csv=root / "wf7c2_symbol_failures.csv",
        preflight_fingerprints_json=root / "wf7c2_preflight_input_fingerprints.json",
        preflight_fingerprints_csv=root / "wf7c2_preflight_input_fingerprints.csv",
    )

    failures = [asdict(item) for item in study.preflight.failures]
    fingerprints = [asdict(item) for item in study.preflight.input_fingerprints]
    treatments = tuple(
        item for item in study.analysis.report.observations if item.is_opposite_supported
    )
    summary = {
        "requested_symbols": list(study.preflight.requested_symbols),
        "requested_symbol_count": len(study.preflight.requested_symbols),
        "successful_symbols": list(study.preflight.successful_symbols),
        "successful_symbol_count": len(study.preflight.successful_symbols),
        "failed_symbols": list(study.preflight.failed_symbols),
        "failed_symbol_count": len(study.preflight.failures),
        "continue_on_symbol_error": study.preflight.continue_on_symbol_error,
        "external_baseline_used": study.preflight.external_baseline_used,
        "frozen_preflight_snapshot_used": study.frozen_preflight_snapshot_used,
        "aggregate_matches_preflight": study.analysis.fingerprint_comparison.matches,
        "opposite_supported_episodes": len(treatments),
        "matched_pairs": len(study.analysis.report.matched_pairs),
        "unmatched_treatments": len(study.analysis.report.unmatched_treatments),
        "is_actionable": False,
    }
    paths.summary_json.write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    pd.DataFrame(
        failures,
        columns=("symbol", "stage", "error_type", "message"),
    ).to_csv(paths.failure_ledger_csv, index=False)

    fingerprint_payload = {
        "symbols": list(study.preflight.successful_symbols),
        "symbol_count": len(study.preflight.successful_symbols),
        "is_actionable": False,
        "fingerprints": fingerprints,
    }
    paths.preflight_fingerprints_json.write_text(
        json.dumps(fingerprint_payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    pd.DataFrame(fingerprints).to_csv(paths.preflight_fingerprints_csv, index=False)
    return paths


def _parse_csv_strings(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _parse_csv_ints(value: str) -> tuple[int, ...]:
    return tuple(int(item) for item in _parse_csv_strings(value))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run WF7C1 across a broad research universe with explicit optional "
            "per-symbol failure accounting. No production actionability changes."
        )
    )
    parser.add_argument("--symbols", required=True, help="Comma-separated symbols.")
    parser.add_argument("--horizons", default="5,10,15")
    parser.add_argument("--out-of-sample-start-week", default=None)
    parser.add_argument(
        "--expected-input-fingerprints",
        default=None,
        help=(
            "Optional prior WF7C0/WF7C2 JSON fingerprint manifest. If supplied, "
            "each requested symbol must match it unless continuation is explicitly enabled."
        ),
    )
    parser.add_argument(
        "--continue-on-symbol-error",
        action="store_true",
        help=(
            "Explicitly continue after symbol-local preflight/fingerprint failures and "
            "record every skipped symbol. Default behavior is fail-fast."
        ),
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_WF7C2_OUTPUT_DIR))
    args = parser.parse_args(argv)

    expected = (
        None
        if args.expected_input_fingerprints is None
        else load_weekly_input_fingerprint_manifest(args.expected_input_fingerprints)
    )
    study = run_weekly_broad_universe_robustness_study(
        _parse_csv_strings(args.symbols),
        horizons_weeks=_parse_csv_ints(args.horizons),
        out_of_sample_start_week=args.out_of_sample_start_week,
        expected_fingerprints=expected,
        continue_on_symbol_error=args.continue_on_symbol_error,
    )
    paths = write_weekly_broad_universe_bundle(study, args.output_dir)
    print(
        json.dumps(
            {
                "requested_symbol_count": len(study.preflight.requested_symbols),
                "successful_symbol_count": len(study.preflight.successful_symbols),
                "failed_symbol_count": len(study.preflight.failures),
                "failed_symbols": list(study.preflight.failed_symbols),
                "aggregate_matches_preflight": (
                    study.analysis.fingerprint_comparison.matches
                ),
                "frozen_preflight_snapshot_used": (
                    study.frozen_preflight_snapshot_used
                ),
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
    "DEFAULT_WF7C2_OUTPUT_DIR",
    "WeeklyBroadUniverseBundlePaths",
    "WeeklyBroadUniversePreflight",
    "WeeklyBroadUniverseRobustnessStudy",
    "WeeklyBroadUniverseSymbolFailure",
    "preflight_weekly_research_universe",
    "run_weekly_broad_universe_robustness_study",
    "write_weekly_broad_universe_bundle",
]
