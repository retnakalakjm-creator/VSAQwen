from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Iterable

from qualification_lifecycle_labels import CurrentVSABias, QualificationLifecycleLabel
from vsa_absorption_background_labels import (
    ABSORPTION_BACKGROUND_FRONTEND_LABEL,
    ABSORPTION_BACKGROUND_PLAIN_ENGLISH,
    AbsorptionBackgroundReviewLabel,
)
from vsa_recovery_sequence_labels import RecoverySequenceReviewLabel


class LegendFamily(StrEnum):
    """Frontend-readable groups for ProVSA legend explanations."""

    LIFECYCLE = "lifecycle"
    LIFECYCLE_FLAG = "lifecycle_flag"
    CURRENT_BIAS = "current_vsa_bias"
    OUTCOME = "outcome_label"
    REVIEW_REASON = "review_reason"
    CLUSTER = "cluster"
    TRANSITION = "transition"
    CASE_TYPE = "case_type"
    REVIEW_MARKER = "review_marker"
    RECOMMENDED_ACTION = "recommended_action"
    EVIDENCE_CODE = "evidence_code"


@dataclass(frozen=True, slots=True)
class PlainEnglishLegend:
    """JSON-ready plain-English explanation for one internal legend code."""

    code: str
    family: LegendFamily
    frontend_label: str
    plain_english: str
    chronological_stage: str
    chart_reading_order: int
    chart_reading_role: str
    example_read: str
    user_action: str
    audit_only: bool = False
    production_safe: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "family": self.family.value,
            "frontend_label": self.frontend_label,
            "plain_english": self.plain_english,
            "chronological_stage": self.chronological_stage,
            "chart_reading_order": self.chart_reading_order,
            "chart_reading_role": self.chart_reading_role,
            "example_read": self.example_read,
            "user_action": self.user_action,
            "audit_only": self.audit_only,
            "production_safe": self.production_safe,
        }


FIELD_FAMILY_ALIASES: dict[str, LegendFamily] = {
    "_outcome_label": LegendFamily.OUTCOME,
    "outcome_label": LegendFamily.OUTCOME,
    "label_firing_outcome": LegendFamily.OUTCOME,
    "_review_reason": LegendFamily.REVIEW_REASON,
    "review_reason": LegendFamily.REVIEW_REASON,
    "reason": LegendFamily.REVIEW_REASON,
    "_classify_cluster": LegendFamily.CLUSTER,
    "classify_cluster": LegendFamily.CLUSTER,
    "cluster_classification": LegendFamily.CLUSTER,
    "_classify_transition": LegendFamily.TRANSITION,
    "classify_transition": LegendFamily.TRANSITION,
    "transition": LegendFamily.TRANSITION,
    "_case_type_for_transition": LegendFamily.CASE_TYPE,
    "case_type_for_transition": LegendFamily.CASE_TYPE,
    "case_type": LegendFamily.CASE_TYPE,
    "lifecycle_status": LegendFamily.LIFECYCLE,
    "status": LegendFamily.LIFECYCLE,
    "review_marker": LegendFamily.REVIEW_MARKER,
    "current_vsa_bias": LegendFamily.CURRENT_BIAS,
    "recommended_casebook_action": LegendFamily.RECOMMENDED_ACTION,
}


CHRONOLOGICAL_READING_CYCLE: tuple[dict[str, Any], ...] = (
    {"order": 1, "stage": "background_mood", "family": LegendFamily.LIFECYCLE.value, "plain_english": "First read the stock's existing background mood: active, conflicted, expired, invalidated, or under supersession review."},
    {"order": 2, "stage": "event_outcome", "family": LegendFamily.OUTCOME.value, "plain_english": "Then ask what happened after the event fired: did later bars confirm it, reject it, or leave it unresolved?"},
    {"order": 3, "stage": "review_reason", "family": LegendFamily.REVIEW_REASON.value, "plain_english": "Next read why the system wants review: missing context, missing follow-through, blockers, diagnostic-only evidence, or a clean candidate."},
    {"order": 4, "stage": "cluster_story", "family": LegendFamily.CLUSTER.value, "plain_english": "Then read nearby events as a group. One candle is a word; a cluster is a sentence."},
    {"order": 5, "stage": "lifecycle_transition", "family": LegendFamily.TRANSITION.value, "plain_english": "Then decide whether the cluster merely explains the chart or challenges the whole lifecycle background."},
    {"order": 6, "stage": "casebook_task", "family": LegendFamily.CASE_TYPE.value, "plain_english": "Then convert the transition or marker into a casebook task for manual chart review."},
    {"order": 7, "stage": "review_marker", "family": LegendFamily.REVIEW_MARKER.value, "plain_english": "Finally read the marker as a chart-review instruction, not as a buy or sell signal."},
)


