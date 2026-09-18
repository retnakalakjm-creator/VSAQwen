# Progression Directionality Semantics Audit

## Purpose

K14 tests whether the directional labels attached to professional structural
progression are semantically consistent across the existing standard audit
basket.

The current production mapping is:

    recent professional swing quality > older quality
    → STRUCTURAL_PROGRESSION_IMPROVING
    → bullish evidence

    recent professional swing quality < older quality
    → STRUCTURAL_PROGRESSION_WEAKENING
    → bearish evidence

K13 showed that the underlying professional score is a weighted significance /
quality score rather than an explicitly price-directional score.

K14 does not assume that mapping is wrong. It measures how often emitted
progression direction agrees or conflicts with independent same-bar context.

## Same-bar comparison dimensions

For every already-emitted progression event:

### Trend alignment

    trend up   + bullish event → aligned
    trend up   + bearish event → opposed
    trend down + bearish event → aligned
    trend down + bullish event → opposed
    trend range                → neutral

### Structural-pattern alignment

    pattern improving + bullish event → aligned
    pattern improving + bearish event → opposed
    pattern weakening + bearish event → aligned
    pattern weakening + bullish event → opposed
    stable / breaking / unknown       → ambiguous

These are diagnostic labels only. They do not replace the production event
direction.

## Basket

The CLI reuses the existing repeatable VSA audit baskets. Default:

    milestone6_standard_india_large_cap_30

A staged run can use --max-symbols before the full basket.

## Outputs

- progression_directionality_summary.json
- progression_directionality_events.csv
- progression_directionality_symbols.csv
- progression_directionality_failures.csv

Failures are isolated per symbol instead of discarding successful audit results.

## CLI

Full standard basket:

    python scripts/audit_progression_directionality_basket.py --now 2026-09-18T16:00:00+05:30

Staged first five symbols:

    python scripts/audit_progression_directionality_basket.py --now 2026-09-18T16:00:00+05:30 --max-symbols 5

## Safety

Read-only and explicitly non-actionable.

K14 does not change structural swing scoring, professional weights, progression
windows, progression thresholds, evidence direction, qualification, scanner
actionability, WeeklySetup materialization, coordinator behavior, daily signals,
alerts, execution, or orders.
