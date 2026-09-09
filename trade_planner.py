"""Analysis-only trade planning layer for confirmed VSA context.

This module converts the confirmed weekly VSA decision context plus recent
structure into a readable trade-planning draft. It deliberately avoids broker,
order, account, funds, holdings, margin, credential, or position-size scope.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TradePlanLevel:
    """A nearby structural area used for planning context, not an order level."""

    label: str
    price: float | None
    lower: float | None
    upper: float | None
    source: str
    note: str

    def to_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "price": self.price,
            "lower": self.lower,
            "upper": self.upper,
            "source": self.source,
            "note": self.note,
        }


@dataclass(frozen=True)
class TradePlan:
    """Readable trade-plan draft for decision support only."""

    posture: str
    setup_type: str
    reference_price: float | None
    support: TradePlanLevel
    resistance: TradePlanLevel
    entry_condition: str
    confirmation_trigger: str
    invalidation_condition: str
    risk_reading: str
    reward_reading: str
    notes: tuple[str, ...]
    analysis_only: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "posture": self.posture,
            "setup_type": self.setup_type,
            "reference_price": self.reference_price,
            "support": self.support.to_dict(),
            "resistance": self.resistance.to_dict(),
            "entry_condition": self.entry_condition,
            "confirmation_trigger": self.confirmation_trigger,
            "invalidation_condition": self.invalidation_condition,
            "risk_reading": self.risk_reading,
            "reward_reading": self.reward_reading,
            "notes": list(self.notes),
            "analysis_only": self.analysis_only,
        }


def build_trade_plan(analysis: Any) -> TradePlan:
    """Build a trade-planning draft from one confirmed analysis result.

    The caller owns data loading, completed-week filtering, and scanner
    execution. This function performs only a bounded pass over already-returned
    bars/swings and does not mutate state or call any external provider.
    """
    context = _field(analysis, "decision_context")
    bars = list(_field(analysis, "bars", ()) or ())
    swings = list(_field(analysis, "structural_swings", ()) or ())
    latest_bar = bars[-1] if bars else None
    reference_price = _optional_float(_field(latest_bar, "close"))
    support = _support_level(swings)
    resistance = _resistance_level(swings)
    bias = _text(_field(context, "bias")).lower()
    tradability = _text(_field(context, "tradability")).lower()
    decision = _text(_field(context, "decision")).lower()
    confidence = _optional_float(_field(context, "confidence"))

    return TradePlan(
        posture=_posture(bias=bias, tradability=tradability, decision=decision),
        setup_type=_setup_type(bias=bias, tradability=tradability),
        reference_price=reference_price,
        support=support,
        resistance=resistance,
        entry_condition=_entry_condition(
            bias=bias,
            tradability=tradability,
            support=support,
            resistance=resistance,
        ),
        confirmation_trigger=_confirmation_trigger(context, bias=bias),
        invalidation_condition=_invalidation_condition(
            context,
            bias=bias,
            support=support,
            resistance=resistance,
        ),
        risk_reading=_risk_reading(
            bias=bias,
            reference_price=reference_price,
            support=support,
            resistance=resistance,
            confidence=confidence,
        ),
        reward_reading=_reward_reading(
            bias=bias,
            reference_price=reference_price,
            support=support,
            resistance=resistance,
        ),
        notes=(
            "Decision-support plan only; this is not an order signal.",
            "No broker, account, funds, holdings, margin, position-size, or order action is produced.",
            "Use completed weekly context only; review lower-timeframe execution separately if needed.",
        ),
    )


def _posture(*, bias: str, tradability: str, decision: str) -> str:
    if "avoid" in tradability or "avoid" in decision:
        return "Avoid"
    if "bear" in bias:
        return "Avoid bullish swing setup"
    if "tradable" in tradability or "review" in decision:
        return "Review setup"
    if "pullback" in tradability or "pullback" in decision:
        return "Wait for pullback"
    if "confirmation" in tradability or "confirmation" in decision:
        return "Wait for confirmation"
    return "Observation only"


def _setup_type(*, bias: str, tradability: str) -> str:
    if "avoid" in tradability:
        return "No valid setup"
    if "bear" in bias:
        return "Bearish context / no bullish swing plan"
    if "bull" in bias and "pullback" in tradability:
        return "Bullish pullback watch"
    if "bull" in bias and "confirmation" in tradability:
        return "Bullish confirmation watch"
    if "bull" in bias:
        return "Bullish continuation review"
    if "mixed" in bias:
        return "Mixed context watch"
    return "No clear setup"


def _entry_condition(
    *,
    bias: str,
    tradability: str,
    support: TradePlanLevel,
    resistance: TradePlanLevel,
) -> str:
    if "avoid" in tradability:
        return "Do not review an entry until the avoid/data-quality condition clears."
    if "bear" in bias:
        return "No bullish entry condition. Wait until supply is absorbed and the VSA story turns constructive."
    if "bull" not in bias:
        return "Wait for a clearer bullish background before planning an entry."

    support_text = _level_text(support)
    if "pullback" in tradability:
        return (
            f"Review only if price pulls back toward {support_text} and the pullback shows No Supply, "
            "fresh demand, or a strong recovery close."
        )
    if "confirmation" in tradability:
        return (
            "Wait for fresh demand or a strong close that confirms supply has dried up before reviewing a trade."
        )
    return (
        f"Review only after either a controlled pullback holds {support_text} or fresh demand confirms continuation."
    )


def _confirmation_trigger(context: Any, *, bias: str) -> str:
    story = _field(context, "story")
    configured = _text(_field(story, "confirmation_condition")).strip()
    if configured:
        return configured
    if "bull" in bias:
        return "Fresh demand, No Supply after pullback, or a strong weekly close would confirm the bullish plan."
    if "bear" in bias:
        return "Fresh supply or a weak rally response would confirm the bearish risk."
    return "Wait for directional VSA evidence and structural confirmation."


def _invalidation_condition(
    context: Any,
    *,
    bias: str,
    support: TradePlanLevel,
    resistance: TradePlanLevel,
) -> str:
    story = _field(context, "story")
    configured = _text(_field(story, "invalidation_condition")).strip()
    if configured:
        return configured
    if "bull" in bias and support.price is not None:
        return f"A decisive failure below {_level_text(support)} invalidates the bullish planning context."
    if "bear" in bias and resistance.price is not None:
        return f"A decisive recovery above {_level_text(resistance)} weakens the bearish context."
    return "Conflicting high-quality VSA evidence invalidates the plan."


def _risk_reading(
    *,
    bias: str,
    reference_price: float | None,
    support: TradePlanLevel,
    resistance: TradePlanLevel,
    confidence: float | None,
) -> str:
    if reference_price is None:
        return "Risk cannot be classified because the latest close is unavailable."
    if "bull" in bias:
        if support.price is None or support.price <= 0:
            return "Risk is unknown because no recent confirmed support area is available."
        distance = ((reference_price - support.price) / reference_price) * 100.0
        if distance < 0:
            return "Price is below the recent support area, so the bullish plan is not valid yet."
        if distance <= 3.0:
            return "Risk is close to nearby support and may be acceptable if confirmation appears."
        if distance <= 8.0:
            return "Risk is moderate; wait for a controlled pullback or stronger confirmation."
        return "Risk is elevated because price is extended above the recent support area."

    if "bear" in bias:
        if resistance.price is None or resistance.price <= 0:
            return "Risk is defensive; no recent confirmed resistance area is available."
        distance = ((resistance.price - reference_price) / reference_price) * 100.0
        if distance < 0:
            return "Price is above the recent resistance area, so bearish pressure may be weakening."
        if distance <= 4.0:
            return "Upside risk is nearby; avoid bullish plans until supply clears."
        return "Bearish context remains, but the distance to resistance should still be respected."

    if confidence is not None and confidence < 0.45:
        return "Risk is elevated because the VSA context has low conviction."
    return "Risk is unclear until the background becomes more directional."


def _reward_reading(
    *,
    bias: str,
    reference_price: float | None,
    support: TradePlanLevel,
    resistance: TradePlanLevel,
) -> str:
    if reference_price is None:
        return "Reward potential cannot be estimated because the latest close is unavailable."
    if "bull" in bias:
        if resistance.price is None or resistance.price <= 0:
            return "Reward is open-ended but cannot be mapped because no recent resistance area is available."
        potential = ((resistance.price - reference_price) / reference_price) * 100.0
        if potential <= 0:
            return "Reward is limited because price is already near or above the recent resistance area."
        if potential >= 12.0:
            return "Reward potential is favorable if demand confirms and resistance remains above price."
        if potential >= 5.0:
            return "Reward potential is moderate and depends on clean follow-through."
        return "Reward potential is limited unless price builds a new base or clears resistance."
    if "bear" in bias:
        return "Bullish reward is not attractive while supply remains the dominant context."
    return "Reward potential is unclear until demand, supply, and structure align."


def _support_level(swings: list[Any]) -> TradePlanLevel:
    swing = _last_swing(swings, want_low=True)
    if swing is None:
        return _empty_level("Support", "No confirmed swing-low support is available yet.")
    price = _optional_float(_field(swing, "price"))
    label = _text(_field(swing, "label")) or "Swing low"
    return _level(
        label=f"Support area from {label}",
        price=price,
        source=f"Confirmed swing low at {_text(_field(swing, 'week')) or _text(_field(swing, 'pivot_week'))}",
        note="Use as planning context; confirmation still comes from VSA behavior around the area.",
    )


def _resistance_level(swings: list[Any]) -> TradePlanLevel:
    swing = _last_swing(swings, want_low=False)
    if swing is None:
        return _empty_level("Resistance", "No confirmed swing-high resistance is available yet.")
    price = _optional_float(_field(swing, "price"))
    label = _text(_field(swing, "label")) or "Swing high"
    return _level(
        label=f"Resistance area from {label}",
        price=price,
        source=f"Confirmed swing high at {_text(_field(swing, 'week')) or _text(_field(swing, 'pivot_week'))}",
        note="Use as planning context; it is not a guaranteed target.",
    )


def _last_swing(swings: list[Any], *, want_low: bool) -> Any | None:
    for swing in reversed(swings):
        if bool(_field(swing, "is_failed", False)):
            continue
        type_text = _text(_field(swing, "type")).lower()
        label_text = _text(_field(swing, "label")).lower()
        is_low = "low" in type_text or label_text in {"hl", "ll"}
        is_high = "high" in type_text or label_text in {"hh", "lh"}
        if want_low and is_low:
            return swing
        if not want_low and is_high:
            return swing
    return None


def _level(
    *,
    label: str,
    price: float | None,
    source: str,
    note: str,
) -> TradePlanLevel:
    if price is None or price <= 0:
        return _empty_level(label, note)
    lower = round(price * 0.99, 2)
    upper = round(price * 1.01, 2)
    return TradePlanLevel(
        label=label,
        price=round(price, 2),
        lower=lower,
        upper=upper,
        source=source,
        note=note,
    )


def _empty_level(label: str, note: str) -> TradePlanLevel:
    return TradePlanLevel(
        label=label,
        price=None,
        lower=None,
        upper=None,
        source="Not available",
        note=note,
    )


def _level_text(level: TradePlanLevel) -> str:
    if level.price is None:
        return level.label.lower()
    if level.lower is not None and level.upper is not None:
        return f"{level.label.lower()} ({level.lower:.2f}–{level.upper:.2f})"
    return f"{level.label.lower()} near {level.price:.2f}"


def _field(value: Any, name: str, default: Any = None) -> Any:
    if value is None:
        return default
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _text(value: Any) -> str:
    if value is None:
        return ""
    enum_value = getattr(value, "value", None)
    if isinstance(enum_value, str):
        return enum_value
    return str(value)


def _optional_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


__all__ = [
    "TradePlan",
    "TradePlanLevel",
    "build_trade_plan",
]
