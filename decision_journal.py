from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable

from decision_context import DecisionContext, SupplyDemandBias, TradabilityStatus


DECISION_JOURNAL_SCHEMA_VERSION = 1
DEFAULT_DECISION_JOURNAL_ROOT = Path("state") / "decision_journal"
DEFAULT_VALIDATION_HORIZON_BARS = 8


class ValidationOutcome(StrEnum):
    """Analysis-only result of comparing an expectation with later bars."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    INVALIDATED = "invalidated"
    MIXED = "mixed"
    OBSERVATION_ONLY = "observation_only"
    NO_DATA = "no_data"


@dataclass(frozen=True, slots=True)
class BarObservation:
    """Small OHLCV snapshot used for post-decision validation."""

    bar_index: int
    week: str
    high: float
    low: float
    close: float
    volume: float | None = None

    @classmethod
    def from_any(cls, value: Any) -> "BarObservation":
        return cls(
            bar_index=int(_read_field(value, "bar_index")),
            week=str(_read_field(value, "week")),
            high=float(_read_field(value, "high")),
            low=float(_read_field(value, "low")),
            close=float(_read_field(value, "close")),
            volume=_optional_float(_read_field(value, "volume", default=None)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "bar_index": self.bar_index,
            "week": self.week,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BarObservation":
        return cls(
            bar_index=int(data["bar_index"]),
            week=str(data["week"]),
            high=float(data["high"]),
            low=float(data["low"]),
            close=float(data["close"]),
            volume=_optional_float(data.get("volume")),
        )


@dataclass(frozen=True, slots=True)
class DecisionJournalEntry:
    """Persisted expectation created from one compact DecisionContext."""

    schema_version: int
    entry_id: str
    symbol: str
    timeframe: str
    source_context_week: str | None
    source_context_bar_index: int | None
    source_context_evaluated_at_utc: str
    created_at_utc: str
    phase: str
    bias: str
    tradability: str
    decision: str
    confidence: float
    net_pressure: float
    headline: str
    summary: str
    confirmation_condition: str
    invalidation_condition: str
    expected_next_behavior: tuple[str, ...]
    support_price: float | None
    resistance_price: float | None
    reference_price: float | None
    status: ValidationOutcome = ValidationOutcome.PENDING

    @classmethod
    def from_context(
        cls,
        context: DecisionContext,
        *,
        created_at_utc: str | None = None,
    ) -> "DecisionJournalEntry":
        support_price = _latest_swing_price(context, wants_high=False)
        resistance_price = _latest_swing_price(context, wants_high=True)
        reference_price = _reference_price(
            bias=context.bias,
            support_price=support_price,
            resistance_price=resistance_price,
        )
        created_at = created_at_utc or _utc_now()
        return cls(
            schema_version=DECISION_JOURNAL_SCHEMA_VERSION,
            entry_id=_entry_id(context),
            symbol=context.symbol,
            timeframe=context.timeframe,
            source_context_week=context.latest_week,
            source_context_bar_index=context.latest_bar_index,
            source_context_evaluated_at_utc=context.evaluated_at_utc,
            created_at_utc=created_at,
            phase=context.phase.value,
            bias=context.bias.value,
            tradability=context.tradability.value,
            decision=context.decision.value,
            confidence=context.confidence,
            net_pressure=context.net_pressure,
            headline=context.story.headline,
            summary=context.story.summary,
            confirmation_condition=context.story.confirmation_condition,
            invalidation_condition=context.story.invalidation_condition,
            expected_next_behavior=tuple(context.story.what_to_expect_next),
            support_price=support_price,
            resistance_price=resistance_price,
            reference_price=reference_price,
            status=(
                ValidationOutcome.OBSERVATION_ONLY
                if context.tradability is TradabilityStatus.AVOID
                else ValidationOutcome.PENDING
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "entry_id": self.entry_id,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "source_context_week": self.source_context_week,
            "source_context_bar_index": self.source_context_bar_index,
            "source_context_evaluated_at_utc": self.source_context_evaluated_at_utc,
            "created_at_utc": self.created_at_utc,
            "phase": self.phase,
            "bias": self.bias,
            "tradability": self.tradability,
            "decision": self.decision,
            "confidence": self.confidence,
            "net_pressure": self.net_pressure,
            "headline": self.headline,
            "summary": self.summary,
            "confirmation_condition": self.confirmation_condition,
            "invalidation_condition": self.invalidation_condition,
            "expected_next_behavior": list(self.expected_next_behavior),
            "support_price": self.support_price,
            "resistance_price": self.resistance_price,
            "reference_price": self.reference_price,
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DecisionJournalEntry":
        return cls(
            schema_version=int(data["schema_version"]),
            entry_id=str(data["entry_id"]),
            symbol=str(data["symbol"]),
            timeframe=str(data["timeframe"]),
            source_context_week=(
                None
                if data.get("source_context_week") is None
                else str(data["source_context_week"])
            ),
            source_context_bar_index=(
                None
                if data.get("source_context_bar_index") is None
                else int(data["source_context_bar_index"])
            ),
            source_context_evaluated_at_utc=str(data["source_context_evaluated_at_utc"]),
            created_at_utc=str(data["created_at_utc"]),
            phase=str(data["phase"]),
            bias=str(data["bias"]),
            tradability=str(data["tradability"]),
            decision=str(data["decision"]),
            confidence=float(data["confidence"]),
            net_pressure=float(data["net_pressure"]),
            headline=str(data["headline"]),
            summary=str(data["summary"]),
            confirmation_condition=str(data["confirmation_condition"]),
            invalidation_condition=str(data["invalidation_condition"]),
            expected_next_behavior=tuple(
                str(item) for item in data.get("expected_next_behavior", ())
            ),
            support_price=_optional_float(data.get("support_price")),
            resistance_price=_optional_float(data.get("resistance_price")),
            reference_price=_optional_float(data.get("reference_price")),
            status=ValidationOutcome(str(data.get("status", ValidationOutcome.PENDING))),
        )


@dataclass(frozen=True, slots=True)
class DecisionJournalEvaluation:
    """Outcome snapshot for a journal entry after later bars are available."""

    entry_id: str
    symbol: str
    timeframe: str
    outcome: ValidationOutcome
    checked_bars: int
    first_checked_week: str | None
    last_checked_week: str | None
    confirmation_hit: bool
    invalidation_hit: bool
    favorable_move_pct: float | None
    adverse_move_pct: float | None
    notes: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "outcome": self.outcome.value,
            "checked_bars": self.checked_bars,
            "first_checked_week": self.first_checked_week,
            "last_checked_week": self.last_checked_week,
            "confirmation_hit": self.confirmation_hit,
            "invalidation_hit": self.invalidation_hit,
            "favorable_move_pct": self.favorable_move_pct,
            "adverse_move_pct": self.adverse_move_pct,
            "notes": self.notes,
        }


class DecisionJournalStore:
    """Durable JSON store for compact decision-validation journal entries."""

    def __init__(self, root: str | Path = DEFAULT_DECISION_JOURNAL_ROOT) -> None:
        self._root = Path(root)

    @staticmethod
    def _safe_name(value: str) -> str:
        name = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
        if not name:
            raise ValueError("DecisionJournal identity cannot produce an empty filename.")
        return name

    def path_for(self, symbol: str, timeframe: str) -> Path:
        if not symbol or not timeframe:
            raise ValueError("symbol and timeframe are required")
        return self._root / (
            f"{self._safe_name(symbol)}__{self._safe_name(timeframe)}.json"
        )

    def load_all(self, symbol: str, timeframe: str) -> tuple[DecisionJournalEntry, ...]:
        path = self.path_for(symbol, timeframe)
        if not path.exists():
            return ()

        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid DecisionJournal file: {path}") from exc

        if not isinstance(payload, list):
            raise ValueError(f"Invalid DecisionJournal file: {path}")

        entries = tuple(DecisionJournalEntry.from_dict(item) for item in payload)
        for entry in entries:
            if entry.schema_version != DECISION_JOURNAL_SCHEMA_VERSION:
                raise ValueError(
                    f"Unsupported DecisionJournal schema version: {entry.schema_version}"
                )
            if entry.symbol != symbol or entry.timeframe != timeframe:
                raise ValueError("DecisionJournal identity does not match requested journal")
        return entries

    def save_all(
        self,
        symbol: str,
        timeframe: str,
        entries: Iterable[DecisionJournalEntry],
    ) -> Path:
        ordered = tuple(entries)
        for entry in ordered:
            if entry.schema_version != DECISION_JOURNAL_SCHEMA_VERSION:
                raise ValueError(
                    f"Unsupported DecisionJournal schema version: {entry.schema_version}"
                )
            if entry.symbol != symbol or entry.timeframe != timeframe:
                raise ValueError("DecisionJournal entry identity does not match destination")

        destination = self.path_for(symbol, timeframe)
        self._root.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            [entry.to_dict() for entry in ordered],
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )

        fd, temp_name = tempfile.mkstemp(
            dir=self._root,
            prefix=f".{destination.stem}.",
            suffix=".tmp",
            text=True,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, destination)
        except Exception:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
            raise
        return destination

    def upsert(self, entry: DecisionJournalEntry) -> Path:
        existing = self.load_all(entry.symbol, entry.timeframe)
        by_id = {item.entry_id: item for item in existing}
        by_id[entry.entry_id] = entry
        ordered = sorted(
            by_id.values(),
            key=lambda item: (
                item.source_context_bar_index if item.source_context_bar_index is not None else -1,
                item.created_at_utc,
                item.entry_id,
            ),
        )
        return self.save_all(entry.symbol, entry.timeframe, ordered)

    def update_status(
        self,
        entry: DecisionJournalEntry,
        outcome: ValidationOutcome,
    ) -> Path:
        return self.upsert(replace(entry, status=outcome))


def create_journal_entry(
    context: DecisionContext,
    *,
    created_at_utc: str | None = None,
) -> DecisionJournalEntry:
    """Create an analysis-only validation journal entry from a DecisionContext."""
    return DecisionJournalEntry.from_context(context, created_at_utc=created_at_utc)


def evaluate_journal_entry(
    entry: DecisionJournalEntry,
    later_bars: Iterable[Any],
    *,
    horizon_bars: int = DEFAULT_VALIDATION_HORIZON_BARS,
) -> DecisionJournalEvaluation:
    """Compare one stored expectation with bars that arrived after it.

    This deliberately uses simple directional/reference checks. It is not a
    trading backtest, not performance attribution, and not a signal rule.
    """
    if horizon_bars <= 0:
        raise ValueError("horizon_bars must be greater than zero")

    bars = _future_bars(entry, later_bars, horizon_bars=horizon_bars)
    if entry.status is ValidationOutcome.OBSERVATION_ONLY or entry.tradability == "avoid":
        return _evaluation(
            entry,
            outcome=ValidationOutcome.OBSERVATION_ONLY,
            bars=bars,
            confirmation_hit=False,
            invalidation_hit=False,
            notes="Entry is observation-only; validation is intentionally skipped.",
        )
    if not bars:
        return _evaluation(
            entry,
            outcome=ValidationOutcome.NO_DATA,
            bars=bars,
            confirmation_hit=False,
            invalidation_hit=False,
            notes="No later bars are available after the source context bar.",
        )

    bias = entry.bias.lower()
    if bias == SupplyDemandBias.BULLISH.value:
        confirmation_hit = _bullish_confirmation(entry, bars)
        invalidation_hit = _bullish_invalidation(entry, bars)
    elif bias == SupplyDemandBias.BEARISH.value:
        confirmation_hit = _bearish_confirmation(entry, bars)
        invalidation_hit = _bearish_invalidation(entry, bars)
    else:
        return _evaluation(
            entry,
            outcome=ValidationOutcome.OBSERVATION_ONLY,
            bars=bars,
            confirmation_hit=False,
            invalidation_hit=False,
            notes="Mixed or neutral context is tracked as observation-only.",
        )

    if confirmation_hit and invalidation_hit:
        outcome = ValidationOutcome.MIXED
        notes = (
            "Both confirmation and invalidation references were touched. "
            "Review the sequence manually."
        )
    elif confirmation_hit:
        outcome = ValidationOutcome.CONFIRMED
        notes = "Later bars confirmed the stored directional expectation."
    elif invalidation_hit:
        outcome = ValidationOutcome.INVALIDATED
        notes = "Later bars invalidated the stored directional expectation."
    else:
        outcome = ValidationOutcome.PENDING
        notes = "Later bars have not confirmed or invalidated the stored expectation yet."

    return _evaluation(
        entry,
        outcome=outcome,
        bars=bars,
        confirmation_hit=confirmation_hit,
        invalidation_hit=invalidation_hit,
        notes=notes,
    )


def _future_bars(
    entry: DecisionJournalEntry,
    later_bars: Iterable[Any],
    *,
    horizon_bars: int,
) -> tuple[BarObservation, ...]:
    observed = [BarObservation.from_any(item) for item in later_bars]
    if entry.source_context_bar_index is not None:
        observed = [
            item
            for item in observed
            if item.bar_index > entry.source_context_bar_index
        ]
    observed.sort(key=lambda item: item.bar_index)
    return tuple(observed[:horizon_bars])


def _evaluation(
    entry: DecisionJournalEntry,
    *,
    outcome: ValidationOutcome,
    bars: tuple[BarObservation, ...],
    confirmation_hit: bool,
    invalidation_hit: bool,
    notes: str,
) -> DecisionJournalEvaluation:
    favorable, adverse = _move_stats(entry, bars)
    return DecisionJournalEvaluation(
        entry_id=entry.entry_id,
        symbol=entry.symbol,
        timeframe=entry.timeframe,
        outcome=outcome,
        checked_bars=len(bars),
        first_checked_week=bars[0].week if bars else None,
        last_checked_week=bars[-1].week if bars else None,
        confirmation_hit=confirmation_hit,
        invalidation_hit=invalidation_hit,
        favorable_move_pct=favorable,
        adverse_move_pct=adverse,
        notes=notes,
    )


def _bullish_confirmation(
    entry: DecisionJournalEntry, bars: tuple[BarObservation, ...]) -> bool:
    if entry.resistance_price is not None:
        return any(bar.close > entry.resistance_price for bar in bars)
    if entry.reference_price is not None:
        return any(bar.close > entry.reference_price for bar in bars)
    return False


def _bullish_invalidation(
    entry: DecisionJournalEntry, bars: tuple[BarObservation, ...]) -> bool:
    if entry.support_price is not None:
        return any(bar.close < entry.support_price for bar in bars)
    if entry.reference_price is not None:
        return any(bar.close < entry.reference_price for bar in bars)
    return False


def _bearish_confirmation(
    entry: DecisionJournalEntry, bars: tuple[BarObservation, ...]) -> bool:
    if entry.support_price is not None:
        return any(bar.close < entry.support_price for bar in bars)
    if entry.reference_price is not None:
        return any(bar.close < entry.reference_price for bar in bars)
    return False


def _bearish_invalidation(
    entry: DecisionJournalEntry, bars: tuple[BarObservation, ...]) -> bool:
    if entry.resistance_price is not None:
        return any(bar.close > entry.resistance_price for bar in bars)
    if entry.reference_price is not None:
        return any(bar.close > entry.reference_price for bar in bars)
    return False


def _move_stats(
    entry: DecisionJournalEntry,
    bars: tuple[BarObservation, ...],
) -> tuple[float | None, float | None]:
    reference = entry.reference_price
    if reference is None or reference == 0 or not bars:
        return None, None

    highs = [bar.high for bar in bars]
    lows = [bar.low for bar in bars]
    if entry.bias == SupplyDemandBias.BEARISH.value:
        favorable = ((reference - min(lows)) / reference) * 100
        adverse = ((max(highs) - reference) / reference) * 100
    else:
        favorable = ((max(highs) - reference) / reference) * 100
        adverse = ((reference - min(lows)) / reference) * 100
    return max(0.0, favorable), max(0.0, adverse)


def _entry_id(context: DecisionContext) -> str:
    week = context.latest_week or "unknown_week"
    bar_index = "none" if context.latest_bar_index is None else str(context.latest_bar_index)
    return "__".join(
        (
            DecisionJournalStore._safe_name(context.symbol),
            DecisionJournalStore._safe_name(context.timeframe),
            DecisionJournalStore._safe_name(week),
            bar_index,
        )
    )


def _latest_swing_price(context: DecisionContext, *, wants_high: bool) -> float | None:
    for swing in reversed(context.structural_swings):
        text = f"{swing.type} {swing.label or ''}".lower()
        is_high = "high" in text or text in {"hh", "lh"}
        is_low = "low" in text or text in {"hl", "ll"}
        if wants_high and is_high:
            return swing.price
        if not wants_high and is_low:
            return swing.price
    return None


def _reference_price(
    *,
    bias: SupplyDemandBias,
    support_price: float | None,
    resistance_price: float | None,
) -> float | None:
    if bias is SupplyDemandBias.BULLISH:
        return support_price or resistance_price
    if bias is SupplyDemandBias.BEARISH:
        return resistance_price or support_price
    return support_price or resistance_price


def _read_field(value: Any, name: str, *, default: Any = ...) -> Any:
    if isinstance(value, dict):
        if name in value:
            return value[name]
        if default is not ...:
            return default
        raise KeyError(name)
    if hasattr(value, name):
        return getattr(value, name)
    if default is not ...:
        return default
    raise AttributeError(name)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "BarObservation",
    "DECISION_JOURNAL_SCHEMA_VERSION",
    "DEFAULT_DECISION_JOURNAL_ROOT",
    "DEFAULT_VALIDATION_HORIZON_BARS",
    "DecisionJournalEntry",
    "DecisionJournalEvaluation",
    "DecisionJournalStore",
    "ValidationOutcome",
    "create_journal_entry",
    "evaluate_journal_entry",
]
