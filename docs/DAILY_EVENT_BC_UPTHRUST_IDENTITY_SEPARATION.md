# M12 / L15 — BUYING_CLIMAX vs UPTHRUST Identity Separation

## Purpose

Canonical M12 L2 established that:

    BUYING_CLIMAX
    and
    UPTHRUST

have exactly the same daily firing set.

Canonical frozen counts:

    BUYING_CLIMAX     4,497
    UPTHRUST          4,497
    overlap           4,497

    relationship      IDENTICAL_FIRING_SET

L15 explains why and applies exactly one narrow counterfactual separation.

No new market-data replay is required.

No production detector is changed.

## Root cause in production code

The two detectors have the same mandatory contract.

Both require:

    Buying Campaign
    Bullish Bar
    Very High Volume
    Above Average Spread

Production `evaluate_detector()` emits after mandatory requirements pass.

It calculates confirmation count but does not gate emission on that result.

Therefore two detectors with the same mandatory requirements will emit on the
same bars even when their confirmations differ.

This makes the canonical L2 identity a structural consequence of the code.

It is not merely an accidental historical correlation.

## Confirmation contracts

The detectors share two confirmations:

    Wide Spread
    Weak Close

The third confirmation differs.

BUYING_CLIMAX:

    Increasing Volume

UPTHRUST:

    Lower Close Than Previous

Canonical L4B previously measured approximate clause pass rates:

BUYING_CLIMAX:

    Wide Spread             ~65.04%
    Weak Close               ~3.96%
    Increasing Volume       ~73.98%

UPTHRUST:

    Wide Spread             ~65.04%
    Weak Close               ~3.96%
    Lower Close Previous     ~3.94%

L15 does not choose a global confirmation threshold.

## Single counterfactual

The only counterfactual tested in L15 is:

    BUYING_CLIMAX candidate
        current mandatory contract
        AND Increasing Volume

    UPTHRUST candidate
        current mandatory contract
        AND Lower Close Than Previous

The two shared confirmations remain descriptive.

No other combinations are tested.

In particular L15 does NOT test:

    Wide Spread AND Weak Close
    Weak Close AND unique clause
    all three confirmations
    majority confirmation
    new spread threshold
    new close threshold
    new volume threshold

Those would be separate hypotheses and would violate the new detector stopping
discipline if introduced before the narrow unique-clause question is answered.

## Why this counterfactual

If two named detectors are intended to describe different bar semantics, the
most conservative existing distinction is the clause that already differs in
their source contracts.

Therefore L15 first asks:

    Are the existing unique clauses sufficient to create meaningfully
    different event populations?

It does not assume that either unique clause is the final correct VSA
definition.

## Frozen source

L15 consumes the canonical L3 confirmation-counterfactual directory:

    reports\daily-events\confirmation-counterfactual\
      milestone6_standard_india_large_cap_30_frozen_2026-09-18

Required canonical conditions include:

    requested symbols          30
    failed symbols              0
    identity mismatches         0
    bar-index mismatches        0
    is_actionable           false

L15 also introspects the current production detector source through the existing
L4B contract extractor.

## Hard gates

L15 fails closed if the production source no longer matches:

Mandatory contract for both:

    Buying Campaign
    Bullish Bar
    Very High Volume
    Above Average Spread

BUYING_CLIMAX confirmations:

    Wide Spread
    Weak Close
    Increasing Volume

UPTHRUST confirmations:

    Wide Spread
    Weak Close
    Lower Close Than Previous

It also requires the canonical baseline identity collision to remain exact:

    BUYING_CLIMAX events       4,497
    UPTHRUST events            4,497
    baseline firing sets       identical

If these conditions change, the old research question is stale and L15 should
not silently continue.

## Four-way identity partition

Every one of the 4,497 shared baseline bars is classified into exactly one
partition:

    BC_UNIQUE_ONLY
        Increasing Volume passes
        Lower Close Than Previous fails

    UT_UNIQUE_ONLY
        Lower Close Than Previous passes
        Increasing Volume fails

    BOTH_UNIQUE
        both unique confirmations pass

    NEITHER_UNIQUE
        neither unique confirmation passes