_STAGE_BY_ORDER = {
    1: "background_mood",
    2: "event_outcome",
    3: "review_reason",
    4: "cluster_story",
    5: "lifecycle_transition",
    6: "casebook_task",
    7: "review_marker",
}


_ROLE_BY_ORDER = {
    1: "Read the background before judging any single event.",
    2: "Read what happened after an event fired.",
    3: "Read why the event or case needs review.",
    4: "Read nearby candles as one chart story.",
    5: "Read whether the cluster challenges the lifecycle background.",
    6: "Read the resulting manual casebook task.",
    7: "Read the final marker as review guidance, not a trading signal.",
}


def build_plain_english_legend_registry() -> tuple[PlainEnglishLegend, ...]:
    """Return the shared plain-English legend registry.

    The registry is read-only. It does not load market data, call providers,
    replay scanners, mutate scanner state, activate detectors, alter scoring or
    ranking, write persistence, or touch API/frontend behavior.
    """

    rows = [
        # Lifecycle status.
        (QualificationLifecycleLabel.UNQUALIFIED.value, LegendFamily.LIFECYCLE, "Unqualified", "No persistent bullish or bearish background is active yet.", 1, "XYZ has no persistent background, so new events should be read as isolated evidence first.", "Wait for a cleaner background or a later casebook setup."),
        (QualificationLifecycleLabel.ACTIVE.value, LegendFamily.LIFECYCLE, "Active", "The existing background mood is still supported by fresh same-side evidence.", 1, "XYZ is persistent bearish and fresh increasing supply appears, so the downtrend story is still valid.", "Respect the existing background until opposing evidence becomes strong enough."),
        (QualificationLifecycleLabel.CONFLICTED.value, LegendFamily.LIFECYCLE, "Conflicted", "The background is being challenged by opposite evidence, but it is not safely replaced yet.", 1, "XYZ is persistent bearish, but fresh demand appears before the bearish state is formally replaced.", "Use chart review; do not auto-flip the stock bullish or bearish."),
        (QualificationLifecycleLabel.SUPERSESSION_REVIEW.value, LegendFamily.LIFECYCLE, "Supersession Review", "Newer evidence may be strong enough to replace the old lifecycle background, but manual confirmation is still required.", 1, "XYZ was persistent bearish, but repeated demand/reversal evidence now deserves review as a possible background replacement.", "Review the chart before promoting a stricter supersession rule."),
        (QualificationLifecycleLabel.INVALIDATED.value, LegendFamily.LIFECYCLE, "Invalidated", "The old background is contradicted by fresh opposite evidence without enough same-side support.", 1, "XYZ was persistent bearish, but fresh bullish VSA evidence appears without fresh bearish support.", "Treat the old background as unreliable for this case."),
        (QualificationLifecycleLabel.EXPIRED.value, LegendFamily.LIFECYCLE, "Expired", "The old background lacks fresh confirmation and should not be trusted as current evidence.", 1, "XYZ had an older bearish label, but no recent supply evidence keeps it alive.", "Wait for fresh evidence before relying on the old label."),
        (QualificationLifecycleLabel.NEEDS_FOLLOW_THROUGH.value, LegendFamily.LIFECYCLE, "Needs Follow-Through", "A challenge exists, but the evidence is stale, fallback-only, or not fresh enough to trust yet.", 1, "XYZ shows an opposite clue, but it comes from stale or fallback evidence.", "Wait for fresh non-fallback confirmation."),
        # Lifecycle flags.
        ("pending_supersession", LegendFamily.LIFECYCLE_FLAG, "Pending Supersession", "The old bearish background is under serious challenge, but the system is not allowed to replace it automatically.", 1, "XYZ is persistent bearish, but stopping volume and demand start appearing near the lows.", "Review the chart; do not treat it as an automatic bullish flip."),
        ("supersession_review_confirmed", LegendFamily.LIFECYCLE_FLAG, "Supersession Review Confirmed", "Manual chart review has confirmed that the newer evidence deserves supersession review.", 1, "XYZ's demand/reversal evidence has been chart-confirmed as a serious challenge to the old bearish state.", "Allow review-only supersession handling; still avoid automatic bullish flipping."),
        ("supersession_review_blocked", LegendFamily.LIFECYCLE_FLAG, "Supersession Review Blocked", "A possible supersession is blocked because important conflict or supply evidence remains.", 1, "XYZ has demand, but hidden supply is still active in the same review window.", "Keep the case in review until blockers clear."),
        # Current bias.
        (CurrentVSABias.NONE.value, LegendFamily.CURRENT_BIAS, "No Current VSA Bias", "No fresh VSA evidence is selected for the current row.", 1, "XYZ has no current VSA code selected this week.", "Do not infer direction from this row alone."),
        (CurrentVSABias.BULLISH.value, LegendFamily.CURRENT_BIAS, "Bullish Current VSA Bias", "Fresh selected VSA evidence leans toward demand or reversal.", 1, "XYZ prints demand_coming_in after a decline.", "Compare it with the older background before changing interpretation."),
        (CurrentVSABias.BEARISH.value, LegendFamily.CURRENT_BIAS, "Bearish Current VSA Bias", "Fresh selected VSA evidence leans toward supply or weakness.", 1, "XYZ prints increasing_supply during a downtrend.", "Check whether it supports or contradicts the lifecycle background."),
        (CurrentVSABias.MIXED.value, LegendFamily.CURRENT_BIAS, "Mixed Current VSA Bias", "Fresh selected evidence contains both demand-side and supply-side clues.", 1, "XYZ shows demand_coming_in and hidden_supply in the same review area.", "Use manual review; do not simplify it into one direction."),
        # Outcome labels.
        ("follow_through", LegendFamily.OUTCOME, "Follow-Through", "Later bars supported the original event.", 2, "XYZ fires increasing_supply and later bars continue weakening.", "Treat the event as confirmed by later evidence."),
        ("invalidated", LegendFamily.OUTCOME, "Invalidated", "Later bars contradicted the original event.", 2, "XYZ fires increasing_supply, but later demand and reversal evidence reject the weakness story.", "Do not rely on the original event without review."),
        ("mixed_conflict", LegendFamily.OUTCOME, "Mixed Conflict", "Later bars show both confirming and opposing evidence.", 2, "XYZ shows supply first, then both demand and hidden supply appear nearby.", "Read it as conflict, not as a clean signal."),
        ("lifecycle_transition", LegendFamily.OUTCOME, "Lifecycle Transition", "The event may be important enough to challenge the larger background state.", 2, "XYZ was persistent bearish, but stopping volume and demand appear after weakness.", "Move from event reading into transition review."),
        ("pending_insufficient", LegendFamily.OUTCOME, "Pending / Insufficient", "There are not enough later bars to judge the event yet.", 2, "XYZ fires a candidate this week, but there are no later candles yet.", "Wait for more bars before deciding."),
        ("no_later_selected", LegendFamily.OUTCOME, "No Later Event Selected", "No useful later event was selected for comparison.", 2, "XYZ has a candidate event, but the later window has no selected VSA event.", "Treat the outcome as unresolved."),
        ("fired", LegendFamily.OUTCOME, "Fired", "The review-only label requirements were satisfied for this saved row or case.", 2, "XYZ has the full review-only sequence and no blocker.", "Send it to chart review; do not auto-trade it."),
        ("not_fired", LegendFamily.OUTCOME, "Not Fired", "The saved row or case did not satisfy the review-only label requirements.", 2, "XYZ has diagnostic hints but lacks the required production sequence.", "Leave it as context only."),
        ("blocked", LegendFamily.OUTCOME, "Blocked", "The required evidence exists, but opposing same-window evidence prevents a clean marker.", 2, "XYZ has absorption and demand, but hidden_supply is still present.", "Review blockers before trusting the setup."),
        ("needs_follow_through", LegendFamily.OUTCOME, "Needs Follow-Through", "The setup has early evidence but still needs fresh non-fallback confirmation.", 2, "XYZ has stopping volume but no fresh demand yet.", "Wait for fresh follow-through."),
        # Review reasons.
        ("missing_prior_context", LegendFamily.REVIEW_REASON, "Missing Prior Context", "The setup lacks the earlier weakness or supply background required for this reading.", 3, "XYZ has demand, but no prior weakness was detected.", "Do not mark recovery without a prior problem to recover from."),
        ("missing_anchor", LegendFamily.REVIEW_REASON, "Missing Anchor", "Prior weakness exists, but there is no stopping-volume or absorption anchor.", 3, "XYZ was weak, but no stopping_volume or supply_absorption appears.", "Wait for a valid anchor."),
        ("missing_test", LegendFamily.REVIEW_REASON, "Missing Test", "An anchor exists, but no later Spring or Shakeout test is present.", 3, "XYZ has stopping volume, but no spring or shakeout follows.", "Keep it as incomplete recovery context."),
        ("missing_follow_through", LegendFamily.REVIEW_REASON, "Missing Follow-Through", "The setup has early ingredients but lacks fresh demand or reversal confirmation.", 3, "XYZ has absorption but no later demand_coming_in or increasing_demand.", "Wait for fresh confirmation."),
        ("fallback_or_stale_follow_through", LegendFamily.REVIEW_REASON, "Fallback or Stale Follow-Through", "The follow-through exists but is fallback-only or too old to trust.", 3, "XYZ has older demand evidence, but it is outside the actionable window.", "Require fresh non-fallback evidence."),
        ("blocked_by_same_window_supply", LegendFamily.REVIEW_REASON, "Blocked by Same-Window Supply", "Supply or structural weakness appears in the same window and blocks a clean review marker.", 3, "XYZ shows absorption and demand, but hidden_supply appears on the seed row.", "Review the blocker before trusting recovery."),
        ("diagnostic_only", LegendFamily.REVIEW_REASON, "Diagnostic Only", "The row has audit or diagnostic hints, but they are not production evidence.", 3, "XYZ has review_potential_absorption but no production supply_absorption code.", "Use it as review context only."),
        ("clean_review_candidate", LegendFamily.REVIEW_REASON, "Clean Review Candidate", "The required evidence is present and no blocker prevents a review-only marker.", 3, "XYZ has prior weakness, absorption, fresh demand, and no same-window supply blocker.", "Send the chart to manual review; do not auto-flip bullish."),
        # Cluster classifications.
        ("detector_gate_noise", LegendFamily.CLUSTER, "Detector Gate Noise", "The grouped events are too noisy or weak to form a reliable chart story.", 4, "XYZ has scattered audit hints without a stable production pattern.", "Ignore as a major lifecycle clue for now."),
        ("overlapping_event_conflict", LegendFamily.CLUSTER, "Overlapping Event Conflict", "Bullish and bearish clues overlap in the same area.", 4, "XYZ has demand_coming_in and hidden_supply in the same cluster.", "Use manual review; do not force one-sided meaning."),
        ("possible_lifecycle_transition", LegendFamily.CLUSTER, "Possible Lifecycle Transition", "The event cluster may be strong enough to challenge the background mood.", 4, "XYZ shows stopping volume, reversal demand, and fading supply after a bearish background.", "Check transition classification next."),
        ("manual_chart_review", LegendFamily.CLUSTER, "Manual Chart Review", "The cluster is meaningful but needs human chart reading before promotion.", 4, "XYZ has several important reversal clues but not enough rule certainty.", "Open the chart and review the full sequence."),
        # Transition classifications.
        ("no_transition", LegendFamily.TRANSITION, "No Transition", "The cluster does not change the larger lifecycle story.", 5, "XYZ has a one-off demand bar but the bearish background remains supported.", "Keep the existing lifecycle state."),
        ("chart_review_conflict_before_invalidation_or_supersession", LegendFamily.TRANSITION, "Review Conflict Before Invalidation or Supersession", "The background is challenged, but the chart must be reviewed before invalidating or replacing it.", 5, "XYZ is bearish, but new demand appears while supply conflict remains.", "Review the chart before any lifecycle promotion."),
        ("chart_confirm_supersession_rule_candidate", LegendFamily.TRANSITION, "Chart-Confirm Supersession Rule Candidate", "The chart may justify a future rule that replaces the old background, but it still requires confirmation.", 5, "XYZ has repeated demand/reversal evidence after a persistent bearish background.", "Treat as a rule-review candidate, not an automatic flip."),
        # Transition case types and casebook case types.
        ("chart_review_conflict_before_invalidation_or_supersession", LegendFamily.CASE_TYPE, "Review Conflict Before Invalidation or Supersession", "Create a casebook review before invalidating or superseding the old lifecycle state.", 6, "XYZ is conflicted because demand is rising while supply has not fully cleared.", "Review the chart before changing lifecycle rules."),
        ("chart_confirm_supersession_rule_candidate", LegendFamily.CASE_TYPE, "Chart-Confirm Supersession Rule Candidate", "Create a casebook task to confirm whether newer evidence should supersede the old background.", 6, "XYZ may no longer deserve its old bearish lifecycle state.", "Review as a future supersession-rule candidate, not as an automatic flip."),
        ("recovery_sequence_review", LegendFamily.CASE_TYPE, "Recovery Sequence Review", "6C found a review-only Stopping Volume -> Spring/Shakeout -> demand follow-through sequence.", 6, "XYZ has prior weakness, stopping volume, spring/shakeout, and demand follow-through.", "Review the chart; do not auto-buy."),
        ("recovery_sequence_blocked", LegendFamily.CASE_TYPE, "Recovery Sequence Blocked", "6C found sequence evidence, but same-window supply or weakness blocks a clean review marker.", 6, "XYZ has a recovery sequence but hidden_supply remains in the review window.", "Inspect blockers before trusting recovery."),
        ("recovery_sequence_needs_follow_through", LegendFamily.CASE_TYPE, "Recovery Sequence Needs Follow-Through", "6C has early sequence ingredients but still needs fresh demand confirmation.", 6, "XYZ has stopping volume and spring but no fresh demand follow-through.", "Wait for non-fallback follow-through."),
        ("recovery_sequence_none", LegendFamily.CASE_TYPE, "No Recovery Sequence Case", "6C did not find enough evidence for a recovery-sequence casebook action.", 6, "XYZ has hints but not the full required sequence.", "Leave it as context only."),
        ("absorption_background_review", LegendFamily.CASE_TYPE, ABSORPTION_BACKGROUND_FRONTEND_LABEL, ABSORPTION_BACKGROUND_PLAIN_ENGLISH, 6, "XYZ is bearish, selling pressure gets absorbed, and fresh demand follows.", "Review the chart; this is not a confirmed bullish reversal."),
        ("absorption_background_blocked", LegendFamily.CASE_TYPE, "Absorption Background Blocked", "Absorption-style evidence exists, but same-window supply or weakness blocks a clean review marker.", 6, "XYZ has supply_absorption and demand, but hidden_supply remains active.", "Review blockers before trusting the setup."),
        ("absorption_background_needs_follow_through", LegendFamily.CASE_TYPE, "Absorption Background Needs Follow-Through", "Absorption-style evidence exists, but fresh demand or reversal follow-through is missing.", 6, "XYZ has stopping volume but no later demand_coming_in.", "Wait for fresh non-fallback follow-through."),
        ("absorption_background_none", LegendFamily.CASE_TYPE, "No Absorption Background Case", "6D did not find enough production evidence for an absorption-background casebook action.", 6, "XYZ has review_potential_absorption but no production absorption code.", "Leave diagnostic hints as context only."),
        # Review markers. Keep `none` once because 6C and 6D share that same marker code.
        (RecoverySequenceReviewLabel.REVIEW.value, LegendFamily.REVIEW_MARKER, "Stopping Volume / Spring-Shakeout Review", "6C found prior weakness, a stopping-volume anchor, a Spring/Shakeout test, and fresh demand follow-through.", 7, "XYZ weakens, prints stopping volume, tests with a shakeout, then demand follows through.", "Send to chart review; do not auto-flip bullish.", True),
        (RecoverySequenceReviewLabel.BLOCKED.value, LegendFamily.REVIEW_MARKER, "Stopping Volume / Spring-Shakeout Blocked", "6C found much of the sequence, but supply or structural weakness blocks a clean marker.", 7, "XYZ has a shakeout and demand, but hidden_supply remains active.", "Review blockers before accepting the sequence.", True),
        (RecoverySequenceReviewLabel.NEEDS_FOLLOW_THROUGH.value, LegendFamily.REVIEW_MARKER, "Stopping Volume / Spring-Shakeout Needs Follow-Through", "6C has the setup but lacks fresh non-fallback demand follow-through.", 7, "XYZ has stopping volume and a spring, but demand has not followed through yet.", "Wait for fresh demand confirmation.", True),
        (RecoverySequenceReviewLabel.NONE.value, LegendFamily.REVIEW_MARKER, "No Review Marker", "This family did not produce a review marker for the current row or case.", 7, "XYZ has diagnostic hints but lacks the required production evidence.", "Do not promote this row.", True),
        (AbsorptionBackgroundReviewLabel.REVIEW.value, LegendFamily.REVIEW_MARKER, ABSORPTION_BACKGROUND_FRONTEND_LABEL, ABSORPTION_BACKGROUND_PLAIN_ENGLISH, 7, "XYZ is bearish, selling pressure is absorbed, and fresh demand/reversal follows.", "Review the chart; do not treat as confirmed bullish reversal.", True),
        (AbsorptionBackgroundReviewLabel.BLOCKED.value, LegendFamily.REVIEW_MARKER, "Absorption Background Blocked", "6D sees absorption-style evidence, but same-window supply or weakness blocks a clean marker.", 7, "XYZ has absorption and demand, but supply_coming_in still appears.", "Review blockers before trusting the setup.", True),
        (AbsorptionBackgroundReviewLabel.NEEDS_FOLLOW_THROUGH.value, LegendFamily.REVIEW_MARKER, "Absorption Background Needs Follow-Through", "6D sees absorption-style evidence but still needs fresh demand or reversal follow-through.", 7, "XYZ has supply_absorption but no later demand confirmation.", "Wait for fresh non-fallback confirmation.", True),
        # Recommended actions.
        ("chart_review_recovery_sequence_candidate", LegendFamily.RECOMMENDED_ACTION, "Review Recovery Sequence Candidate", "Open the chart and review whether the 6C sequence is real.", 6, "XYZ has a full recovery-sequence candidate.", "Review manually before rule promotion."),
        ("chart_review_recovery_sequence_blockers", LegendFamily.RECOMMENDED_ACTION, "Review Recovery Sequence Blockers", "Open the chart and inspect the supply or weakness evidence blocking the 6C setup.", 6, "XYZ has recovery clues but hidden_supply blocks the case.", "Resolve blockers before trusting it."),
        ("wait_for_recovery_sequence_follow_through", LegendFamily.RECOMMENDED_ACTION, "Wait for Recovery Follow-Through", "Do not mark the 6C setup clean until fresh demand follow-through appears.", 6, "XYZ has stopping volume and spring but no demand yet.", "Wait for fresh demand confirmation."),
        ("chart_review_absorption_background_candidate", LegendFamily.RECOMMENDED_ACTION, "Review Absorption Background Candidate", "Open the chart and review whether selling pressure is truly being absorbed.", 6, "XYZ has absorption plus fresh demand after supply pressure.", "Review manually; do not auto-flip bullish."),
        ("chart_review_absorption_background_blockers", LegendFamily.RECOMMENDED_ACTION, "Review Absorption Background Blockers", "Open the chart and inspect the supply or weakness evidence blocking the 6D setup.", 6, "XYZ has absorption but same-window hidden_supply remains.", "Resolve blockers before trusting it."),
        ("wait_for_absorption_background_follow_through", LegendFamily.RECOMMENDED_ACTION, "Wait for Absorption Follow-Through", "Do not mark the 6D setup clean until fresh demand or reversal follow-through appears.", 6, "XYZ has stopping volume but no fresh demand yet.", "Wait for confirmation."),
        ("no_recovery_sequence_casebook_action", LegendFamily.RECOMMENDED_ACTION, "No Recovery Sequence Action", "6C did not create a useful casebook action for this row.", 6, "XYZ lacks the required 6C sequence.", "Do not promote."),
        ("no_absorption_background_casebook_action", LegendFamily.RECOMMENDED_ACTION, "No Absorption Background Action", "6D did not create a useful casebook action for this row.", 6, "XYZ has diagnostic hints but no production absorption setup.", "Do not promote."),
        # Evidence codes.
        ("stopping_volume", LegendFamily.EVIDENCE_CODE, "Stopping Volume", "Selling pressure appears heavy, but the downside result may be slowing or being absorbed.", 2, "XYZ falls on heavy volume but does not continue collapsing afterward.", "Look for a later test and demand follow-through."),
        ("supply_absorption", LegendFamily.EVIDENCE_CODE, "Supply Absorption", "Supply is present, but the chart may be absorbing it instead of breaking down cleanly.", 2, "XYZ sees heavy selling pressure but downside progress weakens.", "Check for fresh demand/reversal follow-through."),
        ("spring", LegendFamily.EVIDENCE_CODE, "Spring", "Price tests below support or prior weakness and then recovers, suggesting supply may have been tested.", 2, "XYZ dips below the prior low and then reclaims it.", "Look for demand follow-through."),
        ("shakeout", LegendFamily.EVIDENCE_CODE, "Shakeout", "A sharp move shakes out weak holders and may test remaining supply.", 2, "XYZ sells off sharply, then demand appears.", "Look for follow-through before review promotion."),
        ("demand_coming_in", LegendFamily.EVIDENCE_CODE, "Demand Coming In", "Fresh demand appears and may challenge a bearish background.", 2, "XYZ prints a strong demand bar after weakness.", "Check whether supply blockers remain."),
        ("increasing_demand", LegendFamily.EVIDENCE_CODE, "Increasing Demand", "Demand is strengthening across the selected evidence window.", 2, "XYZ shows stronger demand after a test.", "Check freshness and blockers."),
        ("increasing_supply", LegendFamily.EVIDENCE_CODE, "Increasing Supply", "Selling pressure is increasing and may support a bearish background or block recovery.", 2, "XYZ keeps showing supply during a decline.", "Treat recovery clues cautiously."),
        ("hidden_supply", LegendFamily.EVIDENCE_CODE, "Hidden Supply", "Selling pressure may still be present even if price action looks stronger.", 2, "XYZ rallies, but hidden supply appears in the same window.", "Review carefully before trusting demand."),
        ("review_potential_absorption", LegendFamily.EVIDENCE_CODE, "Potential Absorption", "Audit diagnostics saw possible absorption, but this is not production evidence by itself.", 3, "XYZ has review_potential_absorption but no production supply_absorption code.", "Do not promote unless production evidence exists.", True),
        ("review_potential_spring_or_shakeout", LegendFamily.EVIDENCE_CODE, "Potential Spring or Shakeout", "Audit diagnostics saw a possible spring/shakeout, but this is not production evidence by itself.", 3, "XYZ looks like a possible shakeout, but no production shakeout code fired.", "Use as context only.", True),
        ("review_potential_stopping_volume", LegendFamily.EVIDENCE_CODE, "Potential Stopping Volume", "Audit diagnostics saw possible stopping volume, but this is not production evidence by itself.", 3, "XYZ may have stopping volume, but only a diagnostic hint is present.", "Use as context only.", True),
    ]
    return tuple(_legend(*row) for row in rows)


