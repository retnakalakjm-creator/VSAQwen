from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

MIXED_OUTCOME_LABEL = "mixed_follow_through_conflict"
DEFAULT_MIXED_CLUSTER_MAX_GAP_ROWS = 2

CSV_COLUMNS = (
    "cluster_id",
    "symbol",
    "start_week",
    "end_week",
    "start_bar_index",
    "end_bar_index",
    "row_count",
    "event_families",
    "event_codes",
    "qualifications",
    "source_buckets",
    "supporting_event_codes",
    "opposing_event_codes",
    "future_lifecycle_actions",
    "replay_weeks",
    "replay_bar_indices",
    "causal_read",
    "recommended_action",
)


@dataclass(frozen=True, slots=True)
class VSAMixedEventClusterReview:
    """Audit-only grouped review of nearby mixed VSA causality rows."""

    cluster_id: str
    symbol: str
    start_week: str
    end_week: str
    start_bar_index: int
    end_bar_index: int
    row_count: int
    event_families: tuple[str, ...]
    event_codes: tuple[str, ...]
    qualifications: tuple[str, ...]
    source_buckets: tuple[str, ...]
    supporting_event_codes: tuple[str, ...]
    opposing_event_codes: tuple[str, ...]
    future_lifecycle_actions: tuple[str, ...]
    replay_weeks: tuple[str, ...]
    replay_bar_indices: tuple[int, ...]
    causal_read: str
    recommended_action: str = "review_grouped_mixed_cluster_before_rule_change"
    audit_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "audit_only": self.audit_only,
            "cluster_id": self.cluster_id,
            "symbol": self.symbol,
            "start_week": self.start_week,
            "end_week": self.end_week,
            "start_bar_index": self.start_bar_index,
            "end_bar_index": self.end_bar_index,
            "row_count": self.row_count,
            "event_families": list(self.event_families),
            "event_codes": list(self.event_codes),
            "qualifications": list(self.qualifications),
            "source_buckets": list(self.source_buckets),
            "supporting_event_codes": list(self.supporting_event_codes),
            "opposing_event_codes": list(self.opposing_event_codes),
            "future_lifecycle_actions": list(self.future_lifecycle_actions),
            "replay_weeks": list(self.replay_weeks),
            "replay_bar_indices": list(self.replay_bar_indices),
            "causal_read": self.causal_read,
            "recommended_action": self.recommended_action,
        }


@dataclass(frozen=True, slots=True)
class VSAMixedEventClusterReviewSummary:
    """Compact audit-only grouped mixed-event review summary."""

    clusters: tuple[VSAMixedEventClusterReview, ...]
    total_input_rows: int
    total_mixed_rows: int
    total_clusters: int
    max_gap_rows: int
    symbol_counts: dict[str, int] = field(default_factory=dict)
    event_family_counts: dict[str, int] = field(default_factory=dict)
    top_cluster_symbols: tuple[dict[str, Any], ...] = ()
    audit_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "audit_only": self.audit_only,
            "max_gap_rows": self.max_gap_rows,
            "total_input_rows": self.total_input_rows,
            "total_mixed_rows": self.total_mixed_rows,
            "total_clusters": self.total_clusters,
            "symbol_counts": dict(self.symbol_counts),
            "event_family_counts": dict(self.event_family_counts),
            "top_cluster_symbols": [dict(row) for row in self.top_cluster_symbols],
            "clusters": [cluster.to_dict() for cluster in self.clusters],
        }


def build_vsa_mixed_event_cluster_review(
    payload: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    *,
    max_gap_rows: int = DEFAULT_MIXED_CLUSTER_MAX_GAP_ROWS,
) -> VSAMixedEventClusterReviewSummary:
    """Group nearby mixed follow-through/conflict causality rows.

    This helper consumes already-generated causality diagnostics JSON, usually the
    output of ``scripts/vsa_event_causality_diagnostics.py`` after PR #86. It
    does not load market data, call providers, replay scanners, mutate scanner
    state, persist output, activate detectors, alter scoring/ranking, or affect
    API/frontend production behavior.
    """

    if max_gap_rows < 0:
        raise ValueError("max_gap_rows must be zero or greater")

    source_rows = tuple(_extract_rows(payload))
    mixed_rows = tuple(sorted(_mixed_rows(source_rows), key=_row_sort_key))
    grouped = tuple(_cluster_rows(mixed_rows, max_gap_rows=max_gap_rows))
    clusters = tuple(_build_cluster(group) for group in grouped)

    return VSAMixedEventClusterReviewSummary(
        clusters=clusters,
        total_input_rows=len(source_rows),
        total_mixed_rows=len(mixed_rows),
        total_clusters=len(clusters),
        max_gap_rows=max_gap_rows,
        symbol_counts=_count(cluster.symbol for cluster in clusters),
        event_family_counts=_event_family_counts(clusters),
        top_cluster_symbols=_top_cluster_symbols(clusters),
    )


