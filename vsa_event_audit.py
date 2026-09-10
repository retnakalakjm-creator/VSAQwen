from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

import pandas as pd

from engine.columns import (
    COL_CLOSE,
    COL_CLOSE_RATIO,
    COL_DIRECTION,
    COL_HIGH,
    COL_LOW,
    COL_OPEN,
    COL_PRICE_CHANGE_PCT,
    COL_SPREAD_CLASS,
    COL_SPREAD_PERCENTILE,
    COL_SPREAD_RATIO,
    COL_VOLUME_CLASS,
    COL_VOLUME_PERCENTILE,
    COL_VOLUME_RATIO,
    COL_WEEK,
)
from metrics_engine import MetricsEngine
from scanner import ScannerEngine

DEFAULT_AUDIT_HORIZON_WEEKS = 20
DEFAULT_MAX_AUDIT_SYMBOLS = 30
MAX_AUDIT_SYMBOLS = 100
MAX_AUDIT_REPLAY_WEEKS = 104
AUDIT_TIMEFRAME = "1W"

STRUCTURAL_EVENT_PREFIX = "structural_progression"

AUDIT_FLAG_NO_TARGET_EVENT = "no_target_event"
AUDIT_FLAG_FALLBACK_SCORING_EVIDENCE = "fallback_scoring_evidence"
AUDIT_FLAG_STALE_SCORING_EVIDENCE = "stale_scoring_evidence"
AUDIT_FLAG_ACTIONABLE_AUDIT_ROW = "actionable_audit_row"
AUDIT_FLAG_STRUCTURAL_EVENT_WITHOUT_VSA_CONFIRMATION = (
    "structural_event_without_vsa_confirmation"
)
AUDIT_FLAG_BULLISH_VSA_AGAINST_BEARISH_QUALIFICATION = (
    "bullish_vsa_against_bearish_qualification"
)
AUDIT_FLAG_BEARISH_VSA_AGAINST_BULLISH_QUALIFICATION = (
    "bearish_vsa_against_bullish_qualification"
)
AUDIT_FLAG_CONFLICTING_TARGET_VSA_PRESSURE = "conflicting_target_vsa_pressure"
AUDIT_FLAG_CONFLICTING_SCORING_VSA_PRESSURE = "conflicting_scoring_vsa_pressure"
AUDIT_FLAG_QUALIFICATION_WITHOUT_CURRENT_EVIDENCE = (
    "qualification_without_current_evidence"
)

DETECTOR_DIAGNOSTIC_POTENTIAL_STOPPING_VOLUME = (
    "review_potential_stopping_volume"
)
DETECTOR_DIAGNOSTIC_POTENTIAL_EFFORT_GT_RESULT = (
    "review_potential_effort_gt_result"
)
DETECTOR_DIAGNOSTIC_POTENTIAL_ABSORPTION = "review_potential_absorption"
DETECTOR_DIAGNOSTIC_POTENTIAL_SPRING_OR_SHAKEOUT = (
    "review_potential_spring_or_shakeout"
)
DETECTOR_DIAGNOSTIC_HIGH_VOLUME_REVERSAL_WITHOUT_BULLISH_EVENT = (
    "review_high_volume_reversal_without_bullish_event"
)

BULLISH_VSA_CODES = frozenset(
    {
        "stopping_volume",
        "demand_coming_in",
        "increasing_demand",
        "hidden_demand",
        "demand_drying_up",
        "no_supply",
        "spring",
        "test",
        "selling_climax",
        "shakeout",
        "absorption",
    }
)
BEARISH_VSA_CODES = frozenset(
    {
        "buying_climax",
        "supply_coming_in",
        "increasing_supply",
        "hidden_supply",
        "supply_high_volume",
        "supply_wide_spread",
        "supply_absorption",
        "upthrust",
        "no_demand",
        "supply_drying_up",
    }
)