def legend_registry_payload() -> dict[str, Any]:
    """Return the full registry as a JSON-ready payload."""

    return {
        "production_safe": True,
        "chart_reading_cycle": chronological_reading_cycle(),
        "field_family_aliases": {key: value.value for key, value in sorted(FIELD_FAMILY_ALIASES.items())},
        "legends": [legend.to_dict() for legend in LEGEND_REGISTRY],
    }


def legend_registry_json(*, indent: int = 2) -> str:
    """Serialize the registry to JSON."""

    return json.dumps(legend_registry_payload(), indent=indent, sort_keys=True)


def chronological_reading_cycle() -> tuple[dict[str, Any], ...]:
    """Return the recommended chart-reading order for legend families."""

    return tuple(dict(item) for item in CHRONOLOGICAL_READING_CYCLE)


def family_for_field(field_name: str) -> LegendFamily | None:
    """Resolve a raw field/helper name to a legend family when known."""

    return FIELD_FAMILY_ALIASES.get(str(field_name).strip())


def get_plain_english_legend(code: Any, *, family: LegendFamily | str | None = None) -> PlainEnglishLegend | None:
    """Return the registered legend for a code, optionally scoped by family."""

    code_text = _code_text(code)
    if not code_text:
        return None
    if family is not None:
        return _REGISTRY_BY_FAMILY_CODE.get((_family_text(family), code_text))
    matches = _REGISTRY_BY_CODE.get(code_text, ())
    if not matches:
        return None
    return sorted(matches, key=lambda item: (item.chart_reading_order, item.family.value))[0]