This directly shows whether the source-level differentiators actually separate
the bars.

## Separation metrics

L15 reports:

    BUYING_CLIMAX unique-gate event count
    BUYING_CLIMAX survival rate

    UPTHRUST unique-gate event count
    UPTHRUST survival rate

    unique-gate overlap count
    unique-gate union count
    unique-gate Jaccard

    whether unique-gated firing sets remain identical

It also reports all four partition counts and per-symbol coverage.

## Important interpretation boundary

A successful separation is NOT enough to change production.

For example:

    BUYING_CLIMAX unique gate survives 70%
    UPTHRUST unique gate survives 4%
    overlap becomes small

would prove that the clauses separate the labels.

It would not prove that:

    Increasing Volume

is the correct mandatory semantic for Buying Climax or that:

    Lower Close Than Previous

is the correct mandatory semantic for Upthrust.

Outcome value and VSA concept validity are separate questions.

## Stop rule

L15 is deliberately bounded.

After canonical results, use this decision tree.

### Outcome A — unique gates still substantially collapse together

If the two candidate sets remain highly overlapping or effectively identical:

    REJECT this separation hypothesis.

Do not add more confirmation combinations in the same research thread.

The pair should move to first-principles semantic redesign.

### Outcome B — one unique gate collapses to a tiny / narrow population

If one label is separated only by removing almost the entire baseline
population:

    PARK that candidate.

Do not immediately loosen the gate by testing many combinations.

A first-principles semantic definition should come before another empirical
threshold search.

### Outcome C — unique gates create distinct, sufficiently represented sets

Then exactly one additional validation stage is allowed:

    one robustness / outcome comparison

using the frozen population.

After that stage the decision must be:

    PROMOTE
    REJECT
    or
    PARK

No third layer of subgroup discovery is allowed without new independent
evidence.

## Why this stopping rule matters

The purpose of M12 is not to optimize each named detector until it produces a
historically attractive subgroup.

The purpose is to make the detector vocabulary:

    mechanically correct
    semantically interpretable
    meaningfully distinct

so higher-level supply/demand sequence reasoning can use it without duplicated
or misleading evidence.

## Outputs

    daily_bc_upthrust_identity_summary.json
    daily_bc_upthrust_identity_partitions.csv
    daily_bc_upthrust_identity_symbols.csv
    daily_bc_upthrust_identity_rows.csv

The identity ledger contains all 4,497 baseline bars with:

    symbol
    bar index
    session
    BUYING_CLIMAX unique confirmation passed
    UPTHRUST unique confirmation passed
    four-way partition

## Local validation

```powershell
python -m ruff check audit/daily_event_bc_upthrust_identity_separation.py scripts/audit_daily_event_bc_upthrust_identity_separation.py tests/test_daily_event_bc_upthrust_identity_separation.py
```

```powershell
python -m pytest -q tests/test_daily_event_bc_upthrust_identity_separation.py tests/test_daily_event_confirmation_semantics.py tests/test_daily_event_confirmation_counterfactual.py
```

## Canonical run

```powershell
python scripts/audit_daily_event_bc_upthrust_identity_separation.py --input-dir reports\daily-events\confirmation-counterfactual\milestone6_standard_india_large_cap_30_frozen_2026-09-18
```

Default output:

    reports\daily-events\bc-upthrust-identity-separation\
      milestone6_standard_india_large_cap_30_frozen_2026-09-18

## Safety

L15 changes no:

- BUYING_CLIMAX production requirements;
- UPTHRUST production requirements;
- confirmation gating;
- Evidence emission;
- detector weights;
- professional supply score;
- scanner ranking;
- DailyBehavior;
- weekly thesis;
- qualification/actionability;
- API behavior;
- alerts/orders;
- production market-data loading.