@dataclass(frozen=True, slots=True)
class VSAEventAuditRow:
    """Compact point-in-time event row for one replay week."""

    symbol: str
    replay_bar_index: int
    replay_week: str
    target_event_codes: tuple[str, ...]
    scoring_event_codes: tuple[str, ...]
    qualifying_event_codes: tuple[str, ...]
    campaign_event_codes: tuple[str, ...]
    structural_event_codes: tuple[str, ...]
    vsa_event_codes: tuple[str, ...]
    qualification: str
    actionable: bool
    used_fallback_evidence: bool
    scoring_evidence_age: int | None
    net_pressure: float
    confidence: float
    audit_flags: tuple[str, ...] = field(default_factory=tuple)
    detector_diagnostics: tuple[str, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def event_count(self) -> int:
        return len(self.target_event_codes)

    def to_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "replay_bar_index": self.replay_bar_index,
            "replay_week": self.replay_week,
            "event_count": self.event_count,
            "target_event_codes": list(self.target_event_codes),
            "scoring_event_codes": list(self.scoring_event_codes),
            "qualifying_event_codes": list(self.qualifying_event_codes),
            "campaign_event_codes": list(self.campaign_event_codes),
            "structural_event_codes": list(self.structural_event_codes),
            "vsa_event_codes": list(self.vsa_event_codes),
            "qualification": self.qualification,
            "actionable": self.actionable,
            "used_fallback_evidence": self.used_fallback_evidence,
            "scoring_evidence_age": self.scoring_evidence_age,
            "net_pressure": self.net_pressure,
            "confidence": self.confidence,
            "audit_flags": list(self.audit_flags),
            "detector_diagnostics": list(self.detector_diagnostics),
            "notes": list(self.notes),
        }


@dataclass(frozen=True, slots=True)
class VSAEventAuditSymbolResult:
    """Audit rows and bounds for one symbol."""

    symbol: str
    timeframe: str
    start_week: str | None
    end_week: str | None
    replay_weeks: int
    rows: tuple[VSAEventAuditRow, ...]
    audit_only: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "start_week": self.start_week,
            "end_week": self.end_week,
            "replay_weeks": self.replay_weeks,
            "rows": [row.to_dict() for row in self.rows],
            "audit_only": self.audit_only,
        }


def parse_symbol_list(
    symbols: str | Sequence[str],
    *,
    max_symbols: int = DEFAULT_MAX_AUDIT_SYMBOLS,
) -> list[str]:
    """Parse a compact symbol list while keeping the API safe for batch audits."""

    if max_symbols <= 0:
        raise ValueError("max_symbols must be greater than zero")

    if isinstance(symbols, str):
        raw = symbols.replace("\n", ",").replace(";", ",").split(",")
    else:
        raw = list(symbols)

    parsed: list[str] = []
    seen: set[str] = set()
    for item in raw:
        symbol = str(item).strip().upper()
        if not symbol or symbol in seen:
            continue
        parsed.append(symbol)
        seen.add(symbol)

    if not parsed:
        raise ValueError("at least one symbol is required")
    if len(parsed) > max_symbols:
        raise ValueError(f"symbol count exceeds max_symbols={max_symbols}")
    if len(parsed) > MAX_AUDIT_SYMBOLS:
        raise ValueError(f"symbol count exceeds hard limit {MAX_AUDIT_SYMBOLS}")
    return parsed


