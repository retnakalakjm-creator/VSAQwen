from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Iterable

from qualification_lifecycle_labels import (
    AUDIT_ONLY_CANDIDATE_CODES,
    DEFAULT_MAX_ACTIONABLE_VSA_AGE,
)


class AbsorptionBackgroundReviewLabel(StrEnum):
    """Review-only labels for absorption-background evidence."""

    NONE = "none"
    REVIEW = "absorption_background_review"
    BLOCKED = "absorption_background_blocked"
    NEEDS_FOLLOW_THROUGH = "absorption_background_needs_follow_through"


PRIOR_SUPPLY_CONTEXT_CODES = frozenset(
    {
        "persistent_bearish",
        "increasing_supply",
        "supply_coming_in",
        "hidden_supply",
        "structural_progression_weakening",
        "buying_climax",
        "markdown",
        "distribution",
        "redistribution",
    }
)

ABSORPTION_BACKGROUND_CODES = frozenset(
    {
        "supply_absorption",
        "stopping_volume",
    }
)

ABSORPTION_DIAGNOSTIC_HINT_CODES = frozenset(
    {
        "review_potential_absorption",
        "audit_absorption_candidate",
        "absorption",
    }
)

DEMAND_REVERSAL_FOLLOW_THROUGH_CODES = frozenset(
    {
        "demand_coming_in",
        "increasing_demand",
        "high_volume_reversal",
    }
)

ABSORPTION_BACKGROUND_BLOCKER_CODES = frozenset(
    {
        "increasing_supply",
        "supply_coming_in",
        "hidden_supply",
        "structural_progression_weakening",
    }
)

ABSORPTION_BACKGROUND_FRONTEND_LABEL = "Absorption Background Review"

ABSORPTION_BACKGROUND_PLAIN_ENGLISH = (
    "Selling pressure may be getting absorbed. The bearish background is weakening, "
    "but this is not yet a confirmed bullish reversal."
)


@dataclass(frozen=True, slots=True)
class AbsorptionBackgroundReviewResult:
    """Read-only review marker result for absorption-background evidence."""

    status: AbsorptionBackgroundReviewLabel
    review_marker: str | None
    frontend_label: str | None
    plain_english: str
    qualification: str
    prior_supply_codes: tuple[str, ...]
    absorption_codes: tuple[str, ...]
    follow_through_codes: tuple[str, ...]
    blocker_codes: tuple[str, ...]
    diagnostic_hint_codes: tuple[str, ...]
    ignored_audit_only_codes: tuple[str, ...]
    follow_through_evidence_age: int | None
    used_fallback_evidence: bool
    reason: str
    production_safe: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "review_marker": self.review_marker,
            "frontend_label": self.frontend_label,
            "plain_english": self.plain_english,
            "qualification": self.qualification,
            "prior_supply_codes": list(self.prior_supply_codes),
            "absorption_codes": list(self.absorption_codes),
            "follow_through_codes": list(self.follow_through_codes),
            "blocker_codes": list(self.blocker_codes),
            "diagnostic_hint_codes": list(self.diagnostic_hint_codes),
            "ignored_audit_only_codes": list(self.ignored_audit_only_codes),
            "follow_through_evidence_age": self.follow_through_evidence_age,
            "used_fallback_evidence": self.used_fallback_evidence,
            "reason": self.reason,
            "production_safe": self.production_safe,
        }


