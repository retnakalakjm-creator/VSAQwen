from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum, auto
from typing import TYPE_CHECKING

from models import EvidenceCode, EvidenceDirection

if TYPE_CHECKING:
    from model.evidence_result_model import EvidenceResult


class PatternQualification(StrEnum):
    UNQUALIFIED = auto()
    PERSISTENT_BULLISH = auto()
    PERSISTENT_BEARISH = auto()


@dataclass(slots=True, frozen=True)
class PatternQualificationResult:
    qualification: PatternQualification
    is_actionable_evidence: bool
    reason: str
    evidence_codes: tuple[EvidenceCode, ...] = ()
    evidence_bar_indices: tuple[int, ...] = ()


class PatternQualificationEngine:
    """
    Validate persistent structural progression from chronological
    point-in-time EvidenceResult snapshots.

    Structural progression is an event, not a persistent state. The
    Evidence Engine emits it when a new structural swing is confirmed,
    so qualification must inspect the chronological event history.

    A qualifying sequence is invalidated by a later opposing structural
    progression event. This keeps qualification point-in-time and prevents
    an old bearish/bullish sequence from remaining actionable indefinitely.
    """

    MIN_QUALIFYING_EVENTS = 3
    MIN_EVENT_SPACING_BARS = 4

    _BULLISH_CODES = frozenset({
        EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING,
    })

    _BEARISH_CODES = frozenset({
        EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING,
    })

    def evaluate(
        self,
        results: Sequence[EvidenceResult],
    ) -> PatternQualificationResult:
        events = self._chronological_events(results)

        bullish = self._persistent_events(
            events,
            self._BULLISH_CODES,
            EvidenceDirection.BULLISH,
        )
        bearish = self._persistent_events(
            events,
            self._BEARISH_CODES,
            EvidenceDirection.BEARISH,
        )

        if len(bearish) >= self.MIN_QUALIFYING_EVENTS:
            return PatternQualificationResult(
                qualification=PatternQualification.PERSISTENT_BEARISH,
                is_actionable_evidence=True,
                reason=(
                    "STRUCTURAL_PROGRESSION_WEAKENING remained persistently "
                    "bearish across three qualifying chronological periods."
                ),
                evidence_codes=tuple(event.code for event in bearish[-3:]),
                evidence_bar_indices=tuple(
                    event.bar_index for event in bearish[-3:]
                ),
            )

        if len(bullish) >= self.MIN_QUALIFYING_EVENTS:
            return PatternQualificationResult(
                qualification=PatternQualification.PERSISTENT_BULLISH,
                is_actionable_evidence=True,
                reason=(
                    "STRUCTURAL_PROGRESSION_IMPROVING remained persistently "
                    "bullish across three qualifying chronological periods."
                ),
                evidence_codes=tuple(event.code for event in bullish[-3:]),
                evidence_bar_indices=tuple(
                    event.bar_index for event in bullish[-3:]
                ),
            )

        return PatternQualificationResult(
            qualification=PatternQualification.UNQUALIFIED,
            is_actionable_evidence=False,
            reason="No validated persistent structural qualification applies.",
        )

    @staticmethod
    def _chronological_events(results: Sequence[EvidenceResult]):
        events = []
        seen: set[tuple[int, EvidenceCode]] = set()

        for result in results:
            for item in result.evidence:
                if item.code not in (
                    EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING,
                    EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING,
                ):
                    continue

                key = (item.bar_index, item.code)
                if key in seen:
                    continue

                seen.add(key)
                events.append(item)

        events.sort(key=lambda item: item.bar_index)
        return events

    def _persistent_events(
        self,
        events,
        codes: frozenset[EvidenceCode],
        direction: EvidenceDirection,
    ):
        selected = [
            event
            for event in events
            if event.code in codes and event.direction == direction
        ]

        if not selected:
            return []

        opposing_codes = (
            self._BEARISH_CODES
            if direction == EvidenceDirection.BULLISH
            else self._BULLISH_CODES
        )

        opposing = [
            event
            for event in events
            if event.code in opposing_codes
        ]

        # A later opposing structural event invalidates the previous
        # sequence. Only events after the latest opposing event can form
        # the currently valid persistent sequence.
        if opposing:
            latest_opposing_bar = opposing[-1].bar_index
            selected = [
                event
                for event in selected
                if event.bar_index > latest_opposing_bar
            ]

        if not selected:
            return []

        qualifying = [selected[-1]]

        for event in reversed(selected[:-1]):
            if (
                qualifying[0].bar_index - event.bar_index
                < self.MIN_EVENT_SPACING_BARS
            ):
                continue

            qualifying.append(event)
            if len(qualifying) >= self.MIN_QUALIFYING_EVENTS:
                break

        qualifying.reverse()

        if len(qualifying) < self.MIN_QUALIFYING_EVENTS:
            return []

        return qualifying