def build_vsa_event_audit(
    *,
    symbol: str,
    weekly: pd.DataFrame,
    start_week: str | None = None,
    end_week: str | None = None,
    horizon_weeks: int = DEFAULT_AUDIT_HORIZON_WEEKS,
    max_replay_weeks: int = MAX_AUDIT_REPLAY_WEEKS,
    scanner: Any | None = None,
) -> VSAEventAuditSymbolResult:
    """Replay a symbol point-in-time and return compact VSA event rows.

    The caller owns data loading. In production this lets the API/service reuse
    the existing cached and incremental-refresh data path once per symbol. This
    function then performs one bounded scanner pass over the requested completed
    weekly window and returns compact audit rows instead of a historical
    warehouse.
    """

    if weekly.empty:
        raise ValueError("weekly data cannot be empty")
    if COL_WEEK not in weekly.columns:
        raise ValueError(f"weekly data must contain {COL_WEEK}")
    if horizon_weeks <= 0:
        raise ValueError("horizon_weeks must be greater than zero")
    if max_replay_weeks <= 0:
        raise ValueError("max_replay_weeks must be greater than zero")

    metrics = MetricsEngine().calculate(weekly)
    if len(metrics) <= ScannerEngine.MIN_REPLAY_BARS:
        raise ValueError(
            "not enough completed weekly bars for point-in-time audit"
        )

    start_index, end_index = _resolve_replay_bounds(
        metrics,
        start_week=start_week,
        end_week=end_week,
        horizon_weeks=horizon_weeks,
        min_index=ScannerEngine.MIN_REPLAY_BARS,
    )
    replay_weeks = end_index - start_index + 1
    if replay_weeks > max_replay_weeks:
        raise ValueError(
            f"requested audit window has {replay_weeks} weeks; "
            f"limit is {max_replay_weeks}"
        )

    scanner_engine = scanner if scanner is not None else ScannerEngine()
    candidates = scanner_engine.scan(metrics.iloc[: end_index + 1].copy())

    rows = tuple(
        _candidate_to_row(symbol, candidate, metrics=metrics)
        for candidate in candidates
        if _candidate_bar_index(candidate) is not None
        and start_index <= _candidate_bar_index(candidate) <= end_index
    )

    return VSAEventAuditSymbolResult(
        symbol=symbol,
        timeframe=AUDIT_TIMEFRAME,
        start_week=_week_at(metrics, start_index),
        end_week=_week_at(metrics, end_index),
        replay_weeks=replay_weeks,
        rows=rows,
    )


def _resolve_replay_bounds(
    metrics: pd.DataFrame,
    *,
    start_week: str | None,
    end_week: str | None,
    horizon_weeks: int,
    min_index: int,
) -> tuple[int, int]:
    max_index = len(metrics) - 1

    if end_week:
        end_index = _last_index_on_or_before(metrics, end_week)
    else:
        end_index = max_index

    if start_week:
        start_index = _first_index_on_or_after(metrics, start_week)
        if not end_week:
            end_index = min(max_index, start_index + horizon_weeks - 1)
    else:
        start_index = max(min_index, end_index - horizon_weeks + 1)

    start_index = max(start_index, min_index)
    end_index = min(end_index, max_index)
    if end_index < start_index:
        raise ValueError("audit date range does not include enough replay bars")
    return start_index, end_index


def _first_index_on_or_after(metrics: pd.DataFrame, week: str) -> int:
    target = pd.Timestamp(week)
    for index, value in enumerate(metrics[COL_WEEK]):
        if pd.Timestamp(value) >= target:
            return index
    raise ValueError(f"start_week is after available data: {week}")


def _last_index_on_or_before(metrics: pd.DataFrame, week: str) -> int:
    target = pd.Timestamp(week)
    selected: int | None = None
    for index, value in enumerate(metrics[COL_WEEK]):
        if pd.Timestamp(value) <= target:
            selected = index
        else:
            break
    if selected is None:
        raise ValueError(f"end_week is before available data: {week}")
    return selected