def label_absorption_background_review(
    *,
    qualification: Any = "",
    prior_evidence: Iterable[Any] | None = None,
    absorption_evidence: Iterable[Any] | None = None,
    follow_through_evidence: Iterable[Any] | None = None,
    same_window_evidence: Iterable[Any] | None = None,
    diagnostic_evidence: Iterable[Any] | None = None,
    follow_through_evidence_age: int | None = None,
    used_fallback_evidence: bool = False,
    max_actionable_vsa_age: int = DEFAULT_MAX_ACTIONABLE_VSA_AGE,
) -> AbsorptionBackgroundReviewResult:
    """Return a conservative review-only marker for absorption background.

    The helper is deliberately pure. It reads already-known evidence only and
    does not load market data, replay scanner history, mutate scanner state,
    activate detector families, change scoring/ranking, write persistence, or
    flip a persistent bearish qualification bullish.

    Diagnostic/audit hints may be reported for casebook context, but they do not
    become production absorption evidence.
    """

    qualification_text = _enum_text(qualification)
    prior_codes_raw = _evidence_codes(prior_evidence)
    absorption_codes_raw = _evidence_codes(absorption_evidence)
    follow_codes_raw = _evidence_codes(follow_through_evidence)
    same_window_codes_raw = _evidence_codes(same_window_evidence)
    diagnostic_codes_raw = _evidence_codes(diagnostic_evidence)

    ignored_audit_codes = _dedupe(
        code
        for code in (
            *prior_codes_raw,
            *absorption_codes_raw,
            *follow_codes_raw,
            *same_window_codes_raw,
            *diagnostic_codes_raw,
        )
        if code in AUDIT_ONLY_CANDIDATE_CODES
    )

    prior_codes = _without_audit_only(prior_codes_raw)
    absorption_codes_clean = _without_audit_only(absorption_codes_raw)
    follow_codes = _without_audit_only(follow_codes_raw)
    same_window_codes = _without_audit_only(same_window_codes_raw)
    diagnostic_codes = _dedupe((*diagnostic_codes_raw, *ignored_audit_codes))

    prior_supply_codes = _select_codes(prior_codes, PRIOR_SUPPLY_CONTEXT_CODES)
    if _is_persistent_bearish(qualification_text) and "persistent_bearish" not in prior_supply_codes:
        prior_supply_codes = ("persistent_bearish", *prior_supply_codes)

    absorption_codes = _select_codes(absorption_codes_clean, ABSORPTION_BACKGROUND_CODES)
    follow_through_codes = _select_codes(
        follow_codes,
        DEMAND_REVERSAL_FOLLOW_THROUGH_CODES,
    )
    blocker_codes = _select_codes(same_window_codes, ABSORPTION_BACKGROUND_BLOCKER_CODES)
    diagnostic_hint_codes = _select_codes(
        diagnostic_codes,
        ABSORPTION_DIAGNOSTIC_HINT_CODES,
    )
    has_stale_follow_through = _is_stale(
        follow_through_evidence_age,
        max_actionable_vsa_age,
    )

    if not prior_supply_codes:
        return _result(
            status=AbsorptionBackgroundReviewLabel.NONE,
            qualification=qualification_text,
            prior_supply_codes=prior_supply_codes,
            absorption_codes=absorption_codes,
            follow_through_codes=follow_through_codes,
            blocker_codes=blocker_codes,
            diagnostic_hint_codes=diagnostic_hint_codes,
            ignored_audit_only_codes=ignored_audit_codes,
            follow_through_evidence_age=follow_through_evidence_age,
            used_fallback_evidence=used_fallback_evidence,
            reason=(
                "No prior supply pressure or bearish background exists, so "
                "absorption-background review is not marked."
            ),
        )

    if not absorption_codes:
        return _result(
            status=AbsorptionBackgroundReviewLabel.NONE,
            qualification=qualification_text,
            prior_supply_codes=prior_supply_codes,
            absorption_codes=absorption_codes,
            follow_through_codes=follow_through_codes,
            blocker_codes=blocker_codes,
            diagnostic_hint_codes=diagnostic_hint_codes,
            ignored_audit_only_codes=ignored_audit_codes,
            follow_through_evidence_age=follow_through_evidence_age,
            used_fallback_evidence=used_fallback_evidence,
            reason=(
                "Prior supply context exists, but no production absorption or "
                "stopping-volume evidence is present. Diagnostic hints remain "
                "review context only."
            ),
        )

    if not follow_through_codes or has_stale_follow_through or used_fallback_evidence:
        return _result(
            status=AbsorptionBackgroundReviewLabel.NEEDS_FOLLOW_THROUGH,
            qualification=qualification_text,
            prior_supply_codes=prior_supply_codes,
            absorption_codes=absorption_codes,
            follow_through_codes=follow_through_codes,
            blocker_codes=blocker_codes,
            diagnostic_hint_codes=diagnostic_hint_codes,
            ignored_audit_only_codes=ignored_audit_codes,
            follow_through_evidence_age=follow_through_evidence_age,
            used_fallback_evidence=used_fallback_evidence,
            reason=(
                "Absorption-style evidence exists after supply pressure, but "
                "fresh demand or reversal follow-through is missing, stale, or fallback-only."
            ),
        )

    if blocker_codes:
        return _result(
            status=AbsorptionBackgroundReviewLabel.BLOCKED,
            qualification=qualification_text,
            prior_supply_codes=prior_supply_codes,
            absorption_codes=absorption_codes,
            follow_through_codes=follow_through_codes,
            blocker_codes=blocker_codes,
            diagnostic_hint_codes=diagnostic_hint_codes,
            ignored_audit_only_codes=ignored_audit_codes,
            follow_through_evidence_age=follow_through_evidence_age,
            used_fallback_evidence=used_fallback_evidence,
            reason=(
                "Absorption-style evidence and fresh follow-through are present, "
                "but same-window supply or structural weakness blocks a clean "
                "background review marker."
            ),
        )

    return _result(
        status=AbsorptionBackgroundReviewLabel.REVIEW,
        qualification=qualification_text,
        prior_supply_codes=prior_supply_codes,
        absorption_codes=absorption_codes,
        follow_through_codes=follow_through_codes,
        blocker_codes=blocker_codes,
        diagnostic_hint_codes=diagnostic_hint_codes,
        ignored_audit_only_codes=ignored_audit_codes,
        follow_through_evidence_age=follow_through_evidence_age,
        used_fallback_evidence=used_fallback_evidence,
        reason=(
            "Prior supply context, absorption-style evidence, and fresh demand/reversal "
            "follow-through are present; mark review-only absorption background without "
            "flipping bullish."
        ),
    )


