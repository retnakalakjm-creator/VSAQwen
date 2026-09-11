from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from vsa_recovery_sequence_casebook import (
    build_vsa_recovery_sequence_casebook,
    render_vsa_recovery_sequence_casebook_csv,
)
from vsa_recovery_sequence_label_firing_audit import (
    build_vsa_recovery_sequence_label_firing_audit,
    render_vsa_recovery_sequence_label_firing_audit_csv,
)
from vsa_recovery_sequence_stage_seed import (
    build_vsa_recovery_sequence_stage_seed,
    render_vsa_recovery_sequence_stage_seed_csv,
)


@dataclass(frozen=True, slots=True)
class VSARecoverySequenceValidationArtifacts:
    """JSON/CSV/Markdown outputs for the saved-output 6C validation chain."""

    stage_seed_json: dict[str, Any]
    stage_seed_csv: str
    casebook_json: dict[str, Any]
    casebook_csv: str
    label_firing_audit_json: dict[str, Any]
    label_firing_audit_csv: str
    report_markdown: str


@dataclass(frozen=True, slots=True)
class VSARecoverySequenceValidationReport:
    """Audit-only report for the complete saved-output 6C validation chain."""

    stage_seed: dict[str, Any]
    casebook: dict[str, Any]
    label_firing_audit: dict[str, Any]
    production_only_stage_seed: dict[str, Any] | None = None
    audit_only: bool = True
    production_safe: bool = True
    validation_path: tuple[str, ...] = field(
        default=(
            "saved raw replay/audit rows",
            "6C stage-seed normalization",
            "6C recovery-sequence casebook",
            "6C label-firing audit",
        )
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "audit_only": self.audit_only,
            "production_safe": self.production_safe,
            "validation_path": list(self.validation_path),
            "stage_seed": dict(self.stage_seed),
            "production_only_stage_seed": (
                dict(self.production_only_stage_seed)
                if self.production_only_stage_seed is not None
                else None
            ),
            "casebook": dict(self.casebook),
            "label_firing_audit": dict(self.label_firing_audit),
        }

    def render_markdown(self) -> str:
        return render_vsa_recovery_sequence_validation_markdown(self)


def build_vsa_recovery_sequence_validation_report(
    payload: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    *,
    lookback_rows: int = 3,
    lookahead_rows: int = 3,
    include_diagnostic_hints: bool = True,
    include_production_only_stage_seed: bool = True,
) -> VSARecoverySequenceValidationReport:
    """Run the saved-output-only 6C validation chain and summarize results.

    This orchestrates already-persisted audit/replay JSON through the 6C
    stage-seed, casebook, and label-firing audit helpers. It does not load
    market data, call providers, replay scanners, mutate scanner state,
    activate detectors, alter scoring/ranking, touch API/frontend behavior, or
    persist anything.
    """

    stage_seed_summary = build_vsa_recovery_sequence_stage_seed(
        payload,
        lookback_rows=lookback_rows,
        lookahead_rows=lookahead_rows,
        include_diagnostic_hints=include_diagnostic_hints,
    )
    stage_seed_json = stage_seed_summary.to_dict()

    production_only_stage_seed_json = None
    if include_production_only_stage_seed:
        production_only_stage_seed_json = build_vsa_recovery_sequence_stage_seed(
            payload,
            lookback_rows=lookback_rows,
            lookahead_rows=lookahead_rows,
            include_diagnostic_hints=False,
        ).to_dict()

    casebook_summary = build_vsa_recovery_sequence_casebook(stage_seed_json)
    casebook_json = casebook_summary.to_dict()

    label_firing_audit_summary = build_vsa_recovery_sequence_label_firing_audit(casebook_json)
    label_firing_audit_json = label_firing_audit_summary.to_dict()

    return VSARecoverySequenceValidationReport(
        stage_seed=stage_seed_json,
        production_only_stage_seed=production_only_stage_seed_json,
        casebook=casebook_json,
        label_firing_audit=label_firing_audit_json,
    )


def build_vsa_recovery_sequence_validation_artifacts(
    payload: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    *,
    lookback_rows: int = 3,
    lookahead_rows: int = 3,
    include_diagnostic_hints: bool = True,
    include_production_only_stage_seed: bool = True,
) -> VSARecoverySequenceValidationArtifacts:
    """Build JSON, CSV, and Markdown outputs for the 6C validation chain."""

    report = build_vsa_recovery_sequence_validation_report(
        payload,
        lookback_rows=lookback_rows,
        lookahead_rows=lookahead_rows,
        include_diagnostic_hints=include_diagnostic_hints,
        include_production_only_stage_seed=include_production_only_stage_seed,
    )
    return VSARecoverySequenceValidationArtifacts(
        stage_seed_json=report.stage_seed,
        stage_seed_csv=render_vsa_recovery_sequence_stage_seed_csv(report.stage_seed),
        casebook_json=report.casebook,
        casebook_csv=render_vsa_recovery_sequence_casebook_csv(report.casebook),
        label_firing_audit_json=report.label_firing_audit,
        label_firing_audit_csv=render_vsa_recovery_sequence_label_firing_audit_csv(
            report.label_firing_audit
        ),
        report_markdown=report.render_markdown(),
    )


