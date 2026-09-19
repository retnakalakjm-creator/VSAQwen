# Progression Shadow Semantic Replay Preview

## Purpose

K25 exposes K24's read-only progression semantic projection through a dev-only
offline replay surface.

It does not expose the projection through the production analysis API.

## Route

    /replay/progression-semantic

The route is enabled only when NODE_ENV is not production.

## Input

K25 uses committed synthetic weekly fixtures only.

No market data, scanner replay, cache, persisted state, or live API fetch is
used.

## Causal display

The replay is stepped one bar at a time.

Only bars up to the current replay cursor are rendered. A semantic marker is not
visible until the replay reaches its event bar.

This makes the preview suitable for verifying the visual meaning of:

    TRANSITION_WARNING
    ALIGNED_PROGRESSION_OBSERVATION
    NEUTRAL_PROGRESSION_OBSERVATION

without exposing future event markers early.

## Production boundary

The preview explicitly disables:

- live API fetch;
- production signals;
- scoring;
- ranking;
- actionability;
- qualification mutation;
- scanner state;
- persistence;
- alerts;
- orders.

Fixture rows also retain K24's explicit safety fields:

    reversal_confirmed = false
    persistent_direction_claim = false
    affects_qualification = false
    affects_scoring = false
    is_actionable = false

## Next stage

K25 is a visual-review surface only.

A later PR may adapt validated K24 artifact JSON into this replay surface, but
that must remain offline/shadow until separately promoted.
