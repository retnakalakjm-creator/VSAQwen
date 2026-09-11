from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from vsa_absorption_background_casebook import (
    build_vsa_absorption_background_casebook,
    render_vsa_absorption_background_casebook_csv,
)
from vsa_absorption_background_labels import ABSORPTION_BACKGROUND_PLAIN_ENGLISH


@dataclass(frozen=True, slots=True)
class VSAAbsorptionBackgroundValidationReport:
    """Repeatable audit-only validation report for 6D absorption background."""

    casebook_summary: Any
    production_only_summary: Any
    lookback_rows: int
    lookahead_rows: int
    audit_only: bool = True
    production_safe: bool = True

    def to_dict(self) -> dict[str, Any]:
        casebook_payload = self.casebook_summary.to_dict()
        production_only_payload = self.production_only_summary.to_dict()
        return {
            "audit_only": self.audit_only,
            "production_safe": self.production_safe,
            "lookback_rows": self.lookback_rows,
            "lookahead_rows": self.lookahead_rows,
            "plain_english": ABSORPTION_BACKGROUND_PLAIN_ENGLISH,
            "total_input_rows": casebook_payload["total_input_rows"],
            "total_casebook_rows": casebook_payload["total_casebook_rows"],
            "status_counts": dict(casebook_payload["status_counts"]),
            "case_type_counts": dict(casebook_payload["case_type_counts"]),
            "seed_type_counts": dict(casebook_payload["seed_type_counts"]),
            "recommended_action_counts": dict(casebook_payload["recommended_action_counts"]),
            "diagnostic_hint_counts": dict(casebook_payload["diagnostic_hint_counts"]),
            "production_only": {
                "total_casebook_rows": production_only_payload["total_casebook_rows"],
                "status_counts": dict(production_only_payload["status_counts"]),
                "case_type_counts": dict(production_only_payload["case_type_counts"]),
                "seed_type_counts": dict(production_only_payload["seed_type_counts"]),
                "recommended_action_counts": dict(
                    production_only_payload["recommended_action_counts"]
                ),
                "diagnostic_hint_counts": dict(
                    production_only_payload["diagnostic_hint_counts"]
                ),
            },
            "top_casebook_items": [dict(item) for item in casebook_payload["top_casebook_items"]],
            "rows": [dict(row) for row in casebook_payload["rows"]],
        }


def build_vsa_absorption_background_validation_report(
    payload: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    *,
    lookback_rows: int = 3,
    lookahead_rows: int = 3,
) -> VSAAbsorptionBackgroundValidationReport:
    """Run the 6D saved-output validation chain.

    This helper only delegates to the already audit-only absorption-background
    casebook builder. It does not load market data, call providers, replay
    scanners, mutate scanner state, activate detectors, change scoring/ranking,
    write persistence, or touch API/frontend behavior.
    """

    safe_lookback = max(0, int(lookback_rows))
    safe_lookahead = max(0, int(lookahead_rows))
    casebook_summary = build_vsa_absorption_background_casebook(
        payload,
        lookback_rows=safe_lookback,
        lookahead_rows=safe_lookahead,
        include_diagnostic_hints=True,
    )
    production_only_summary = build_vsa_absorption_background_casebook(
        payload,
        lookback_rows=safe_lookback,
        lookahead_rows=safe_lookahead,
        include_diagnostic_hints=False,
    )
    return VSAAbsorptionBackgroundValidationReport(
        casebook_summary=casebook_summary,
        production_only_summary=production_only_summary,
        lookback_rows=safe_lookback,
        lookahead_rows=safe_lookahead,
    )