def render_vsa_recovery_sequence_validation_markdown(
    report: VSARecoverySequenceValidationReport | Mapping[str, Any],
) -> str:
    """Render a human-readable 6C validation chain report."""

    data = report.to_dict() if isinstance(report, VSARecoverySequenceValidationReport) else dict(report)
    stage_seed = _mapping(data.get("stage_seed"))
    production_only_stage_seed = _optional_mapping(data.get("production_only_stage_seed"))
    casebook = _mapping(data.get("casebook"))
    label_firing_audit = _mapping(data.get("label_firing_audit"))

    lines = [
        "# Milestone 6C Saved-Output Validation Report",
        "",
        "## Scope",
        "",
        "Audit validation only. No scanner adapter change, no provider or market-data loading, no scanner replay loop, no detector activation, no automatic bullish flip, no scoring/ranking change, no API/frontend change, no replay UI, and no persistence change.",
        "",
        "## Validation path",
        "",
    ]
    lines.extend(f"{index}. {step}" for index, step in enumerate(data.get("validation_path", ()), start=1))
    lines.extend(
        [
            "",
            "## Summary counts",
            "",
            f"- Saved replay rows checked: {stage_seed.get('total_input_rows', 0)}",
            f"- Stage-seed rows: {stage_seed.get('total_stage_seed_rows', 0)}",
            f"- Casebook rows: {casebook.get('total_casebook_rows', 0)}",
            f"- Label-firing rows: {label_firing_audit.get('total_input_rows', 0)}",
            "",
            "## Stage-seed status counts",
            "",
        ]
    )
    lines.extend(_bullet_counts(_mapping(stage_seed.get("status_counts"))))
    lines.extend(["", "## Stage-seed type counts", ""])
    lines.extend(_bullet_counts(_mapping(stage_seed.get("stage_seed_type_counts"))))
    lines.extend(["", "## Diagnostic hint counts", ""])
    lines.extend(_bullet_counts(_mapping(stage_seed.get("diagnostic_hint_counts"))))

    if production_only_stage_seed is not None:
        lines.extend(
            [
                "",
                "## Production-only stage-seed check",
                "",
                f"- Stage-seed rows: {production_only_stage_seed.get('total_stage_seed_rows', 0)}",
            ]
        )
        lines.extend(_bullet_counts(_mapping(production_only_stage_seed.get("stage_seed_type_counts"))))

    lines.extend(["", "## Casebook status counts", ""])
    lines.extend(_bullet_counts(_mapping(casebook.get("status_counts"))))
    lines.extend(["", "## Label-firing outcome counts", ""])
    lines.extend(_bullet_counts(_mapping(label_firing_audit.get("outcome_counts"))))
    lines.extend(["", "## Expectation counts", ""])
    lines.extend(_bullet_counts(_mapping(label_firing_audit.get("expectation_counts"))))

    lines.extend(["", "## Read", "", _validation_read(stage_seed, casebook, label_firing_audit), ""])
    return "\n".join(lines)


def _validation_read(
    stage_seed: Mapping[str, Any],
    casebook: Mapping[str, Any],
    label_firing_audit: Mapping[str, Any],
) -> str:
    fired = _int(label_firing_audit.get("fired_count"))
    blocked = _int(label_firing_audit.get("blocked_count"))
    needs_follow_through = _int(label_firing_audit.get("needs_follow_through_count"))
    stage_rows = _int(stage_seed.get("total_stage_seed_rows"))
    casebook_rows = _int(casebook.get("total_casebook_rows"))

    if fired:
        return (
            f"6C produced {fired} review-only recovery-sequence label(s). "
            f"Blocked={blocked}, needs_follow_through={needs_follow_through}. "
            "Review the casebook rows before any production activation decision."
        )
    if blocked or needs_follow_through:
        return (
            "6C found partial recovery-sequence structure, but no clean label fired. "
            f"Blocked={blocked}, needs_follow_through={needs_follow_through}. "
            "This remains a manual review/audit result only."
        )
    if stage_rows and casebook_rows:
        return (
            "6C stage seeds were found, but no clean recovery-sequence label fired. "
            "This usually means the saved evidence is diagnostic-only, missing a production anchor/test, or lacks fresh non-fallback follow-through."
        )
    return "No 6C stage seeds were found in the saved input rows."


def _bullet_counts(counts: Mapping[str, Any]) -> list[str]:
    if not counts:
        return ["- none"]
    return [f"- {key}: {value}" for key, value in sorted(counts.items())]


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _optional_mapping(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


__all__ = [
    "VSARecoverySequenceValidationArtifacts",
    "VSARecoverySequenceValidationReport",
    "build_vsa_recovery_sequence_validation_artifacts",
    "build_vsa_recovery_sequence_validation_report",
    "render_vsa_recovery_sequence_validation_markdown",
]
