# HIDDEN_SUPPLY Audit Record

## Current Status

`HIDDEN_SUPPLY` is **audit-complete / non-scoring** and remains outside the production evidence path.

No production collector, registry, or score mutation was added from this audit campaign.

## Candidate Definition

The current production semantic definition was audited point-in-time:

1. Up bar.
2. High / very-high / ultra-high volume.
3. Lower close or close on the low.

The production collector implements this definition directly in `evidence/supply.py::_collect_hidden_supply`.

## Candidate Audit

Across 8 symbols:

- candidate events: `139`
- positive outcomes: `82`
- negative outcomes: `57`
- flat outcomes: `0`
- decisive outcomes: `139`
- positive decisive rate: `58.99%`
- mean 8-bar return: `+2.78%`
- audit failures: `0`

## Semantic-Quality Audit

Across the 139 candidate events:

- high volume: `139 / 139`
- very-high volume: `60 / 139`
- lower close: `137 / 139`
- close on low: `2 / 139`
- semantic failures: `0`

The candidate population therefore reproduces the intended production semantics exactly.

## Interaction / Contradiction Audit

The first interaction audit incorrectly counted `HIDDEN_SUPPLY` against itself. That was rejected as a false self-conflict.

After correcting the classifier so the target event is excluded from its own conflict set:

- events: `139`
- supply-conflict events: `0`
- supply-conflict rate: `0.00%`
- `SUPPLY_COMING_IN_LIKE`: `0`
- `INCREASING_SUPPLY_LIKE`: `0`
- `UPTHRUST_LIKE`: `0`
- `NO_DEMAND_LIKE`: `0`
- `BUYING_CLIMAX_LIKE`: `0`
- demand interactions: `0`
- self-conflict excluded: `YES`

No empirical conflict penalty or rejection rule was established.

## Decision-Value Audit

Candidate population:

- events: `139`
- positive decisive rate: `58.99%`
- mean 8-bar return: `+2.78%`

Eligible-market baseline from the same 8-symbol universe:

- events: `11,353`
- positive decisive rate: `60.80%`
- mean 8-bar return: `+3.83%`

Observed lift:

```text
positive decisive rate lift = -1.81 percentage points
mean return lift             = -1.05 percentage points
candidate share              = 1.22% of eligible events
```

The candidate population does not demonstrate incremental decision value over the eligible-market baseline.

Synthetic weight tests (`0.00`, `0.25`, `0.30`, `0.38`, `0.45`, `0.50`) therefore do not justify assigning positive production ranking weight to the current `HIDDEN_SUPPLY` definition.

## Frozen Decision

```text
HIDDEN_SUPPLY = 0.00
conflict_penalty = 0.00
rejection = NO
status = AUDIT_COMPLETE / NON_SCORING
production_path = NO
```

This is **not a rejection of the VSA concept**. It is a decision not to promote the current detector definition into scoring because the audited population does not demonstrate incremental decision value over the eligible-market baseline.

A future revision to `HIDDEN_SUPPLY` semantics would require a fresh audit cycle rather than inheriting this decision automatically.