def explain_legend(code: Any, *, family: LegendFamily | str | None = None) -> dict[str, Any]:
    """Return a JSON-ready explanation for a code with a safe fallback."""

    legend = get_plain_english_legend(code, family=family)
    if legend is not None:
        return legend.to_dict()
    code_text = _code_text(code)
    family_text = _family_text(family) if family is not None else "unknown"
    return {
        "code": code_text,
        "family": family_text,
        "frontend_label": _fallback_label(code_text),
        "plain_english": "No plain-English explanation has been registered for this legend yet.",
        "chronological_stage": "unknown",
        "chart_reading_order": 99,
        "chart_reading_role": "Unknown legend; add it to the shared registry before showing it without explanation.",
        "example_read": "No example is registered yet.",
        "user_action": "Add a registry entry before relying on this code in the frontend.",
        "audit_only": False,
        "production_safe": True,
    }


def explain_legend_for_field(field_name: str, code: Any) -> dict[str, Any]:
    """Explain a code by first resolving its field/helper family."""

    family = family_for_field(field_name)
    return explain_legend(code, family=family)


def explain_legend_codes(codes: Iterable[Any], *, family: LegendFamily | str | None = None) -> tuple[dict[str, Any], ...]:
    """Explain many codes in stable chart-reading order."""

    explanations = tuple(explain_legend(code, family=family) for code in codes)
    return tuple(sorted(explanations, key=lambda item: (int(item["chart_reading_order"]), str(item["family"]), str(item["code"]))))