def _candidate_to_row(
    symbol: str,
    candidate: Any,
    *,
    metrics: pd.DataFrame,
) -> VSAEventAuditRow:
    target_codes = _event_codes(getattr(candidate, "target_bar_evidence", ()))
    scoring_codes = _event_codes(getattr(candidate, "scoring_evidence", ()))
    qualifying_codes = _event_codes(getattr(candidate, "qualifying_evidence", ()))
    campaign_codes = _event_codes(getattr(candidate, "campaign_evidence", ()))
    structural_codes = tuple(
        code for code in target_codes if _is_structural_event_code(code)
    )
    vsa_codes = tuple(
        code for code in target_codes if not _is_structural_event_code(code)
    )
    qualification = _enum_text(getattr(candidate, "qualification", ""))
    replay_bar_index = _candidate_bar_index(candidate)
    if replay_bar_index is None:
        raise ValueError("candidate is missing bar_index")

    audit_flags = _audit_flags(
        candidate,
        target_codes=target_codes,
        scoring_codes=scoring_codes,
        campaign_codes=campaign_codes,
        structural_codes=structural_codes,
        vsa_codes=vsa_codes,
        qualification=qualification,
    )
    detector_diagnostics = _detector_diagnostics(
        metrics,
        replay_bar_index,
        target_codes=target_codes,
        scoring_codes=scoring_codes,
        campaign_codes=campaign_codes,
        qualification=qualification,
    )
    notes = _audit_notes(
        candidate,
        target_codes,
        scoring_codes,
        audit_flags,
        detector_diagnostics,
    )
    return VSAEventAuditRow(
        symbol=symbol,
        replay_bar_index=replay_bar_index,
        replay_week=str(getattr(candidate, "week", "")),
        target_event_codes=target_codes,
        scoring_event_codes=scoring_codes,
        qualifying_event_codes=qualifying_codes,
        campaign_event_codes=campaign_codes,
        structural_event_codes=structural_codes,
        vsa_event_codes=vsa_codes,
        qualification=qualification,
        actionable=bool(getattr(candidate, "actionable", False)),
        used_fallback_evidence=bool(getattr(candidate, "used_fallback_evidence", False)),
        scoring_evidence_age=getattr(candidate, "scoring_evidence_age", None),
        net_pressure=float(getattr(candidate, "net_pressure", 0.0)),
        confidence=float(getattr(candidate, "confidence", 0.0)),
        audit_flags=audit_flags,
        detector_diagnostics=detector_diagnostics,
        notes=notes,
    )


def _audit_flags(
    candidate: Any,
    *,
    target_codes: tuple[str, ...],
    scoring_codes: tuple[str, ...],
    campaign_codes: tuple[str, ...],
    structural_codes: tuple[str, ...],
    vsa_codes: tuple[str, ...],
    qualification: str,
) -> tuple[str, ...]:
    flags: list[str] = []

    if not target_codes:
        flags.append(AUDIT_FLAG_NO_TARGET_EVENT)

    if scoring_codes and (
        not target_codes or bool(getattr(candidate, "used_fallback_evidence", False))
    ):
        flags.append(AUDIT_FLAG_FALLBACK_SCORING_EVIDENCE)

    scoring_age = getattr(candidate, "scoring_evidence_age", None)
    if scoring_age is not None and scoring_age > ScannerEngine.MAX_ACTIONABLE_VSA_AGE:
        flags.append(AUDIT_FLAG_STALE_SCORING_EVIDENCE)

    if bool(getattr(candidate, "actionable", False)):
        flags.append(AUDIT_FLAG_ACTIONABLE_AUDIT_ROW)

    if structural_codes and not vsa_codes:
        flags.append(AUDIT_FLAG_STRUCTURAL_EVENT_WITHOUT_VSA_CONFIRMATION)

    if _is_bearish_qualification(qualification) and _has_bullish_vsa(vsa_codes):
        flags.append(AUDIT_FLAG_BULLISH_VSA_AGAINST_BEARISH_QUALIFICATION)

    if _is_bullish_qualification(qualification) and _has_bearish_vsa(vsa_codes):
        flags.append(AUDIT_FLAG_BEARISH_VSA_AGAINST_BULLISH_QUALIFICATION)

    if _has_bullish_vsa(vsa_codes) and _has_bearish_vsa(vsa_codes):
        flags.append(AUDIT_FLAG_CONFLICTING_TARGET_VSA_PRESSURE)

    if _has_bullish_vsa(scoring_codes) and _has_bearish_vsa(scoring_codes):
        flags.append(AUDIT_FLAG_CONFLICTING_SCORING_VSA_PRESSURE)

    if (
        _is_persistent_qualification(qualification)
        and not target_codes
        and not scoring_codes
        and not campaign_codes
    ):
        flags.append(AUDIT_FLAG_QUALIFICATION_WITHOUT_CURRENT_EVIDENCE)

    return _dedupe(flags)


