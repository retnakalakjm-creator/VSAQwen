"""
Shared helper functions for the Evidence Engine.

These helpers provide reusable semantic checks used by
Supply, Demand, Effort, Trend and Wyckoff modules.
"""

from __future__ import annotations
from collections.abc import Callable

from evidence.weight import WeightCalculator
from models import (
    BackgroundContext,
    Evidence,
    EvidenceCategory,
    EvidenceCode,
    EvidenceDirection,
    Requirement,
)
from .profiles import EVIDENCE_REGISTRY

EvidenceCollector = Callable[[BackgroundContext], list[Evidence]]


def add_evidence(
    *,
    evidence: list[Evidence],
    ctx: BackgroundContext,
    code: EvidenceCode,
    test_index: int | None = None,
    recovery_index: int | None = None,
    quality: float = 1.0,
) -> Evidence:
    profile = EVIDENCE_REGISTRY[code]

    if code == EvidenceCode.DEMAND_COMING_IN:
        weight = 0.38
    else:
        weight = WeightCalculator.calculate(
            code,
            ctx,
            quality=quality,
        )

    item = Evidence(
        code=profile.code,
        category=profile.category,
        direction=profile.direction,
        strength=profile.strength,
        quality=quality,
        weight=weight,
        observation=profile.observation,
        description=profile.description,
        bar_index=ctx.current.bar_index,
        week_beginning=ctx.current.week_beginning,
        test_index=test_index,
        recovery_index=recovery_index,
    )

    evidence.append(item)
    return item


def has_evidence(
    evidence: list[Evidence],
    code: EvidenceCode,
) -> bool:
    return any(item.code == code for item in evidence)


def count_evidence(
    evidence: list[Evidence],
    code: EvidenceCode,
) -> int:
    return sum(1 for item in evidence if item.code == code)


def requirement(
    *,
    name: str,
    passed: bool,
    mandatory: bool = True,
    message: str | None = None,
) -> Requirement:
    return Requirement(
        name=name,
        passed=passed,
        mandatory=mandatory,
        message=message,
    )


def requirements_passed(
    requirements: tuple[Requirement, ...],
) -> bool:
    return all(
        requirement.passed
        for requirement in requirements
        if requirement.mandatory
    )


def confirmation_score(
    *conditions: bool,
) -> tuple[int, float]:
    passed = sum(conditions)
    confidence = passed / len(conditions) if conditions else 0.0
    return passed, confidence


def confirmation_count(
    confirmations: tuple[Requirement, ...],
) -> int:
    return sum(confirmation.passed for confirmation in confirmations)


def passed_requirements(
    requirements: tuple[Requirement, ...],
) -> tuple[Requirement, ...]:
    return tuple(
        requirement
        for requirement in requirements
        if requirement.passed
    )


def failed_requirements(
    requirements: tuple[Requirement, ...],
) -> tuple[Requirement, ...]:
    return tuple(
        requirement
        for requirement in requirements
        if not requirement.passed
    )


def evaluate_detector(
    *,
    evidence: list[Evidence],
    ctx: BackgroundContext,
    code: EvidenceCode,
    requirements: tuple[Requirement, ...],
    confirmations: tuple[Requirement, ...] = (),
    test_index: int | None = None,
    recovery_index: int | None = None,
    quality: float = 1.0,
) -> bool:
    if not requirements_passed(requirements):
        return False

    confirmation_score = confirmation_count(confirmations)
    _ = confirmation_score

    add_evidence(
        evidence=evidence,
        ctx=ctx,
        code=code,
        test_index=test_index,
        recovery_index=recovery_index,
        quality=quality,
    )

    return True


__all__ = [
    "EvidenceCollector",
    "add_evidence",
    "has_evidence",
    "count_evidence",
    "requirement",
    "confirmation_score",
    "confirmation_count",
    "passed_requirements",
    "failed_requirements",
    "evaluate_detector",
]