def render_vsa_mixed_event_cluster_review_csv(
    summary: VSAMixedEventClusterReviewSummary | Mapping[str, Any],
) -> str:
    """Render grouped mixed-event clusters to CSV for manual chart review."""

    rows = _cluster_dicts(summary)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(CSV_COLUMNS), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(_csv_row(row))
    return output.getvalue()


def _cluster_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    max_gap_rows: int,
) -> Iterable[tuple[Mapping[str, Any], ...]]:
    current: list[Mapping[str, Any]] = []
    last_symbol = ""
    last_bar_index = -1

    for row in rows:
        symbol = str(row.get("symbol", ""))
        bar_index = _int_or_default(row.get("replay_bar_index", row.get("bar_index")), -1)
        if not symbol or bar_index < 0:
            continue
        same_cluster = (
            current
            and symbol == last_symbol
            and bar_index - last_bar_index <= max_gap_rows
        )
        if not same_cluster:
            if current:
                yield tuple(current)
            current = []
        current.append(row)
        last_symbol = symbol
        last_bar_index = bar_index
    if current:
        yield tuple(current)


def _build_cluster(rows: Sequence[Mapping[str, Any]]) -> VSAMixedEventClusterReview:
    if not rows:
        raise ValueError("cannot build a mixed-event cluster from no rows")

    ordered = tuple(sorted(rows, key=_row_sort_key))
    symbol = str(ordered[0].get("symbol", ""))
    bar_indices = tuple(_int_or_default(row.get("replay_bar_index", row.get("bar_index")), -1) for row in ordered)
    replay_weeks = tuple(str(row.get("replay_week", row.get("week", ""))) for row in ordered)
    start_bar = min(bar_indices)
    end_bar = max(bar_indices)
    start_week = replay_weeks[0]
    end_week = replay_weeks[-1]
    event_families = _dedupe(str(row.get("event_family", "")) for row in ordered)
    event_codes = _dedupe(str(row.get("event_code", "")) for row in ordered)
    qualifications = _dedupe(str(row.get("qualification", "")) for row in ordered)
    source_buckets = _dedupe(str(row.get("source_bucket", "")) for row in ordered)
    support = _dedupe(_flatten(row.get("future_supporting_event_codes") for row in ordered))
    opposition = _dedupe(_flatten(row.get("future_opposing_event_codes") for row in ordered))
    lifecycle_actions = _dedupe(_flatten(row.get("future_lifecycle_actions") for row in ordered))

    return VSAMixedEventClusterReview(
        cluster_id=f"{symbol}:{start_bar}-{end_bar}",
        symbol=symbol,
        start_week=start_week,
        end_week=end_week,
        start_bar_index=start_bar,
        end_bar_index=end_bar,
        row_count=len(ordered),
        event_families=event_families,
        event_codes=event_codes,
        qualifications=qualifications,
        source_buckets=source_buckets,
        supporting_event_codes=support,
        opposing_event_codes=opposition,
        future_lifecycle_actions=lifecycle_actions,
        replay_weeks=replay_weeks,
        replay_bar_indices=bar_indices,
        causal_read=_cluster_causal_read(
            symbol=symbol,
            start_week=start_week,
            end_week=end_week,
            row_count=len(ordered),
            event_families=event_families,
            support=support,
            opposition=opposition,
            lifecycle_actions=lifecycle_actions,
        ),
    )