def _detector_diagnostics(
    metrics: pd.DataFrame,
    bar_index: int,
    *,
    target_codes: tuple[str, ...],
    scoring_codes: tuple[str, ...],
    campaign_codes: tuple[str, ...],
    qualification: str,
) -> tuple[str, ...]:
    """Return audit-only review hints for likely missed VSA detector cases.

    These diagnostics are intentionally weaker than production evidence rules.
    They flag rows that deserve manual review or future detector calibration;
    they do not create evidence and do not alter scanner scoring.
    """

    if bar_index < 0 or bar_index >= len(metrics):
        return ()

    row = metrics.iloc[bar_index]
    diagnostics: list[str] = []
    target_code_set = set(target_codes)
    high_volume = _is_high_volume(row)
    very_high_volume = _is_very_high_volume(row)
    close_off_low = _close_ratio(row) >= 0.35
    close_mid_or_higher = _close_ratio(row) >= 0.45
    bearish_context = (
        _has_bearish_vsa(scoring_codes)
        or _has_bearish_vsa(campaign_codes)
        or _is_bearish_qualification(qualification)
    )

    if (
        high_volume
        and _is_down_bar(row)
        and close_off_low
        and "stopping_volume" not in target_code_set
    ):
        diagnostics.append(DETECTOR_DIAGNOSTIC_POTENTIAL_STOPPING_VOLUME)

    if (
        very_high_volume
        and (_is_narrow_or_normal_spread(row) or _has_muted_downside_result(row))
        and "effort_gt_result" not in target_code_set
    ):
        diagnostics.append(DETECTOR_DIAGNOSTIC_POTENTIAL_EFFORT_GT_RESULT)

    if (
        high_volume
        and bearish_context
        and close_mid_or_higher
        and not _has_any(
            target_code_set,
            {
                "absorption",
                "demand_coming_in",
                "increasing_demand",
                "stopping_volume",
            },
        )
    ):
        diagnostics.append(DETECTOR_DIAGNOSTIC_POTENTIAL_ABSORPTION)

    if (
        _penetrates_prior_support(metrics, bar_index)
        and close_off_low
        and not _has_any(target_code_set, {"spring", "shakeout"})
    ):
        diagnostics.append(DETECTOR_DIAGNOSTIC_POTENTIAL_SPRING_OR_SHAKEOUT)

    if (
        high_volume
        and bearish_context
        and close_off_low
        and not _has_bullish_vsa(target_codes)
    ):
        diagnostics.append(
            DETECTOR_DIAGNOSTIC_HIGH_VOLUME_REVERSAL_WITHOUT_BULLISH_EVENT
        )

    return _dedupe(diagnostics)


