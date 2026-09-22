"""Capture and compare scanner candidate ledgers on frozen daily inputs.

The script is intentionally self-contained so the exact same file can be copied
outside the worktree and run against both a baseline checkout and a corrected
checkout. It imports scanner code from the current working directory.
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import pandas as pd


ROOT = Path.cwd()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit.daily_input_reproducibility import (  # noqa: E402
    daily_audit_input_manifest_sha256,
    load_daily_audit_input,
    load_daily_audit_input_bundle,
)
from data import daily_to_weekly  # noqa: E402
from historical_scanner import HistoricalScannerRunner  # noqa: E402
from metrics_engine import MetricsEngine  # noqa: E402


LEDGER_NAME = "scanner_candidate_ledger.csv"
SUMMARY_NAME = "scanner_candidate_summary.json"
DELTA_NAME = "scanner_candidate_deltas.csv"
COMPARE_SUMMARY_NAME = "scanner_candidate_compare_summary.json"


def _value(value: object) -> object:
    return getattr(value, "value", value)


def _codes(items) -> str:
    return "|".join(str(_value(item.code)) for item in items)


def _float(value: object) -> float:
    return float(value)


def _capture_symbol(input_dir: Path, symbol: str) -> list[dict[str, object]]:
    daily = load_daily_audit_input(input_dir, symbol)
    weekly = daily_to_weekly(daily)
    metrics = MetricsEngine().calculate(weekly)
    candidates = HistoricalScannerRunner().scan(metrics)

    rows: list[dict[str, object]] = []
    for candidate in candidates:
        rows.append(
            {
                "symbol": symbol,
                "bar_index": int(candidate.bar_index),
                "week": str(candidate.week),
                "qualification": str(_value(candidate.qualification)),
                "qualification_actionable": bool(
                    candidate.qualification_result.is_actionable_evidence
                ),
                "actionable": bool(candidate.actionable),
                "reason": str(candidate.reason),
                "target_codes": _codes(candidate.target_bar_evidence),
                "scoring_codes": _codes(candidate.scoring_evidence),
                "qualifying_codes": _codes(candidate.qualifying_evidence),
                "scoring_bar_index": (
                    None
                    if candidate.scoring_bar_index is None
                    else int(candidate.scoring_bar_index)
                ),
                "scoring_evidence_age": (
                    None
                    if candidate.scoring_evidence_age is None
                    else int(candidate.scoring_evidence_age)
                ),
                "used_fallback_evidence": bool(candidate.used_fallback_evidence),
                "confidence": _float(candidate.confidence),
                "net_strength": _float(candidate.net_strength),
                "net_pressure": _float(candidate.net_pressure),
                "ranking_score": _float(candidate.ranking_score),
            }
        )
    return rows


def capture(
    input_dir: Path,
    output_dir: Path,
    *,
    workers: int = 1,
) -> dict[str, object]:
    bundle = load_daily_audit_input_bundle(input_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if workers < 1:
        raise ValueError("workers must be >= 1")

    rows: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []
    symbols = [fingerprint.symbol for fingerprint in bundle.fingerprints]

    if workers == 1:
        for position, symbol in enumerate(symbols, start=1):
            try:
                rows.extend(_capture_symbol(input_dir, symbol))
                print(
                    f"[{position}/{len(symbols)}] {symbol} OK",
                    file=sys.stderr,
                    flush=True,
                )
            except Exception as exc:  # audit CLI must report per-symbol failures
                failures.append({"symbol": symbol, "error": repr(exc)})
                print(
                    f"[{position}/{len(symbols)}] {symbol} FAILED: {exc!r}",
                    file=sys.stderr,
                    flush=True,
                )
    else:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(_capture_symbol, input_dir, symbol): symbol
                for symbol in symbols
            }
            completed = 0
            for future in as_completed(futures):
                symbol = futures[future]
                completed += 1
                try:
                    rows.extend(future.result())
                    print(
                        f"[{completed}/{len(symbols)}] {symbol} OK",
                        file=sys.stderr,
                        flush=True,
                    )
                except Exception as exc:
                    failures.append({"symbol": symbol, "error": repr(exc)})
                    print(
                        f"[{completed}/{len(symbols)}] {symbol} FAILED: {exc!r}",
                        file=sys.stderr,
                        flush=True,
                    )

    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame.sort_values(["symbol", "bar_index"], inplace=True)
        frame.reset_index(drop=True, inplace=True)
    frame.to_csv(output_dir / LEDGER_NAME, index=False)

    summary: dict[str, object] = {
        "audit": "causal-vsa-scanner-candidate-ledger-v1",
        "input_snapshot_audit_id": bundle.audit_id,
        "input_snapshot_basket": bundle.basket_name,
        "input_snapshot_cutoff": bundle.cutoff,
        "input_snapshot_period": bundle.period,
        "input_snapshot_manifest_sha256": daily_audit_input_manifest_sha256(
            input_dir
        ),
        "requested_symbol_count": bundle.symbol_count,
        "worker_count": workers,
        "succeeded_symbol_count": bundle.symbol_count - len(failures),
        "failed_symbol_count": len(failures),
        "candidate_row_count": len(frame),
        "actionable_count": (
            int(frame["actionable"].sum()) if not frame.empty else 0
        ),
        "fallback_count": (
            int(frame["used_fallback_evidence"].sum()) if not frame.empty else 0
        ),
        "failures": failures,
        "is_actionable": False,
    }
    (output_dir / SUMMARY_NAME).write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return summary


def _normalized(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    for column in (
        "qualification",
        "reason",
        "target_codes",
        "scoring_codes",
        "qualifying_codes",
        "week",
    ):
        if column in normalized.columns:
            normalized[column] = normalized[column].fillna("").astype(str)
    return normalized


def compare(
    before_dir: Path,
    after_dir: Path,
    output_dir: Path,
) -> dict[str, object]:
    before = _normalized(pd.read_csv(before_dir / LEDGER_NAME))
    after = _normalized(pd.read_csv(after_dir / LEDGER_NAME))
    output_dir.mkdir(parents=True, exist_ok=True)

    key = ["symbol", "bar_index", "week"]
    merged = before.merge(
        after,
        on=key,
        how="outer",
        suffixes=("_before", "_after"),
        indicator=True,
    )

    comparable = merged[merged["_merge"] == "both"].copy()
    text_fields = (
        "qualification",
        "reason",
        "target_codes",
        "scoring_codes",
        "qualifying_codes",
    )
    bool_fields = (
        "qualification_actionable",
        "actionable",
        "used_fallback_evidence",
    )
    numeric_fields = (
        "scoring_bar_index",
        "scoring_evidence_age",
        "confidence",
        "net_strength",
        "net_pressure",
        "ranking_score",
    )

    changed_masks: dict[str, pd.Series] = {}
    for field in (*text_fields, *bool_fields):
        changed_masks[field] = (
            comparable[f"{field}_before"].fillna("")
            != comparable[f"{field}_after"].fillna("")
        )

    for field in numeric_fields:
        left = pd.to_numeric(
            comparable[f"{field}_before"],
            errors="coerce",
        )
        right = pd.to_numeric(
            comparable[f"{field}_after"],
            errors="coerce",
        )
        changed_masks[field] = ~(
            (left.isna() & right.isna())
            | (left.sub(right).abs() <= 1e-12)
        )

    any_change = pd.Series(False, index=comparable.index)
    for mask in changed_masks.values():
        any_change |= mask

    delta = comparable.loc[any_change].copy()
    delta.to_csv(output_dir / DELTA_NAME, index=False)

    before_summary = json.loads(
        (before_dir / SUMMARY_NAME).read_text(encoding="utf-8")
    )
    after_summary = json.loads(
        (after_dir / SUMMARY_NAME).read_text(encoding="utf-8")
    )

    summary: dict[str, object] = {
        "audit": "causal-vsa-scanner-candidate-compare-v1",
        "before_manifest_sha256": before_summary[
            "input_snapshot_manifest_sha256"
        ],
        "after_manifest_sha256": after_summary[
            "input_snapshot_manifest_sha256"
        ],
        "same_input_manifest": (
            before_summary["input_snapshot_manifest_sha256"]
            == after_summary["input_snapshot_manifest_sha256"]
        ),
        "before_row_count": len(before),
        "after_row_count": len(after),
        "left_only_row_count": int((merged["_merge"] == "left_only").sum()),
        "right_only_row_count": int((merged["_merge"] == "right_only").sum()),
        "changed_candidate_row_count": len(delta),
        "target_code_change_count": int(changed_masks["target_codes"].sum()),
        "qualifying_code_change_count": int(
            changed_masks["qualifying_codes"].sum()
        ),
        "scoring_code_change_count": int(changed_masks["scoring_codes"].sum()),
        "scoring_bar_change_count": int(
            changed_masks["scoring_bar_index"].sum()
        ),
        "scoring_age_change_count": int(
            changed_masks["scoring_evidence_age"].sum()
        ),
        "fallback_flag_change_count": int(
            changed_masks["used_fallback_evidence"].sum()
        ),
        "qualification_change_count": int(
            changed_masks["qualification"].sum()
        ),
        "reason_change_count": int(changed_masks["reason"].sum()),
        "qualification_actionable_change_count": int(
            changed_masks["qualification_actionable"].sum()
        ),
        "actionable_change_count": int(changed_masks["actionable"].sum()),
        "confidence_change_count": int(changed_masks["confidence"].sum()),
        "net_strength_change_count": int(changed_masks["net_strength"].sum()),
        "net_pressure_change_count": int(changed_masks["net_pressure"].sum()),
        "ranking_change_count": int(changed_masks["ranking_score"].sum()),
        "is_actionable": False,
    }
    (output_dir / COMPARE_SUMMARY_NAME).write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return summary


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    capture_parser = subparsers.add_parser("capture")
    capture_parser.add_argument("--input-snapshot-dir", type=Path, required=True)
    capture_parser.add_argument("--output-dir", type=Path, required=True)
    capture_parser.add_argument("--workers", type=int, default=1)

    compare_parser = subparsers.add_parser("compare")
    compare_parser.add_argument("--before-dir", type=Path, required=True)
    compare_parser.add_argument("--after-dir", type=Path, required=True)
    compare_parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "capture":
        result = capture(
            args.input_snapshot_dir,
            args.output_dir,
            workers=args.workers,
        )
    else:
        result = compare(args.before_dir, args.after_dir, args.output_dir)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