def _result(
    *,
    status: AbsorptionBackgroundReviewLabel,
    qualification: str,
    prior_supply_codes: tuple[str, ...],
    absorption_codes: tuple[str, ...],
    follow_through_codes: tuple[str, ...],
    blocker_codes: tuple[str, ...],
    diagnostic_hint_codes: tuple[str, ...],
    ignored_audit_only_codes: tuple[str, ...],
    follow_through_evidence_age: int | None,
    used_fallback_evidence: bool,
    reason: str,
) -> AbsorptionBackgroundReviewResult:
    is_review = status is AbsorptionBackgroundReviewLabel.REVIEW
    return AbsorptionBackgroundReviewResult(
        status=status,
        review_marker=status.value if is_review else None,
        frontend_label=ABSORPTION_BACKGROUND_FRONTEND_LABEL if is_review else None,
        plain_english=ABSORPTION_BACKGROUND_PLAIN_ENGLISH,
        qualification=qualification,
        prior_supply_codes=prior_supply_codes,
        absorption_codes=absorption_codes,
        follow_through_codes=follow_through_codes,
        blocker_codes=blocker_codes,
        diagnostic_hint_codes=diagnostic_hint_codes,
        ignored_audit_only_codes=ignored_audit_only_codes,
        follow_through_evidence_age=follow_through_evidence_age,
        used_fallback_evidence=used_fallback_evidence,
        reason=reason,
    )


def _select_codes(codes: Iterable[str], selected: frozenset[str]) -> tuple[str, ...]:
    return tuple(code for code in codes if code in selected)


def _without_audit_only(codes: Iterable[str]) -> tuple[str, ...]:
    return tuple(code for code in codes if code not in AUDIT_ONLY_CANDIDATE_CODES)


def _is_persistent_bearish(qualification: str) -> bool:
    lowered = qualification.lower()
    return "persistent_bearish" in lowered or lowered.endswith("bearish") or "bearish" in lowered


def _is_stale(age: int | None, max_actionable_vsa_age: int) -> bool:
    return age is not None and age > max_actionable_vsa_age


def _evidence_codes(scoring_evidence: Iterable[Any] | None) -> tuple[str, ...]:
    if scoring_evidence is None:
        return ()
    codes: list[str] = []
    for item in scoring_evidence:
        code_value = item.get("code") if isinstance(item, dict) else getattr(item, "code", item)
        code = _enum_text(code_value).strip()
        if code:
            codes.append(code)
    return _dedupe(codes)


def _enum_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    enum_value = getattr(value, "value", None)
    if isinstance(enum_value, str):
        return enum_value
    enum_name = getattr(value, "name", None)
    if isinstance(enum_name, str):
        return enum_name.lower()
    return str(value)


def _dedupe(items: Iterable[str]) -> tuple[str, ...]:
    selected: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item not in seen:
            selected.append(item)
            seen.add(item)
    return tuple(selected)


__all__ = [
    "ABSORPTION_BACKGROUND_BLOCKER_CODES",
    "ABSORPTION_BACKGROUND_CODES",
    "ABSORPTION_BACKGROUND_FRONTEND_LABEL",
    "ABSORPTION_BACKGROUND_PLAIN_ENGLISH",
    "ABSORPTION_DIAGNOSTIC_HINT_CODES",
    "DEMAND_REVERSAL_FOLLOW_THROUGH_CODES",
    "PRIOR_SUPPLY_CONTEXT_CODES",
    "AbsorptionBackgroundReviewLabel",
    "AbsorptionBackgroundReviewResult",
    "label_absorption_background_review",
]
