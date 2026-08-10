from dataclasses import dataclass
from collections import defaultdict 
import config
from models import AggregatedEvidenceEvent, Direction, Evidence, EvidenceCode, EvidenceDirection, EvidenceSummary, MarketBias

class EvidenceAggregator:

    def aggregate(
    self,
    evidences: tuple[Evidence, ...],
    ) -> EvidenceSummary:

        grouped: dict[
            tuple[int, EvidenceDirection],
            list[Evidence],
        ] = defaultdict(list)

        for evidence in evidences:
            grouped[
                (
                    evidence.bar_index,
                    evidence.direction,
                )
            ].append(evidence)

        # --------------------------------------------------
        # Diagnostic
        # --------------------------------------------------

        aggregated_events: list[AggregatedEvidenceEvent] = []

        for (bar_index, direction), items in sorted(
            grouped.items()
        ):

            primary = tuple(
                item
                for item in items
                if item.code in config.PRIMARY_VSA_CODES
            )

            supporting = tuple(
                item
                for item in items
                if item.code in config.SUPPORTING_VSA_CODES
            )

            effort_result = tuple(
                item
                for item in items
                if item.code in config.EFFORT_RESULT_CODES
            )

            structural = tuple(
                item
                for item in items
                if item.code in config.STRUCTURAL_CODES
            )

            contribution = self._calculate_event_contribution(
                items
            )

            event = AggregatedEvidenceEvent(
                bar_index=bar_index,
                direction=direction,
                evidences=tuple(items),
                codes=tuple(item.code for item in items),
                primary_codes=tuple(
                    item.code for item in primary
                ),
                supporting_codes=tuple(
                    item.code for item in supporting
                ),
                effort_result_codes=tuple(
                    item.code for item in effort_result
                ),
                structural_codes=tuple(
                    item.code for item in structural
                ),
                contribution=contribution,
            )

            aggregated_events.append(event)

            print(
                "AGGREGATED EVENT",
                {
                    "bar_index": event.bar_index,
                    "direction": event.direction,
                    "codes": event.codes,
                    "primary": event.primary_codes,
                    "supporting": event.supporting_codes,
                    "effort_result": event.effort_result_codes,
                    "structural": event.structural_codes,
                    "contribution": event.contribution,
                },
            )
        
        # --------------------------------------------------
        # Counts
        # --------------------------------------------------

        bullish_events = [
            event
            for event in aggregated_events
            if event.direction == EvidenceDirection.BULLISH
        ]

        bearish_events = [
            event
            for event in aggregated_events
            if event.direction == EvidenceDirection.BEARISH
        ]

        bullish_score = sum(
            event.contribution
            for event in bullish_events
        )

        bearish_score = sum(
            event.contribution
            for event in bearish_events
        )

        net_score = (
            bullish_score
            - bearish_score
        )
        # --------------------------------------------------
        # Bias
        # --------------------------------------------------

        if net_score >= config.EVIDENCE_BIAS_THRESHOLD:
            bias = MarketBias.BULLISH

        elif net_score <= -config.EVIDENCE_BIAS_THRESHOLD:
            bias = MarketBias.BEARISH

        else:
            bias = MarketBias.NEUTRAL

        
        return EvidenceSummary(
            bullish=tuple(
                evidence
                for event in bullish_events
                for evidence in event.evidences
            ),
            bearish=tuple(
                evidence
                for event in bearish_events
                for evidence in event.evidences
            ),

            bullish_score=bullish_score,
            bearish_score=bearish_score,

            bullish_count=len(bullish_events),
            bearish_count=len(bearish_events),
            total_count=len(aggregated_events),

            net_score=net_score,

            bias=bias,
        )
        
    def _event_contribution(
        self,
        evidences: list[Evidence],
    ) -> float:

        contributions = [
            evidence.weight * evidence.strength
            for evidence in evidences
        ]

        base = max(contributions)

        codes = {
            evidence.code
            for evidence in evidences
        }

        primary = codes & config.PRIMARY_VSA_CODES
        supporting = codes & config.SUPPORTING_VSA_CODES
        structural = codes & config.STRUCTURAL_CODES

        # --------------------------------------------------
        # Primary + Primary
        # --------------------------------------------------

        if len(primary) >= 2:
            return min(
                base * config.COMBINED_PRIMARY_MULTIPLIER,
                config.MAX_COMBINED_EVENT_CONTRIBUTION,
            )

        # --------------------------------------------------
        # Primary + Supporting
        # --------------------------------------------------

        if primary and supporting:
            return min(
                base * config.PRIMARY_SUPPORTING_MULTIPLIER,
                config.MAX_COMBINED_EVENT_CONTRIBUTION,
            )

        # --------------------------------------------------
        # Primary + Structural
        # --------------------------------------------------

        if primary and structural:
            return min(
                base * config.PRIMARY_STRUCTURAL_MULTIPLIER,
                config.MAX_COMBINED_EVENT_CONTRIBUTION,
            )

        # --------------------------------------------------
        # Supporting + Supporting
        # --------------------------------------------------

        if len(supporting) >= 2:
            return min(
                base * config.COMBINED_SUPPORTING_MULTIPLIER,
                config.MAX_COMBINED_EVENT_CONTRIBUTION,
            )

        # --------------------------------------------------
        # Supporting + Structural
        # --------------------------------------------------

        if supporting and structural:
            return min(
                base * config.SUPPORTING_STRUCTURAL_MULTIPLIER,
                config.MAX_COMBINED_EVENT_CONTRIBUTION,
            )

        # --------------------------------------------------
        # Single evidence
        # --------------------------------------------------

        return base

    def _calculate_event_contribution(
        self,
        items: list[Evidence],
    ) -> float:

        primary = [
            item
            for item in items
            if item.code in config.PRIMARY_VSA_CODES
        ]

        supporting = [
            item
            for item in items
            if item.code in config.SUPPORTING_VSA_CODES
        ]

        effort_result = [
            item
            for item in items
            if item.code in config.EFFORT_RESULT_CODES
        ]

        structural = [
            item
            for item in items
            if item.code in config.STRUCTURAL_CODES
        ]

        # --------------------------------------------------
        # Primary event
        # --------------------------------------------------

        if primary:
            primary_contribution = max(
                item.weight * item.strength
                for item in primary
            )
        else:
            primary_contribution = 0.0

        # --------------------------------------------------
        # Supporting evidence
        # --------------------------------------------------

        supporting_contribution = 0.0

        if supporting:
            supporting_contribution = max(
                item.weight * item.strength
                for item in supporting
            )

        # --------------------------------------------------
        # Effort / result
        # --------------------------------------------------

        effort_result_contribution = 0.0

        if effort_result:
            effort_result_contribution = max(
                item.weight * item.strength
                for item in effort_result
            )

        # --------------------------------------------------
        # Structural context
        # --------------------------------------------------

        structural_contribution = 0.0

        if structural:
            structural_contribution = max(
                item.weight * item.strength
                for item in structural
            )

        # --------------------------------------------------
        # If a primary event exists, it is the anchor.
        # Other evidence modifies it rather than stacking
        # independently.
        # --------------------------------------------------

        if primary:

            contribution = primary_contribution

            if supporting:
                contribution += (
                    supporting_contribution
                    * config.PRIMARY_SUPPORTING_MODIFIER
                )

            if effort_result:
                contribution += (
                    effort_result_contribution
                    * config.PRIMARY_EFFORT_RESULT_MODIFIER
                )

            if structural:
                contribution += (
                    structural_contribution
                    * config.PRIMARY_STRUCTURAL_MODIFIER
                )

        else:

            # No primary event.
            # Supporting evidence can still contribute,
            # but at reduced influence.

            contribution = (
                supporting_contribution
                * config.SUPPORTING_BASE_WEIGHT
                + effort_result_contribution
                * config.EFFORT_RESULT_BASE_WEIGHT
                + structural_contribution
                * config.STRUCTURAL_BASE_WEIGHT
            )

        return contribution