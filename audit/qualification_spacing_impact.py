"""Counterfactual audit for structural qualification event spacing.

This module is analysis-only. It compares the current production qualification
selector with a strict pairwise-spacing interpretation using the already-frozen
K14 structural progression event stream. Production qualification behavior is
not modified here.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from audit.progression_directional_outcomes import (
    ProgressionDirectionalityArtifactInput,
)
from audit.progression_directionality_semantics import (
    ProgressionDirectionalityRow,
)
from background.qualification import (
    PatternQualification,
    PatternQualificationEngine,
)
from models import (
    Evidence,
    EvidenceCategory,
    EvidenceCode,
    EvidenceDirection,
)


QUALIFICATION_SPACING_IMPACT_AUDIT_ID = (
    "qualification-spacing-counterfactual-v1"
)


@dataclass(frozen=True, slots=True)
class QualificationSpacingImpactRow:
    symbol: str
    campaign_id: int
    event_bar_index: int
    event_week: str
    event_direction: str
    previous_event_bar_index: int | None
    bars_since_previous_event: int | None
    current_qualification: PatternQualification
    current_selected_bars: tuple[int, ...]
    strict_qualification: PatternQualification
    strict_selected_bars: tuple[int, ...]
    diverged: bool
    divergence_kind: str


@dataclass(frozen=True, slots=True)
class QualificationSpacingSymbolSummary:
    symbol: str
    event_count: int
    campaign_count: int
    divergence_event_count: int
    affected_campaign_count: int
    first_divergence_bar_index: int | None
    first_divergence_week: str | None
    current_persistent_onset_count: int
    strict_persistent_onset_count: int


@dataclass(frozen=True, slots=True)
class QualificationSpacingImpactAudit:
    audit_id: str
    basket_name: str
    requested_symbol_count: int
    event_count: int
    affected_symbol_count: int
    affected_campaign_count: int
    divergence_event_count: int
    rows: tuple[QualificationSpacingImpactRow, ...]
    symbol_summaries: tuple[QualificationSpacingSymbolSummary, ...]

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class QualificationSpacingImpactAuditPaths:
    summary_json: Path
    event_ledger_csv: Path
    symbol_summary_csv: Path

    def as_dict(self) -> dict[str, str]:
        return {
            "summary_json": str(self.summary_json),
            "event_ledger_csv": str(self.event_ledger_csv),
            "symbol_summary_csv": str(self.symbol_summary_csv),
        }


def _evidence_from_row(row: ProgressionDirectionalityRow) -> Evidence:
    if row.event_direction == "bullish":
        code = EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING
        direction = EvidenceDirection.BULLISH
    elif row.event_direction == "bearish":
        code = EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING
        direction = EvidenceDirection.BEARISH
    else:
        raise ValueError(
            f"unsupported progression direction: {row.event_direction}"
        )

    return Evidence(
        code=code,
        category=EvidenceCategory.TREND,
        direction=direction,
        strength=1.0,
        weight=0.0,
        observation="structural progression",
        description="qualification spacing counterfactual",
        bar_index=row.event_bar_index,
        week_beginning=row.event_week,
    )


def _legacy_selected(
    events: tuple[Evidence, ...],
) -> tuple[Evidence, ...]:
    """Reproduce the pre-fix newest-anchor production selector."""

    if not events:
        return ()

    qualifying = [events[-1]]
    newest = events[-1]

    for event in reversed(events[:-1]):
        if (
            newest.bar_index - event.bar_index
            < PatternQualificationEngine.MIN_EVENT_SPACING_BARS
        ):
            continue

        qualifying.append(event)
        if (
            len(qualifying)
            >= PatternQualificationEngine.MIN_QUALIFYING_EVENTS
        ):
            break

    qualifying.reverse()
    if (
        len(qualifying)
        < PatternQualificationEngine.MIN_QUALIFYING_EVENTS
    ):
        return ()
    return tuple(qualifying)


def _strict_selected(
    events: tuple[Evidence, ...],
) -> tuple[Evidence, ...]:
    if not events:
        return ()

    qualifying = [events[-1]]
    last_accepted = events[-1]

    for event in reversed(events[:-1]):
        if (
            last_accepted.bar_index - event.bar_index
            < PatternQualificationEngine.MIN_EVENT_SPACING_BARS
        ):
            continue

        qualifying.append(event)
        last_accepted = event
        if (
            len(qualifying)
            >= PatternQualificationEngine.MIN_QUALIFYING_EVENTS
        ):
            break

    qualifying.reverse()
    if (
        len(qualifying)
        < PatternQualificationEngine.MIN_QUALIFYING_EVENTS
    ):
        return ()
    return tuple(qualifying)


def _qualification_for_selected(
    selected: tuple[Evidence, ...],
) -> PatternQualification:
    if not selected:
        return PatternQualification.UNQUALIFIED
    direction = selected[-1].direction
    if direction is EvidenceDirection.BULLISH:
        return PatternQualification.PERSISTENT_BULLISH
    if direction is EvidenceDirection.BEARISH:
        return PatternQualification.PERSISTENT_BEARISH
    return PatternQualification.UNQUALIFIED


def _divergence_kind(
    current: PatternQualification,
    strict: PatternQualification,
) -> str:
    if current is strict:
        return "none"
    if (
        current is not PatternQualification.UNQUALIFIED
        and strict is PatternQualification.UNQUALIFIED
    ):
        return "current_persistent_strict_unqualified"
    if (
        current is PatternQualification.UNQUALIFIED
        and strict is not PatternQualification.UNQUALIFIED
    ):
        return "strict_persistent_current_unqualified"
    return "direction_mismatch"


def _is_persistent(value: PatternQualification) -> bool:
    return value is not PatternQualification.UNQUALIFIED


def _audit_symbol(
    *,
    symbol: str,
    rows: tuple[ProgressionDirectionalityRow, ...],
) -> tuple[
    tuple[QualificationSpacingImpactRow, ...],
    QualificationSpacingSymbolSummary,
]:
    campaign: list[Evidence] = []
    output: list[QualificationSpacingImpactRow] = []

    campaign_id = 0
    previous_direction: EvidenceDirection | None = None
    previous_event_bar: int | None = None
    previous_current = PatternQualification.UNQUALIFIED
    previous_strict = PatternQualification.UNQUALIFIED
    current_onsets = 0
    strict_onsets = 0

    for row in sorted(rows, key=lambda item: item.event_bar_index):
        event = _evidence_from_row(row)

        if (
            previous_direction is None
            or event.direction != previous_direction
        ):
            campaign_id += 1
            campaign = [event]
        else:
            campaign.append(event)

        current_selected = _legacy_selected(tuple(campaign))
        current_qualification = _qualification_for_selected(
            current_selected
        )
        strict_selected = _strict_selected(tuple(campaign))
        strict_qualification = _qualification_for_selected(strict_selected)

        if (
            _is_persistent(current_qualification)
            and not _is_persistent(previous_current)
        ):
            current_onsets += 1
        if (
            _is_persistent(strict_qualification)
            and not _is_persistent(previous_strict)
        ):
            strict_onsets += 1

        diverged = current_qualification is not strict_qualification
        output.append(
            QualificationSpacingImpactRow(
                symbol=symbol,
                campaign_id=campaign_id,
                event_bar_index=event.bar_index,
                event_week=row.event_week,
                event_direction=row.event_direction,
                previous_event_bar_index=previous_event_bar,
                bars_since_previous_event=(
                    None
                    if previous_event_bar is None
                    else event.bar_index - previous_event_bar
                ),
                current_qualification=current_qualification,
                current_selected_bars=tuple(
                    item.bar_index for item in current_selected
                ),
                strict_qualification=strict_qualification,
                strict_selected_bars=tuple(
                    item.bar_index for item in strict_selected
                ),
                diverged=diverged,
                divergence_kind=_divergence_kind(
                    current_qualification,
                    strict_qualification,
                ),
            )
        )

        previous_direction = event.direction
        previous_event_bar = event.bar_index
        previous_current = current_qualification
        previous_strict = strict_qualification

    divergence_rows = [item for item in output if item.diverged]
    affected_campaigns = {
        item.campaign_id for item in divergence_rows
    }
    first = divergence_rows[0] if divergence_rows else None

    return (
        tuple(output),
        QualificationSpacingSymbolSummary(
            symbol=symbol,
            event_count=len(output),
            campaign_count=campaign_id,
            divergence_event_count=len(divergence_rows),
            affected_campaign_count=len(affected_campaigns),
            first_divergence_bar_index=(
                None if first is None else first.event_bar_index
            ),
            first_divergence_week=(
                None if first is None else first.event_week
            ),
            current_persistent_onset_count=current_onsets,
            strict_persistent_onset_count=strict_onsets,
        ),
    )


def build_qualification_spacing_impact_audit(
    artifact_input: ProgressionDirectionalityArtifactInput,
) -> QualificationSpacingImpactAudit:
    all_rows: list[QualificationSpacingImpactRow] = []
    summaries: list[QualificationSpacingSymbolSummary] = []

    for symbol in artifact_input.requested_symbols:
        rows, summary = _audit_symbol(
            symbol=symbol,
            rows=artifact_input.rows_by_symbol[symbol],
        )
        expected = artifact_input.event_counts_by_symbol[symbol]
        if len(rows) != expected:
            raise ValueError(
                f"{symbol} spacing audit count mismatch: "
                f"{len(rows)} != {expected}"
            )
        all_rows.extend(rows)
        summaries.append(summary)

    affected_symbols = {
        item.symbol
        for item in all_rows
        if item.diverged
    }
    affected_campaigns = {
        (item.symbol, item.campaign_id)
        for item in all_rows
        if item.diverged
    }

    return QualificationSpacingImpactAudit(
        audit_id=QUALIFICATION_SPACING_IMPACT_AUDIT_ID,
        basket_name=artifact_input.basket_name,
        requested_symbol_count=len(artifact_input.requested_symbols),
        event_count=len(all_rows),
        affected_symbol_count=len(affected_symbols),
        affected_campaign_count=len(affected_campaigns),
        divergence_event_count=sum(
            1 for item in all_rows if item.diverged
        ),
        rows=tuple(all_rows),
        symbol_summaries=tuple(summaries),
    )


def _row_payload(
    row: QualificationSpacingImpactRow,
) -> dict[str, object]:
    payload = asdict(row)
    payload["current_qualification"] = row.current_qualification.value
    payload["strict_qualification"] = row.strict_qualification.value
    payload["current_selected_bars"] = ";".join(
        str(item) for item in row.current_selected_bars
    )
    payload["strict_selected_bars"] = ";".join(
        str(item) for item in row.strict_selected_bars
    )
    return payload


def write_qualification_spacing_impact_audit(
    audit: QualificationSpacingImpactAudit,
    output_dir: str | Path,
) -> QualificationSpacingImpactAuditPaths:
    import pandas as pd

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = QualificationSpacingImpactAuditPaths(
        summary_json=root / "qualification_spacing_impact_summary.json",
        event_ledger_csv=root / "qualification_spacing_impact_events.csv",
        symbol_summary_csv=root / "qualification_spacing_impact_symbols.csv",
    )

    summary = {
        "audit_id": audit.audit_id,
        "basket_name": audit.basket_name,
        "requested_symbol_count": audit.requested_symbol_count,
        "event_count": audit.event_count,
        "affected_symbol_count": audit.affected_symbol_count,
        "affected_campaign_count": audit.affected_campaign_count,
        "divergence_event_count": audit.divergence_event_count,
        "min_qualifying_events": (
            PatternQualificationEngine.MIN_QUALIFYING_EVENTS
        ),
        "min_event_spacing_bars": (
            PatternQualificationEngine.MIN_EVENT_SPACING_BARS
        ),
        "current_selector": (
            "pre-fix production: compare every older candidate "
            "against newest event"
        ),
        "strict_counterfactual": (
            "compare every older candidate against last accepted event"
        ),
        "is_actionable": False,
    }
    paths.summary_json.write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    pd.DataFrame(
        [_row_payload(item) for item in audit.rows],
    ).to_csv(paths.event_ledger_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.symbol_summaries],
    ).to_csv(paths.symbol_summary_csv, index=False)
    return paths


__all__ = [
    "QUALIFICATION_SPACING_IMPACT_AUDIT_ID",
    "QualificationSpacingImpactAudit",
    "QualificationSpacingImpactAuditPaths",
    "QualificationSpacingImpactRow",
    "QualificationSpacingSymbolSummary",
    "build_qualification_spacing_impact_audit",
    "write_qualification_spacing_impact_audit",
]