def _cluster_causal_read(
    *,
    symbol: str,
    start_week: str,
    end_week: str,
    row_count: int,
    event_families: tuple[str, ...],
    support: tuple[str, ...],
    opposition: tuple[str, ...],
    lifecycle_actions: tuple[str, ...],
) -> str:
    families = ", ".join(event_families) or "mixed VSA candidates"
    support_text = ", ".join(support) or "none"
    opposition_text = ", ".join(opposition) or "none"
    action_text = f" Lifecycle actions: {', '.join(lifecycle_actions)}." if lifecycle_actions else ""
    if start_week == end_week:
        window = start_week
    else:
        window = f"{start_week} to {end_week}"
    return (
        f"{symbol} has a {row_count}-row mixed-event cluster from {window}. "
        f"Families: {families}. Same-side evidence: {support_text}. "
        f"Opposing evidence: {opposition_text}.{action_text} "
        "Review the sequence as one cluster before activating or weighting any single event family."
    )


def _extract_rows(payload: Mapping[str, Any] | Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    if isinstance(payload, Mapping):
        if "rows" in payload:
            return tuple(dict(row) for row in _mapping_sequence(payload.get("rows")))
        if "clusters" in payload:
            # Already-grouped input is not a valid source for regrouping, but
            # treating clusters as rows keeps the helper deterministic.
            return tuple(dict(row) for row in _mapping_sequence(payload.get("clusters")))
        if "results" in payload:
            extracted: list[dict[str, Any]] = []
            for result in _mapping_sequence(payload.get("results")):
                extracted.extend(dict(row) for row in _mapping_sequence(result.get("rows")))
            return tuple(extracted)
        return (dict(payload),)
    return tuple(dict(row) for row in payload)


def _mixed_rows(rows: Sequence[Mapping[str, Any]]) -> Iterable[Mapping[str, Any]]:
    for row in rows:
        if str(row.get("outcome_label", "")) == MIXED_OUTCOME_LABEL:
            yield row


def _cluster_dicts(
    summary: VSAMixedEventClusterReviewSummary | Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    if isinstance(summary, VSAMixedEventClusterReviewSummary):
        return tuple(cluster.to_dict() for cluster in summary.clusters)
    return tuple(dict(row) for row in _mapping_sequence(summary.get("clusters")))


def _csv_row(row: Mapping[str, Any]) -> dict[str, str]:
    csv_row: dict[str, str] = {}
    for column in CSV_COLUMNS:
        value = row.get(column, "")
        if isinstance(value, (list, tuple)):
            csv_row[column] = ";".join(str(item) for item in value)
        else:
            csv_row[column] = str(value)
    return csv_row


def _event_family_counts(clusters: Sequence[VSAMixedEventClusterReview]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for cluster in clusters:
        for family in cluster.event_families:
            if not family:
                continue
            counts[family] = counts.get(family, 0) + 1
    return counts


def _top_cluster_symbols(
    clusters: Sequence[VSAMixedEventClusterReview],
    *,
    limit: int = 10,
) -> tuple[dict[str, Any], ...]:
    counts = _count(cluster.symbol for cluster in clusters)
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
    return tuple({"symbol": symbol, "cluster_count": count} for symbol, count in ordered)


def _count(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value)
        if not key:
            continue
        counts[key] = counts.get(key, 0) + 1
    return counts


def _row_sort_key(row: Mapping[str, Any]) -> tuple[str, int, str, str]:
    return (
        str(row.get("symbol", "")),
        _int_or_default(row.get("replay_bar_index", row.get("bar_index")), -1),
        str(row.get("replay_week", row.get("week", ""))),
        str(row.get("event_code", "")),
    )


def _mapping_sequence(value: Any) -> tuple[Mapping[str, Any], ...]:
    if value is None:
        return ()
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(item for item in value if isinstance(item, Mapping))
    return ()


def _flatten(values: Iterable[Any]) -> Iterable[str]:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            if value:
                yield value
            continue
        if isinstance(value, Iterable):
            for item in value:
                text = str(item)
                if text:
                    yield text
        else:
            text = str(value)
            if text:
                yield text


def _dedupe(values: Iterable[str]) -> tuple[str, ...]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value)
        if not text or text in seen:
            continue
        output.append(text)
        seen.add(text)
    return tuple(output)


def _int_or_default(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


__all__ = [
    "DEFAULT_MIXED_CLUSTER_MAX_GAP_ROWS",
    "MIXED_OUTCOME_LABEL",
    "VSAMixedEventClusterReview",
    "VSAMixedEventClusterReviewSummary",
    "build_vsa_mixed_event_cluster_review",
    "render_vsa_mixed_event_cluster_review_csv",
]