def registry_by_family() -> dict[str, list[dict[str, Any]]]:
    """Group registry entries by family for frontend legend panels."""

    grouped: dict[str, list[dict[str, Any]]] = {}
    for legend in LEGEND_REGISTRY:
        grouped.setdefault(legend.family.value, []).append(legend.to_dict())
    for legends in grouped.values():
        legends.sort(key=lambda item: (int(item["chart_reading_order"]), str(item["frontend_label"]), str(item["code"])))
    return dict(sorted(grouped.items()))


def _legend(
    code: str,
    family: LegendFamily,
    frontend_label: str,
    plain_english: str,
    chart_reading_order: int,
    example_read: str,
    user_action: str,
    audit_only: bool = False,
    production_safe: bool = True,
) -> PlainEnglishLegend:
    return PlainEnglishLegend(
        code=code,
        family=family,
        frontend_label=frontend_label,
        plain_english=plain_english,
        chronological_stage=_STAGE_BY_ORDER[chart_reading_order],
        chart_reading_order=chart_reading_order,
        chart_reading_role=_ROLE_BY_ORDER[chart_reading_order],
        example_read=example_read,
        user_action=user_action,
        audit_only=audit_only,
        production_safe=production_safe,
    )


def _build_family_code_index(legends: Iterable[PlainEnglishLegend]) -> dict[tuple[str, str], PlainEnglishLegend]:
    index: dict[tuple[str, str], PlainEnglishLegend] = {}
    for legend in legends:
        key = (legend.family.value, legend.code)
        if key in index:
            raise ValueError(f"Duplicate legend entry for {key}")
        index[key] = legend
    return index


