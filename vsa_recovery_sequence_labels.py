from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Iterable

from qualification_lifecycle_labels import (
    AUDIT_ONLY_CANDIDATE_CODES,
    DEFAULT_MAX_ACTIONABLE_VSA_AGE,
)


class RecoverySequenceReviewLabel(StrEnum):
    """Review-only labels for Stopping Volume -> Spring/Shakeout sequences."""

    NONE = "none"
    REVIEW = "stopping_volume_spring_shakeout_review"
    BLOCKED = "stopping_volume_spring_shakeout_blocked"
    NEEDS_FOLLOW_THROUGH = "stopping_volume_spring_shakeout_needs_follow_through"


PRIOR_WEAKNESS_CODES = frozenset(
    {
        "persistent_bearish",
        "increasing_supply",
        "supply_coming_in",
        "hidden_supply",
        "supply_absorption",
        "structural_progression_weakening",
        "buying_climax",
        "markdown",
        "distribution",
        "redistribution",
    }
)

STOPPING_VOLUME_ANCHOR_CODES = frozenset(
    {
        "stopping_volume",
        "supply_absorption",
    }
)

SPRING_SHAKEOUT_TEST_CODES = frozenset(
    {
        "spring",
        "shakeout",
    }
)

DEMAND_FOLLOW_THROUGH_CODES = frozenset(
    {
        "demand_coming_in",
        "increasing_demand",
    }
)

RECOVERY_SEQUENCE_BLOCKER_CODES = frozenset(
    {
        "increasing_supply",
        "supply_coming_in",
        "hidden_supply",
        "structural_progression_weakening",
    }
)


@dataclass(frozen=True, slots=True)
class RecoverySequenceReviewResult:
    """Read-only review marker result for recovery-sequence evidence."""

    status: RecoverySequenceReviewLabel
    review_marker: str | None
    qualification: str
    prior_weakness_codes: tuple[str, ...]
    stopping_volume_codes: tuple[str, ...]
    spring_shakeout_codes: tuple[str, ...]
    follow_through_codes: tuple[str, ...]
    blocker_codes: tuple[str, ...]
    ignored_audit_only_codes: tuple[str, ...]
    follow_through_evidence_age: int | None
    used_fallback_evidence: bool
    reason: str
    production_safe: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "review_marker": self.review_marker,
            "qualification": self.qualification,
            "prior_weakness_codes": list(self.prior_weakness_codes),
            "stopping_volume_codes": list(self.stopping_volume_codes),
            "spring_shakeout_codes": list(self.spring_shakeout_codes),
            "follow_through_codes": list(self.follow_through_codes),
            "blocker_codes": list(self.blocker_codes),
            "ignored_audit_only_codes": list(self.ignored_audit_only_codes),
            "follow_through_evidence_age": self.follow_through_evidence_age,
            "used_fallback_evidence": self.used_fallback_evidence,
            "reason": self.reason,
            "production_safe": self.production_safe,
        }