def _audit_notes(
    candidate: Any,
    target_codes: tuple[str, ...],
    scoring_codes: tuple[str, ...],
    audit_flags: tuple[str, ...],
    detector_diagnostics: tuple[str, ...],
) -> tuple[str, ...]:
    notes: list[str] = []
    if AUDIT_FLAG_NO_TARGET_EVENT in audit_flags:
        notes.append("No event fired on the replay week.")
    if scoring_codes and not target_codes:
        notes.append("Scanner is using earlier scoring evidence; inspect event age.")
    if bool(getattr(candidate, "used_fallback_evidence", False)):
        notes.append("Scoring evidence is not on the replay week.")
    if AUDIT_FLAG_STALE_SCORING_EVIDENCE in audit_flags:
        notes.append(
            "Scoring evidence is older than the maximum actionable VSA age."
        )
    if AUDIT_FLAG_STRUCTURAL_EVENT_WITHOUT_VSA_CONFIRMATION in audit_flags:
        notes.append(
            "Structural event fired without same-week non-structural VSA confirmation."
        )
    if AUDIT_FLAG_BULLISH_VSA_AGAINST_BEARISH_QUALIFICATION in audit_flags:
        notes.append(
            "Bullish VSA evidence appeared while qualification remained bearish."
        )
    if AUDIT_FLAG_BEARISH_VSA_AGAINST_BULLISH_QUALIFICATION in audit_flags:
        notes.append(
            "Bearish VSA evidence appeared while qualification remained bullish."
        )
    if AUDIT_FLAG_CONFLICTING_TARGET_VSA_PRESSURE in audit_flags:
        notes.append("Bullish and bearish VSA both fired on the replay week.")
    if AUDIT_FLAG_CONFLICTING_SCORING_VSA_PRESSURE in audit_flags:
        notes.append("Bullish and bearish VSA both appear in scoring evidence.")
    if AUDIT_FLAG_QUALIFICATION_WITHOUT_CURRENT_EVIDENCE in audit_flags:
        notes.append(
            "Persistent qualification remains even though no current target, scoring, or campaign evidence is present."
        )
    if (
        DETECTOR_DIAGNOSTIC_POTENTIAL_STOPPING_VOLUME
        in detector_diagnostics
    ):
        notes.append(
            "High-volume down bar closed off the low; review why Stopping Volume did not fire."
        )
    if (
        DETECTOR_DIAGNOSTIC_POTENTIAL_EFFORT_GT_RESULT
        in detector_diagnostics
    ):
        notes.append(
            "Very-high-volume effort produced muted downside result; review Effort vs Result calibration."
        )
    if DETECTOR_DIAGNOSTIC_POTENTIAL_ABSORPTION in detector_diagnostics:
        notes.append(
            "High-volume bar in bearish context closed off the low/midpoint; review possible absorption."
        )
    if (
        DETECTOR_DIAGNOSTIC_POTENTIAL_SPRING_OR_SHAKEOUT
        in detector_diagnostics
    ):
        notes.append(
            "Bar interacted with prior support and recovered; review Spring/Shakeout criteria."
        )
    if (
        DETECTOR_DIAGNOSTIC_HIGH_VOLUME_REVERSAL_WITHOUT_BULLISH_EVENT
        in detector_diagnostics
    ):
        notes.append(
            "High-volume reversal candidate has no same-week bullish VSA event."
        )
    if bool(getattr(candidate, "actionable", False)):
        notes.append("Actionable candidate in audit output; review manually before any production interpretation.")
    if bool(getattr(candidate, "signal_bar_anomaly", False)):
        reason = getattr(candidate, "signal_bar_anomaly_reason", None)
        notes.append(str(reason or "Signal bar anomaly detected."))
    return _dedupe(notes)


def _event_codes(events: Iterable[Any]) -> tuple[str, ...]:
    codes: list[str] = []
    seen: set[str] = set()
    for event in events:
        code = _enum_text(getattr(event, "code", event))
        if code not in seen:
            codes.append(code)
            seen.add(code)
    return tuple(codes)


def _enum_text(value: Any) -> str:
    enum_value = getattr(value, "value", value)
    return str(enum_value)


def _candidate_bar_index(candidate: Any) -> int | None:
    value = getattr(candidate, "bar_index", None)
    if value is None:
        return None
    return int(value)


def _week_at(metrics: pd.DataFrame, index: int) -> str:
    return str(metrics.iloc[index][COL_WEEK])


def _is_structural_event_code(code: str) -> bool:
    return code.startswith(STRUCTURAL_EVENT_PREFIX)


