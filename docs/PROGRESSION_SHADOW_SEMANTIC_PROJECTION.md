# Progression Shadow Semantic Projection

## Purpose

K24 introduces a read-only semantic projection for existing structural
progression evidence.

K13-K23 show that the production progression label should not be interpreted as a
symmetric persistent directional state:

- trend-opposed progression is the strongest transition/reversal-warning context;
- bullish-opposed warnings are especially early;
- many observed reversals later revert;
- trend-aligned progression is not a reliable continuation outperform signal.

K24 therefore changes no production semantics. It only adds a shadow descriptive
view.

## Projection contract

    trend alignment = opposed
    -> TRANSITION_WARNING

    trend alignment = aligned
    -> ALIGNED_PROGRESSION_OBSERVATION

    trend alignment = neutral
    -> NEUTRAL_PROGRESSION_OBSERVATION

    trend alignment = unknown
    -> UNKNOWN_TREND_CONTEXT_OBSERVATION

For TRANSITION_WARNING, projected_transition_direction preserves the original
progression event direction.

That field means only:

    direction toward which the transition warning points

It does not mean:

    reversal confirmed
    new persistent trend
    qualification direction
    trading signal

## Explicit safety fields

Every projected row contains:

    reversal_confirmed = false
    persistent_direction_claim = false
    affects_qualification = false
    affects_scoring = false
    is_actionable = false

K24 does not create state and cannot persist a warning into later bars.

## Frozen input

K24 consumes the validated K14 directionality artifacts:

    progression_directionality_events.csv
    progression_directionality_symbols.csv

No scanner replay or market-data access is required.

## Safety

K24 does not modify:

- production structural progression evidence;
- PatternQualificationEngine;
- qualification campaigns;
- scoring or ranking;
- ScannerCandidate actionability;
- WeeklySetup materialization;
- daily entry/replay;
- alerts or orders.

Any later integration must remain shadow-only until a separate promotion decision
is supported by evidence.
