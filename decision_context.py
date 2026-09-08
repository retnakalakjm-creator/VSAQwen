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


DECISION_CONTEXT_SCHEMA_VERSION = 1
DEFAULT_DECISION_CONTEXT_ROOT = Path("state") / "decision_context"
DEFAULT_MAX_DECISION_EVENTS = 12
DEFAULT_MAX_STRUCTURAL_SWINGS = 8


class DecisionMode(StrEnum):
    """Whether the context is based on confirmed or developing market data."""

    CONFIRMED = "confirmed"
    DEVELOPING = "developing"


class SupplyDemandBias(StrEnum):
    """Compact supply/demand read used by the decision-support UI."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    MIXED = "mixed"
    NEUTRAL = "neutral"


class MarketPhaseContext(StrEnum):
    """High-level VSA/Wyckoff phase estimate for decision support."""

    LATE_ACCUMULATION = "late_accumulation"
    ACCUMULATION = "accumulation"
    REACCUMULATION = "reaccumulation"
    MARKUP = "markup"
    DISTRIBUTION = "distribution"
    REDISTRIBUTION = "redistribution"
    MARKDOWN = "markdown"
    UNCERTAIN = "uncertain"


class TradabilityStatus(StrEnum):
    """Human-decision label; this must never trigger order placement."""

    TRADABLE_NOW = "tradable_now"
    WAIT_FOR_PULLBACK = "wait_for_pullback"
    WAIT_FOR_CONFIRMATION = "wait_for_confirmation"
    OBSERVATION_ONLY = "observation_only"
    AVOID = "avoid"


class DecisionAction(StrEnum):
    """Compact action guidance for analysis-only workflows."""

    REVIEW_SETUP = "review_setup"
    WATCHLIST = "watchlist"
    WAIT_FOR_PULLBACK = "wait_for_pullback"
    WAIT_FOR_CONFIRMATION = "wait_for_confirmation"
    OBSERVE_ONLY = "observe_only"
    AVOID = "avoid"


@dataclass(frozen=True, slots=True)
class DecisionContextEvent:
    """One recent decision-relevant event, not a full historical event log."""

    bar_index: int
    week: str
    code: str
    category: str
    direction: str
    strength: float
    quality: float
    observation: str
    description: str
    role: str

    @property
    def importance(self) -> float:
        return max(0.0, self.strength) * max(0.0, self.quality)

    @classmethod
    def from_evidence(cls, evidence: Any, *, role: str) -> "DecisionContextEvent":
        return cls(
            bar_index=int(getattr(evidence, "bar_index")),
            week=str(getattr(evidence, "week_beginning")),
            code=_enum_text(getattr(evidence, "code")),
            category=_enum_name(getattr(evidence, "category")),
            direction=_enum_name(getattr(evidence, "direction")),
            strength=float(getattr(evidence, "strength", 0.0)),
            quality=float(getattr(evidence, "quality", 1.0)),
            observation=str(getattr(evidence, "observation", "")),
            description=str(getattr(evidence, "description", "")),
            role=role,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "bar_index": self.bar_index,
            "week": self.week,
            "code": self.code,
            "category": self.category,
            "direction": self.direction,
            "strength": self.strength,
            "quality": self.quality,
            "observation": self.observation,
            "description": self.description,
            "role": self.role,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DecisionContextEvent":
        return cls(
            bar_index=int(data["bar_index"]),
            week=str(data["week"]),
            code=str(data["code"]),
            category=str(data["category"]),
            direction=str(data["direction"]),
            strength=float(data["strength"]),
            quality=float(data.get("quality", 1.0)),
            observation=str(data.get("observation", "")),
            description=str(data.get("description", "")),
            role=str(data.get("role", "recent")),
        )


@dataclass(frozen=True, slots=True)
class StructuralSwingMemory:
    """Compact structural swing memory for the current decision context."""

    pivot_bar_index: int
    confirmation_bar_index: int
    pivot_week: str
    type: str
    label: str | None
    price: float
    grade: str
    is_failed: bool
    score: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "pivot_bar_index": self.pivot_bar_index,
            "confirmation_bar_index": self.confirmation_bar_index,
            "pivot_week": self.pivot_week,
            "type": self.type,
            "label": self.label,
            "price": self.price,
            "grade": self.grade,
            "is_failed": self.is_failed,
            "score": self.score,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StructuralSwingMemory":
        score = data.get("score")
        return cls(
            pivot_bar_index=int(data["pivot_bar_index"]),
            confirmation_bar_index=int(data["confirmation_bar_index"]),
            pivot_week=str(data["pivot_week"]),
            type=str(data["type"]),
            label=None if data.get("label") is None else str(data["label"]),
            price=float(data["price"]),
            grade=str(data["grade"]),
            is_failed=bool(data["is_failed"]),
            score=None if score is None else float(score),
        )


@dataclass(frozen=True, slots=True)
class VSAStorySummary:
    """Short explanation fields that the local UI can render immediately."""

    headline: str
    summary: str
    confirmation_condition: str
    invalidation_condition: str
    what_to_expect_next: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "headline": self.headline,
            "summary": self.summary,
            "confirmation_condition": self.confirmation_condition,
            "invalidation_condition": self.invalidation_condition,
            "what_to_expect_next": list(self.what_to_expect_next),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VSAStorySummary":
        return cls(
            headline=str(data["headline"]),
            summary=str(data["summary"]),
            confirmation_condition=str(data["confirmation_condition"]),
            invalidation_condition=str(data["invalidation_condition"]),
            what_to_expect_next=tuple(
                str(item) for item in data.get("what_to_expect_next", ())
            ),
        )


@dataclass(frozen=True, slots=True)
class DecisionContext:
    """Persistable compact market read for one symbol/timeframe.

    This is intentionally a decision-support memory, not a full historical
    audit dataset. It stores only recent events and structural context needed
    to explain the current scanner decision.
    """

    schema_version: int
    symbol: str
    timeframe: str
    mode: DecisionMode
    latest_bar_index: int | None
    latest_week: str | None
    qualification: str
    actionable: bool
    decision: DecisionAction
    tradability: TradabilityStatus
    phase: MarketPhaseContext
    bias: SupplyDemandBias
    confidence: float
    net_strength: float
    net_pressure: float
    reason: str
    recent_events: tuple[DecisionContextEvent, ...]
    structural_swings: tuple[StructuralSwingMemory, ...]
    story: VSAStorySummary
    evaluated_at_utc: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "mode": self.mode.value,
            "latest_bar_index": self.latest_bar_index,
            "latest_week": self.latest_week,
            "qualification": self.qualification,
            "actionable": self.actionable,
            "decision": self.decision.value,
            "tradability": self.tradability.value,
            "phase": self.phase.value,
            "bias": self.bias.value,
            "confidence": self.confidence,
            "net_strength": self.net_strength,
            "net_pressure": self.net_pressure,
            "reason": self.reason,
            "recent_events": [event.to_dict() for event in self.recent_events],
            "structural_swings": [swing.to_dict() for swing in self.structural_swings],
            "story": self.story.to_dict(),
            "evaluated_at_utc": self.evaluated_at_utc,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DecisionContext":
        return cls(
            schema_version=int(data["schema_version"]),
            symbol=str(data["symbol"]),
            timeframe=str(data["timeframe"]),
            mode=DecisionMode(str(data["mode"])),
            latest_bar_index=(
                None
                if data.get("latest_bar_index") is None
                else int(data["latest_bar_index"])
            ),
            latest_week=None if data.get("latest_week") is None else str(data["latest_week"]),
            qualification=str(data["qualification"]),
            actionable=bool(data["actionable"]),
            decision=DecisionAction(str(data["decision"])),
            tradability=TradabilityStatus(str(data["tradability"])),
            phase=MarketPhaseContext(str(data["phase"])),
            bias=SupplyDemandBias(str(data["bias"])),
            confidence=float(data["confidence"]),
            net_strength=float(data["net_strength"]),
            net_pressure=float(data["net_pressure"]),
            reason=str(data.get("reason", "")),
            recent_events=tuple(
                DecisionContextEvent.from_dict(item)
                for item in data.get("recent_events", ())
            ),
            structural_swings=tuple(
                StructuralSwingMemory.from_dict(item)
                for item in data.get("structural_swings", ())
            ),
            story=VSAStorySummary.from_dict(data["story"]),
            evaluated_at_utc=str(data["evaluated_at_utc"]),
        )


class DecisionContextStore:
    """Durable JSON store for compact decision contexts."""

    def __init__(self, root: str | Path = DEFAULT_DECISION_CONTEXT_ROOT) -> None:
        self._root = Path(root)

    @staticmethod
    def _safe_name(value: str) -> str:
        name = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
        if not name:
            raise ValueError("DecisionContext identity cannot produce an empty filename.")
        return name

    def path_for(self, symbol: str, timeframe: str) -> Path:
        if not symbol or not timeframe:
            raise ValueError("symbol and timeframe are required")
        return self._root / (
            f"{self._safe_name(symbol)}__{self._safe_name(timeframe)}.json"
        )

    def save(self, context: DecisionContext) -> Path:
        if context.schema_version != DECISION_CONTEXT_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported DecisionContext schema version: {context.schema_version}"
            )

        destination = self.path_for(context.symbol, context.timeframe)
        self._root.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            context.to_dict(),
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

    def load(self, symbol: str, timeframe: str) -> DecisionContext:
        path = self.path_for(symbol, timeframe)
        if not path.exists():
            raise FileNotFoundError(path)

        try:
            with path.open("r", encoding="utf-8") as handle:
                context = DecisionContext.from_dict(json.load(handle))
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid DecisionContext file: {path}") from exc

        if context.schema_version != DECISION_CONTEXT_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported DecisionContext schema version: {context.schema_version}"
            )
        if context.symbol != symbol or context.timeframe != timeframe:
            raise ValueError("DecisionContext identity does not match requested context")
        return context

    def delete(self, symbol: str, timeframe: str) -> None:
        self.path_for(symbol, timeframe).unlink(missing_ok=True)


def build_decision_context(
    candidate: Any,
    *,
    symbol: str,
    timeframe: str = "1W",
    mode: DecisionMode | str = DecisionMode.CONFIRMED,
    max_events: int = DEFAULT_MAX_DECISION_EVENTS,
    max_structural_swings: int = DEFAULT_MAX_STRUCTURAL_SWINGS,
    evaluated_at_utc: str | None = None,
) -> DecisionContext:
    """Build compact decision context from the latest scanner candidate.

    The builder is deliberately lossy: it keeps only recent decision-relevant
    events and swings so the local app can explain the current market read
    without persisting a full historical event log.
    """
    if max_events <= 0:
        raise ValueError("max_events must be greater than zero")
    if max_structural_swings <= 0:
        raise ValueError("max_structural_swings must be greater than zero")

    mode_value = mode if isinstance(mode, DecisionMode) else DecisionMode(str(mode))
    events = _recent_events(candidate, max_events=max_events)
    swings = _recent_structural_swings(
        candidate,
        max_structural_swings=max_structural_swings,
    )
    bias = _infer_bias(candidate, events)
    qualification = _enum_text(getattr(candidate, "qualification", "unqualified"))
    phase = _infer_phase(qualification=qualification, bias=bias, candidate=candidate)
    tradability = _infer_tradability(candidate, bias=bias)
    decision = _decision_for_tradability(tradability)
    story = _build_story(
        candidate,
        bias=bias,
        phase=phase,
        tradability=tradability,
        events=events,
    )

    return DecisionContext(
        schema_version=DECISION_CONTEXT_SCHEMA_VERSION,
        symbol=symbol.strip().upper(),
        timeframe=timeframe,
        mode=mode_value,
        latest_bar_index=_optional_int(getattr(candidate, "bar_index", None)),
        latest_week=_optional_str(getattr(candidate, "week", None)),
        qualification=qualification,
        actionable=bool(getattr(candidate, "actionable", False)),
        decision=decision,
        tradability=tradability,
        phase=phase,
        bias=bias,
        confidence=float(getattr(candidate, "confidence", 0.0)),
        net_strength=float(getattr(candidate, "net_strength", 0.0)),
        net_pressure=float(getattr(candidate, "net_pressure", 0.0)),
        reason=str(getattr(candidate, "reason", "")),
        recent_events=events,
        structural_swings=swings,
        story=story,
        evaluated_at_utc=evaluated_at_utc or _utc_now(),
    )


def _recent_events(candidate: Any, *, max_events: int) -> tuple[DecisionContextEvent, ...]:
    role_items = (
        ("campaign", getattr(candidate, "campaign_evidence", ())),
        ("qualifying", getattr(candidate, "qualifying_evidence", ())),
        ("scoring", getattr(candidate, "scoring_evidence", ())),
        ("target", getattr(candidate, "target_bar_evidence", ())),
    )

    by_key: dict[tuple[int, str], DecisionContextEvent] = {}
    for role, evidence_items in role_items:
        for evidence in _iter_items(evidence_items):
            event = DecisionContextEvent.from_evidence(evidence, role=role)
            key = (event.bar_index, event.code)
            if key in by_key:
                by_key[key] = _merge_event_role(by_key[key], role)
            else:
                by_key[key] = event

    ordered = sorted(
        by_key.values(),
        key=lambda event: (event.bar_index, event.importance, event.code),
    )
    return tuple(ordered[-max_events:])


def _merge_event_role(event: DecisionContextEvent, role: str) -> DecisionContextEvent:
    roles = event.role.split("|")
    if role in roles:
        return event
    return replace(event, role="|".join([*roles, role]))


def _recent_structural_swings(
    candidate: Any,
    *,
    max_structural_swings: int,
) -> tuple[StructuralSwingMemory, ...]:
    trend = getattr(getattr(candidate, "evidence", None), "context", None)
    trend = getattr(trend, "trend", None)
    structure = getattr(trend, "structure", trend)
    structural_swings = getattr(structure, "structural_swings", ())

    memories = [
        _structural_swing_memory(item)
        for item in _iter_items(structural_swings)
    ]
    memories = [memory for memory in memories if memory is not None]
    memories.sort(key=lambda swing: (swing.confirmation_bar_index, swing.pivot_bar_index))
    return tuple(memories[-max_structural_swings:])


def _structural_swing_memory(item: Any) -> StructuralSwingMemory | None:
    swing = getattr(item, "swing", None)
    if swing is None:
        return None

    score = None
    evaluation = getattr(item, "evaluation", None)
    professional = getattr(evaluation, "professional", None)
    if professional is not None:
        try:
            score = float(getattr(professional, "overall"))
        except (TypeError, ValueError):
            score = None

    label = getattr(swing, "label", None)
    return StructuralSwingMemory(
        pivot_bar_index=int(getattr(swing, "bar_index")),
        confirmation_bar_index=int(getattr(swing, "confirmation_index")),
        pivot_week=str(getattr(swing, "week_beginning")),
        type=_enum_text(getattr(swing, "type")),
        label=None if label is None else _enum_text(label),
        price=float(getattr(swing, "price")),
        grade=_enum_name(getattr(item, "grade", "")),
        is_failed=bool(getattr(item, "is_failed", False)),
        score=score,
    )


def _infer_bias(
    candidate: Any,
    events: tuple[DecisionContextEvent, ...],
) -> SupplyDemandBias:
    net_pressure = float(getattr(candidate, "net_pressure", 0.0))
    bullish = sum(1 for event in events if event.direction.upper() == "BULLISH")
    bearish = sum(1 for event in events if event.direction.upper() == "BEARISH")

    if bullish and bearish:
        if abs(net_pressure) < 0.05:
            return SupplyDemandBias.MIXED
        return SupplyDemandBias.BULLISH if net_pressure > 0 else SupplyDemandBias.BEARISH

    if net_pressure > 0.05 or bullish > bearish:
        return SupplyDemandBias.BULLISH
    if net_pressure < -0.05 or bearish > bullish:
        return SupplyDemandBias.BEARISH
    return SupplyDemandBias.NEUTRAL


def _infer_phase(
    *,
    qualification: str,
    bias: SupplyDemandBias,
    candidate: Any,
) -> MarketPhaseContext:
    qualification_text = qualification.lower()
    trend = getattr(getattr(candidate, "evidence", None), "context", None)
    trend = getattr(trend, "trend", None)
    direction = _enum_text(getattr(trend, "direction", "")).lower()
    state = _enum_text(getattr(trend, "state", "")).lower()

    if "bullish" in qualification_text and bias is SupplyDemandBias.BULLISH:
        return MarketPhaseContext.LATE_ACCUMULATION
    if "bearish" in qualification_text and bias is SupplyDemandBias.BEARISH:
        return MarketPhaseContext.DISTRIBUTION
    if direction == "up" and bias is SupplyDemandBias.BULLISH:
        return MarketPhaseContext.MARKUP
    if direction == "down" and bias is SupplyDemandBias.BEARISH:
        return MarketPhaseContext.MARKDOWN
    if direction == "range" and bias is SupplyDemandBias.BULLISH:
        return MarketPhaseContext.ACCUMULATION
    if direction == "range" and bias is SupplyDemandBias.BEARISH:
        return MarketPhaseContext.DISTRIBUTION
    if state == "correcting" and bias is SupplyDemandBias.BULLISH:
        return MarketPhaseContext.REACCUMULATION
    return MarketPhaseContext.UNCERTAIN


def _infer_tradability(
    candidate: Any,
    *,
    bias: SupplyDemandBias,
) -> TradabilityStatus:
    if bool(getattr(candidate, "signal_bar_anomaly", False)):
        return TradabilityStatus.AVOID

    if bool(getattr(candidate, "actionable", False)):
        if bool(getattr(candidate, "execution_pending", False)):
            return TradabilityStatus.WAIT_FOR_CONFIRMATION
        return TradabilityStatus.TRADABLE_NOW

    if bias in (SupplyDemandBias.BULLISH, SupplyDemandBias.BEARISH):
        return TradabilityStatus.WAIT_FOR_CONFIRMATION

    if bias is SupplyDemandBias.MIXED:
        return TradabilityStatus.OBSERVATION_ONLY

    return TradabilityStatus.OBSERVATION_ONLY


def _decision_for_tradability(tradability: TradabilityStatus) -> DecisionAction:
    if tradability is TradabilityStatus.TRADABLE_NOW:
        return DecisionAction.REVIEW_SETUP
    if tradability is TradabilityStatus.WAIT_FOR_PULLBACK:
        return DecisionAction.WAIT_FOR_PULLBACK
    if tradability is TradabilityStatus.WAIT_FOR_CONFIRMATION:
        return DecisionAction.WAIT_FOR_CONFIRMATION
    if tradability is TradabilityStatus.AVOID:
        return DecisionAction.AVOID
    return DecisionAction.OBSERVE_ONLY


def _build_story(
    candidate: Any,
    *,
    bias: SupplyDemandBias,
    phase: MarketPhaseContext,
    tradability: TradabilityStatus,
    events: tuple[DecisionContextEvent, ...],
) -> VSAStorySummary:
    headline = _headline(bias=bias, phase=phase, tradability=tradability)
    event_sentence = _event_sentence(events)
    reason = str(getattr(candidate, "reason", "")).strip()

    summary_parts = [
        f"Recent VSA context is {bias.value.replace('_', ' ')} with a phase read of {phase.value.replace('_', ' ')}.",
    ]
    if event_sentence:
        summary_parts.append(event_sentence)
    if reason:
        summary_parts.append(reason)

    return VSAStorySummary(
        headline=headline,
        summary=" ".join(summary_parts),
        confirmation_condition=_confirmation_condition(bias),
        invalidation_condition=_invalidation_condition(bias),
        what_to_expect_next=_expectations(bias=bias, tradability=tradability),
    )


def _headline(
    *,
    bias: SupplyDemandBias,
    phase: MarketPhaseContext,
    tradability: TradabilityStatus,
) -> str:
    if tradability is TradabilityStatus.AVOID:
        return "Avoid acting on this signal until data quality is reviewed"
    if bias is SupplyDemandBias.BULLISH:
        return f"Bullish VSA context in {phase.value.replace('_', ' ')}"
    if bias is SupplyDemandBias.BEARISH:
        return f"Bearish VSA context in {phase.value.replace('_', ' ')}"
    if bias is SupplyDemandBias.MIXED:
        return "Mixed VSA context; wait for clearer confirmation"
    return "No decisive VSA context yet"


def _event_sentence(events: tuple[DecisionContextEvent, ...]) -> str:
    if not events:
        return ""

    recent = events[-3:]
    codes = ", ".join(event.code for event in recent)
    return f"Most relevant recent events: {codes}."


def _confirmation_condition(bias: SupplyDemandBias) -> str:
    if bias is SupplyDemandBias.BULLISH:
        return (
            "Look for fresh demand, low-volume pullback holding support, or a "
            "strong close that confirms supply has dried up."
        )
    if bias is SupplyDemandBias.BEARISH:
        return (
            "Look for fresh supply, weak rally behavior, or a poor close that "
            "confirms demand is failing."
        )
    return "Wait for directional VSA evidence and structural confirmation."


def _invalidation_condition(bias: SupplyDemandBias) -> str:
    if bias is SupplyDemandBias.BULLISH:
        return (
            "A decisive breakdown below the recent test/support area or renewed "
            "high-quality supply weakens the bullish story."
        )
    if bias is SupplyDemandBias.BEARISH:
        return (
            "A decisive recovery above the recent supply area or strong demand "
            "weakens the bearish story."
        )
    return "Conflicting high-quality evidence keeps the current story unconfirmed."


def _expectations(
    *,
    bias: SupplyDemandBias,
    tradability: TradabilityStatus,
) -> tuple[str, ...]:
    if tradability is TradabilityStatus.AVOID:
        return (
            "Treat this as observation only until the anomalous signal bar is reviewed.",
            "Re-run the analysis after adjusted or confirmed OHLCV data is available.",
        )
    if bias is SupplyDemandBias.BULLISH:
        return (
            "Constructive pullbacks should show lower volume and hold above recent support.",
            "Fresh demand with wider spread and a strong close would improve tradability.",
            "Failure below the recent test/support area weakens the accumulation thesis.",
        )
    if bias is SupplyDemandBias.BEARISH:
        return (
            "Rallies should struggle on weak demand if supply remains dominant.",
            "Fresh supply with poor close behavior would strengthen the bearish read.",
            "Strong recovery above the recent supply area weakens the distribution thesis.",
        )
    return (
        "Expect choppy or unclear behavior until fresh directional VSA evidence appears.",
        "Wait for a clearer sequence before treating the setup as decision-worthy.",
    )


def _iter_items(value: Iterable[Any] | None) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, tuple):
        return value
    if isinstance(value, list):
        return tuple(value)
    return tuple(value)


def _enum_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    enum_value = getattr(value, "value", None)
    if isinstance(enum_value, str):
        return enum_value
    enum_name = getattr(value, "name", None)
    if enum_name is not None:
        return str(enum_name)
    return str(value)


def _enum_name(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    enum_name = getattr(value, "name", None)
    if enum_name is not None:
        return str(enum_name)
    enum_value = getattr(value, "value", None)
    if enum_value is not None:
        return str(enum_value)
    return str(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "DECISION_CONTEXT_SCHEMA_VERSION",
    "DEFAULT_DECISION_CONTEXT_ROOT",
    "DEFAULT_MAX_DECISION_EVENTS",
    "DEFAULT_MAX_STRUCTURAL_SWINGS",
    "DecisionAction",
    "DecisionContext",
    "DecisionContextEvent",
    "DecisionContextStore",
    "DecisionMode",
    "MarketPhaseContext",
    "StructuralSwingMemory",
    "SupplyDemandBias",
    "TradabilityStatus",
    "VSAStorySummary",
    "build_decision_context",
]