def _is_persistent_qualification(qualification: str) -> bool:
    return qualification.startswith("persistent_")


def _is_bearish_qualification(qualification: str) -> bool:
    return qualification == "persistent_bearish"


def _is_bullish_qualification(qualification: str) -> bool:
    return qualification == "persistent_bullish"


def _has_bullish_vsa(codes: Iterable[str]) -> bool:
    return any(code in BULLISH_VSA_CODES for code in codes)


def _has_bearish_vsa(codes: Iterable[str]) -> bool:
    return any(code in BEARISH_VSA_CODES for code in codes)


def _has_any(codes: Iterable[str], wanted: set[str]) -> bool:
    return any(code in wanted for code in codes)


def _is_down_bar(row: pd.Series) -> bool:
    return _float_at(row, COL_CLOSE) < _float_at(row, COL_OPEN) or _enum_name(
        row.get(COL_DIRECTION)
    ) == "down"


def _is_high_volume(row: pd.Series) -> bool:
    return (
        _enum_name(row.get(COL_VOLUME_CLASS)) in {"high", "very_high", "ultra_high"}
        or _float_at(row, COL_VOLUME_RATIO) >= 1.3
        or _float_at(row, COL_VOLUME_PERCENTILE) >= 70.0
    )


def _is_very_high_volume(row: pd.Series) -> bool:
    return (
        _enum_name(row.get(COL_VOLUME_CLASS)) in {"very_high", "ultra_high"}
        or _float_at(row, COL_VOLUME_RATIO) >= 1.75
        or _float_at(row, COL_VOLUME_PERCENTILE) >= 85.0
    )


def _is_narrow_or_normal_spread(row: pd.Series) -> bool:
    return (
        _enum_name(row.get(COL_SPREAD_CLASS))
        in {"narrow", "below_average", "average"}
        or _float_at(row, COL_SPREAD_RATIO) <= 1.1
        or _float_at(row, COL_SPREAD_PERCENTILE) <= 60.0
    )


def _has_muted_downside_result(row: pd.Series) -> bool:
    price_change_pct = _float_at(row, COL_PRICE_CHANGE_PCT)
    return abs(price_change_pct) <= 2.5 or _close_ratio(row) >= 0.35


def _penetrates_prior_support(
    metrics: pd.DataFrame,
    bar_index: int,
    *,
    lookback: int = 12,
    tolerance: float = 0.005,
) -> bool:
    if bar_index <= 0 or COL_LOW not in metrics.columns:
        return False

    start = max(0, bar_index - lookback)
    prior = metrics.iloc[start:bar_index]
    if prior.empty:
        return False

    support = _safe_min(prior[COL_LOW])
    if support is None or support <= 0.0:
        return False

    row = metrics.iloc[bar_index]
    current_low = _float_at(row, COL_LOW)
    current_close = _float_at(row, COL_CLOSE)
    penetrated_support = current_low <= support * (1.0 + tolerance)
    recovered_from_support = current_close >= support or _close_ratio(row) >= 0.55
    return penetrated_support and recovered_from_support


def _close_ratio(row: pd.Series) -> float:
    return _float_at(row, COL_CLOSE_RATIO, default=0.5)


def _float_at(row: pd.Series, column: str, *, default: float = 0.0) -> float:
    if column not in row:
        return default
    value = row[column]
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _enum_name(value: Any) -> str:
    name = getattr(value, "name", None)
    if name is not None:
        return str(name).lower()
    text = str(getattr(value, "value", value)).lower()
    if "." in text:
        return text.rsplit(".", maxsplit=1)[-1]
    return text


def _safe_min(values: pd.Series) -> float | None:
    try:
        value = values.min()
    except ValueError:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        return None
    return float(value)


def _dedupe(items: Iterable[str]) -> tuple[str, ...]:
    selected: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item not in seen:
            selected.append(item)
            seen.add(item)
    return tuple(selected)