def label_stopping_volume_spring_shakeout_review(
    *,
    qualification: Any = "",
    prior_evidence: Iterable[Any] | None = None,
    stopping_volume_evidence: Iterable[Any] | None = None,
    spring_shakeout_evidence: Iterable[Any] | None = None,
    follow_through_evidence: Iterable[Any] | None = None,
    same_window_evidence: Iterable[Any] | None = None,
    follow_through_evidence_age: int | None = None,
    used_fallback_evidence: bool = False,
    max_actionable_vsa_age: int = DEFAULT_MAX_ACTIONABLE_VSA_AGE,
) -> RecoverySequenceReviewResult:
    """Return a conservative review-only marker for a recovery sequence.

    The helper is deliberately pure: it does not load market data, mutate scanner
    state, change scoring/ranking, activate detector families, or flip a
    persistent bearish qualification bullish. Callers must supply already-known
    evidence split into sequence stages.
    """

    qualification_text = _enum_text(qualification)
    prior_codes_raw = _evidence_codes(prior_evidence)
    anchor_codes_raw = _evidence_codes(stopping_volume_evidence)
    test_codes_raw = _evidence_codes(spring_shakeout_evidence)
    follow_codes_raw = _evidence_codes(follow_through_evidence)
    same_window_codes_raw = _evidence_codes(same_window_evidence)

    ignored_audit_codes = _dedupe(
        code
        for code in (
            *prior_codes_raw,
            *anchor_codes_raw,
            *test_codes_raw,
            *follow_codes_raw,
            *same_window_codes_raw,
        )
        if code in AUDIT_ONLY_CANDIDATE_CODES
    )

    prior_codes = _without_audit_only(prior_codes_raw)
    anchor_codes = _without_audit_only(anchor_codes_raw)
    test_codes = _without_audit_only(test_codes_raw)
    follow_codes = _without_audit_only(follow_codes_raw)
    same_window_codes = _without_audit_only(same_window_codes_raw)

    prior_weakness_codes = _select_codes(prior_codes, PRIOR_WEAKNESS_CODES)
    if _is_persistent_bearish(qualification_text) and "persistent_bearish" not in prior_weakness_codes:
        prior_weakness_codes = ("persistent_bearish", *prior_weakness_codes)

    stopping_volume_codes = _select_codes(anchor_codes, STOPPING_VOLUME_ANCHOR_CODES)
    spring_shakeout_codes = _select_codes(test_codes, SPRING_SHAKEOUT_TEST_CODES)
    follow_through_codes = _select_codes(follow_codes, DEMAND_FOLLOW_THROUGH_CODES)
    blocker_codes = _select_codes(same_window_codes, RECOVERY_SEQUENCE_BLOCKER_CODES)

    has_stale_follow_through = _is_stale(
        follow_through_evidence_age,
        max_actionable_vsa_age,
    )

    if not prior_weakness_codes:
        return _result(
            status=RecoverySequenceReviewLabel.NONE,
            qualification=qualification_text,
            prior_weakness_codes=prior_weakness_codes,
            stopping_volume_codes=stopping_volume_codes,
            spring_shakeout_codes=spring_shakeout_codes,
            follow_through_codes=follow_through_codes,
            blocker_codes=blocker_codes,
            ignored_audit_only_codes=ignored_audit_codes,
            follow_through_evidence_age=follow_through_evidence_age,
            used_fallback_evidence=used_fallback_evidence,
            reason="No prior weakness context exists, so no recovery sequence is marked.",
        )

    if not stopping_volume_codes:
        return _result(
            status=RecoverySequenceReviewLabel.NONE,
            qualification=qualification_text,
            prior_weakness_codes=prior_weakness_codes,
            stopping_volume_codes=stopping_volume_codes,
            spring_shakeout_codes=spring_shakeout_codes,
            follow_through_codes=follow_through_codes,
            blocker_codes=blocker_codes,
            ignored_audit_only_codes=ignored_audit_codes,
            follow_through_evidence_age=follow_through_evidence_age,
            used_fallback_evidence=used_fallback_evidence,
            reason="Prior weakness exists, but no stopping-volume or supply-absorption anchor is present.",
        )

    if not spring_shakeout_codes:
        return _result(
            status=RecoverySequenceReviewLabel.NONE,
            qualification=qualification_text,
            prior_weakness_codes=prior_weakness_codes,
            stopping_volume_codes=stopping_volume_codes,
            spring_shakeout_codes=spring_shakeout_codes,
            follow_through_codes=follow_through_codes,
            blocker_codes=blocker_codes,
            ignored_audit_only_codes=ignored_audit_codes,
            follow_through_evidence_age=follow_through_evidence_age,
            used_fallback_evidence=used_fallback_evidence,
            reason="Stopping-volume evidence exists, but no later Spring or Shakeout test is present.",
        )

    if not follow_through_codes or has_stale_follow_through or used_fallback_evidence:
        return _result(
            status=RecoverySequenceReviewLabel.NEEDS_FOLLOW_THROUGH,
            qualification=qualification_text,
            prior_weakness_codes=prior_weakness_codes,
            stopping_volume_codes=stopping_volume_codes,
            spring_shakeout_codes=spring_shakeout_codes,
            follow_through_codes=follow_through_codes,
            blocker_codes=blocker_codes,
            ignored_audit_only_codes=ignored_audit_codes,
            follow_through_evidence_age=follow_through_evidence_age,
            used_fallback_evidence=used_fallback_evidence,
            reason=(
                "Stopping Volume -> Spring/Shakeout context exists, but fresh "
                "same-window demand follow-through is missing, stale, or fallback-only."
            ),
        )

    if blocker_codes:
        return _result(
            status=RecoverySequenceReviewLabel.BLOCKED,
            qualification=qualification_text,
            prior_weakness_codes=prior_weakness_codes,
            stopping_volume_codes=stopping_volume_codes,
            spring_shakeout_codes=spring_shakeout_codes,
            follow_through_codes=follow_through_codes,
            blocker_codes=blocker_codes,
            ignored_audit_only_codes=ignored_audit_codes,
            follow_through_evidence_age=follow_through_evidence_age,
            used_fallback_evidence=used_fallback_evidence,
            reason=(
                "Stopping Volume -> Spring/Shakeout -> demand follow-through is present, "
                "but same-window supply or structural weakness blocks a clean review marker."
            ),
        )

    return _result(
        status=RecoverySequenceReviewLabel.REVIEW,
        qualification=qualification_text,
        prior_weakness_codes=prior_weakness_codes,
        stopping_volume_codes=stopping_volume_codes,
        spring_shakeout_codes=spring_shakeout_codes,
        follow_through_codes=follow_through_codes,
        blocker_codes=blocker_codes,
        ignored_audit_only_codes=ignored_audit_codes,
        follow_through_evidence_age=follow_through_evidence_age,
        used_fallback_evidence=used_fallback_evidence,
        reason=(
            "Prior weakness, stopping-volume anchor, Spring/Shakeout test, and fresh demand "
            "follow-through are present; mark review-only recovery sequence without flipping bullish."
        ),
    )


