# Progression Shadow Replay Dataset

## Purpose

K26 converts validated K24 shadow semantic projections into replay-ready weekly
windows for later dev-only visual review.

K26 does not modify the K25 frontend route.

## Input

Frozen K24 artifacts:

    progression_shadow_semantic_summary.json
    progression_shadow_semantic_rows.csv

Weekly OHLCV comes from the existing local cache through the standard completed
daily -> completed weekly path.

Unless --refresh is explicitly supplied, the cache is treated as frozen.

## Stable event identity

K24 source event_bar_index is provenance only.

K26 resolves every event by exact event_week against the local completed-weekly
history. This keeps the dataset portable when local cache history lengths differ.

## Replay window

Default:

    4 weekly bars before event
    event bar
    4 weekly bars after event

Each sequence contains exactly one semantic marker, on the resolved event bar.

Non-event frames carry no semantic role or projected transition direction.

## Safety

Every frame preserves:

    reversal_confirmed = false
    persistent_direction_claim = false
    affects_qualification = false
    affects_scoring = false
    is_actionable = false

K26 is dataset generation only. It changes no scanner state, qualification,
scoring, actionability, API response, frontend behavior, persistence, alerts, or
orders.

## Next stage

K27 may add a frontend adapter that consumes the generated JSON through the
existing dev-only progression replay route.