def render_vsa_absorption_background_validation_report_markdown(
    report: VSAAbsorptionBackgroundValidationReport | Mapping[str, Any],
) -> str:
    """Render a concise Markdown validation report for saved 6D absorption output."""

    payload = report.to_dict() if isinstance(report, VSAAbsorptionBackgroundValidationReport) else dict(report)
    production_only = dict(payload.get("production_only", {}))

    lines = [
        "# 6D Absorption Background Saved-Output Validation",
        "",
        "## Scope",
        "",
        "This report is audit-only and production-safe. It reads saved audit/replay rows only.",
        "",
        "It does not load market data, call providers, replay scanners, mutate scanner state, "
        "activate detectors, change scoring/ranking, write persistence, or touch API/frontend behavior.",
        "",
        "## Plain-English frontend contract",
        "",
        str(payload.get("plain_english", ABSORPTION_BACKGROUND_PLAIN_ENGLISH)),
        "",
        "## Input and window",
        "",
        f"- Saved replay rows checked: {payload.get('total_input_rows', 0)}",
        f"- Lookback rows: {payload.get('lookback_rows', 0)}",
        f"- Lookahead rows: {payload.get('lookahead_rows', 0)}",
        "",
        "## Casebook output",
        "",
        f"- Casebook rows: {payload.get('total_casebook_rows', 0)}",
        "",
        "### Status counts",
        "",
        *_bullet_counts(payload.get("status_counts", {})),
        "",
        "### Seed type counts",
        "",
        *_bullet_counts(payload.get("seed_type_counts", {})),
        "",
        "### Diagnostic hint counts",
        "",
        *_bullet_counts(payload.get("diagnostic_hint_counts", {})),
        "",
        "## Production-only cross-check",
        "",
        f"- Production-only casebook rows: {production_only.get('total_casebook_rows', 0)}",
        "",
        "### Production-only status counts",
        "",
        *_bullet_counts(production_only.get("status_counts", {})),
        "",
        "## Top casebook items",
        "",
        *_top_items(payload.get("top_casebook_items", ())),
        "",
        "## Conservative interpretation",
        "",
        _interpretation(payload),
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def render_vsa_absorption_background_validation_casebook_csv(
    report: VSAAbsorptionBackgroundValidationReport | Mapping[str, Any],
) -> str:
    """Render the main casebook rows from a validation report to CSV."""

    if isinstance(report, VSAAbsorptionBackgroundValidationReport):
        return render_vsa_absorption_background_casebook_csv(report.casebook_summary)
    return render_vsa_absorption_background_casebook_csv({"rows": report.get("rows", ())})


def _bullet_counts(counts: Mapping[str, Any]) -> list[str]:
    if not counts:
        return ["- none"]
    return [f"- {key}: {value}" for key, value in sorted(counts.items())]


def _top_items(items: Any) -> list[str]:
    if not items:
        return ["- none"]
    lines: list[str] = []
    for item in list(items)[:10]:
        if not isinstance(item, Mapping):
            continue
        lines.append(
            "- "
            f"{item.get('symbol', '')} "
            f"{item.get('replay_week', '')}: "
            f"{item.get('case_type', '')} / "
            f"{item.get('recommended_casebook_action', '')}"
        )
    return lines or ["- none"]


def _interpretation(payload: Mapping[str, Any]) -> str:
    status_counts = dict(payload.get("status_counts", {}))
    review_count = int(status_counts.get("absorption_background_review", 0))
    blocked_count = int(status_counts.get("absorption_background_blocked", 0))
    needs_count = int(status_counts.get("absorption_background_needs_follow_through", 0))
    none_count = int(status_counts.get("none", 0))

    if review_count:
        return (
            "At least one clean review-only absorption-background marker fired. "
            "This still means chart review, not an automatic bullish flip."
        )
    if blocked_count or needs_count:
        return (
            "Absorption-style evidence exists, but the current saved output remains conservative: "
            "some rows are blocked or need fresh follow-through, and no automatic bullish flip is allowed."
        )
    if none_count:
        return (
            "Saved rows produced only non-firing absorption-background cases. Diagnostic hints, if present, "
            "remain review context and are not promoted into production labels."
        )
    return "No absorption-background casebook rows were produced from the saved output."


__all__ = [
    "VSAAbsorptionBackgroundValidationReport",
    "build_vsa_absorption_background_validation_report",
    "render_vsa_absorption_background_validation_casebook_csv",
    "render_vsa_absorption_background_validation_report_markdown",
]