def _result(
    *,
    status: RecoverySequenceReviewLabel,
    qualification: str,
    prior_weakness_codes: tuple[str, ...],
    stopping_volume_codes: tuple[str, ...],
    spring_shakeout_codes: tuple[str, ...],
    follow_through_codes: tuple[str, ...],
    blocker_codes: tuple[str, ...],
    ignored_audit_only_codes: tuple[str, ...],
    follow_through_evidence_age: int | None,
    used_fallback_evidence: bool,
    reason: str,
) -> RecoverySequenceReviewResult:
    return RecoverySequenceReviewResult(
        status=status,
        review_marker=status.value if status is RecoverySequenceReviewLabel.REVIEW else None,
        qualification=qualification,
        prior_weakness_codes=prior_weakness_codes,
        stopping_volume_codes=stopping_volume_codes,
        spring_shakeout_codes=spring_shakeout_codes,
        follow_through_codes=follow_through_codes,
        blocker_codes=blocker_codes,
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
        code = _enum_text(getattr(item, "code", item)).strip()
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
    "DEMAND_FOLLOW_THROUGH_CODES",
    "PRIOR_WEAKNESS_CODES",
    "RECOVERY_SEQUENCE_BLOCKER_CODES",
    "SPRING_SHAKEOUT_TEST_CODES",
    "STOPPING_VOLUME_ANCHOR_CODES",
    "RecoverySequenceReviewLabel",
    "RecoverySequenceReviewResult",
    "label_stopping_volume_spring_shakeout_review",
]
