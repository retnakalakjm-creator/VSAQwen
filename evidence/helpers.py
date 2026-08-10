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
from .profiles import (
    EVIDENCE_REGISTRY,
)

# ----------------------------------------------------------
# Collector Type
# ----------------------------------------------------------
EvidenceCollector = Callable[
    [BackgroundContext],
    list[Evidence],
]


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
    """
    Return True if evidence already exists.
    """

    return any(
        item.code == code
        for item in evidence
    )


def count_evidence(
    evidence: list[Evidence],
    code: EvidenceCode,
) -> int:

    return sum(
        1
        for item in evidence
        if item.code == code
    )

def requirement(
    *,
    name: str,
    passed: bool,
    mandatory: bool = True,
    message: str | None = None,
) -> Requirement:
    """
    Construct one detector requirement.
    """

    return Requirement(
        name=name,
        passed=passed,
        mandatory=mandatory,
        message=message,
    )



def requirements_passed(
    requirements: tuple[
        Requirement,
        ...
    ],
) -> bool:
    """
    Return True only if every mandatory requirement passes.
    """

    return all(

        requirement.passed

        for requirement in requirements

        if requirement.mandatory

    )

def confirmation_score(
    *conditions: bool,
) -> tuple[int, float]:
    """
    Returns

    (
        confirmations,
        confidence,
    )
    """

    passed = sum(conditions)

    confidence = (
        passed / len(conditions)
        if conditions
        else 0.0
    )

    return passed, confidence

def confirmation_count(
    confirmations: tuple[
        Requirement,
        ...
    ],
) -> int:
    """
    Number of passed confirmations.
    """

    return sum(

        confirmation.passed

        for confirmation in confirmations

    )
    
def passed_requirements(
    requirements: tuple[
        Requirement,
        ...
    ],
) -> tuple[
        Requirement,
        ...
    ]:
    """
    Return all satisfied requirements.
    """

    return tuple(

        requirement

        for requirement in requirements

        if requirement.passed

    )

def failed_requirements(
    requirements: tuple[
        Requirement,
        ...
    ],
) -> tuple[
        Requirement,
        ...
    ]:
    """
    Return all failed requirements.
    """

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
    requirements: tuple[
        Requirement,
        ...
    ],
    confirmations: tuple[
        Requirement,
        ...
    ] = (),
    test_index: int | None = None,
    recovery_index: int | None = None,
    quality: float = 1.0,
) -> bool:
    """
    Evaluate one Evidence detector.

    All mandatory requirements must pass.

    Confirmations are reserved for future
    confidence and strength scoring.

    Returns
    -------
    bool
        True if Evidence was generated.
    """

    if not requirements_passed(
        requirements,
    ):
        return False

    # ----------------------------------------
    # Future:
    # Confidence / Strength adjustment
    # ----------------------------------------

    confirmation_score = confirmation_count(
        confirmations,
    )

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
    
    "requirements_passed",
    
    "passed_requirements",
    
    "failed_requirements",
    
    "evaluate_detector",
]