def _build_code_index(legends: Iterable[PlainEnglishLegend]) -> dict[str, tuple[PlainEnglishLegend, ...]]:
    grouped: dict[str, list[PlainEnglishLegend]] = {}
    for legend in legends:
        grouped.setdefault(legend.code, []).append(legend)
    return {key: tuple(value) for key, value in grouped.items()}


def _code_text(value: Any) -> str:
    if value is None:
        return ""
    enum_value = getattr(value, "value", None)
    if isinstance(enum_value, str):
        return enum_value
    return str(value).strip()


def _family_text(value: LegendFamily | str | None) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, LegendFamily):
        return value.value
    return str(value).strip()


def _fallback_label(code: str) -> str:
    return " ".join(part.capitalize() for part in code.replace("-", "_").split("_") if part) or "Unknown"


LEGEND_REGISTRY = build_plain_english_legend_registry()
_REGISTRY_BY_FAMILY_CODE = _build_family_code_index(LEGEND_REGISTRY)
_REGISTRY_BY_CODE = _build_code_index(LEGEND_REGISTRY)


__all__ = [
    "CHRONOLOGICAL_READING_CYCLE",
    "FIELD_FAMILY_ALIASES",
    "LEGEND_REGISTRY",
    "LegendFamily",
    "PlainEnglishLegend",
    "build_plain_english_legend_registry",
    "chronological_reading_cycle",
    "explain_legend",
    "explain_legend_codes",
    "explain_legend_for_field",
    "family_for_field",
    "get_plain_english_legend",
    "legend_registry_json",
    "legend_registry_payload",
    "registry_by_family",
]
