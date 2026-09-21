# M12 / L16 — BUYING_CLIMAX vs UPTHRUST Semantic Design

## Status

Design-only.

This document defines the intended semantic distinction between:

    BUYING_CLIMAX
    UPTHRUST

after L15 proved that their current production contracts collapse to the same
4,497-event firing set.

No detector logic is changed here.

No historical outcome optimization is performed here.

No threshold is tuned here.

## Why L16 exists

Canonical M12 established:

    BUYING_CLIMAX events      4,497
    UPTHRUST events           4,497
    overlap                   4,497

Root cause:

    identical mandatory requirements
    + non-gating confirmations
    = identical production firing sets

L15 tested the smallest existing source distinction:

    BUYING_CLIMAX
        + Increasing Volume

    UPTHRUST
        + Lower Close Than Previous

Result:

    BUYING_CLIMAX candidate
        3,327 / 4,497
        73.98%

    UPTHRUST candidate
        177 / 4,497
        3.94%

    genuinely UPTHRUST-only
        56 / 4,497
        1.25%

Therefore:

    promoting the existing unique confirmations
    is rejected as the semantic repair.

The next step must begin from the intended VSA concepts rather than from
historical subgroup optimization.

## Design principle

The two labels should represent different information dimensions.

They may overlap on some bars.

They should not be forced to be mutually exclusive.

But they also should not be aliases.

Expected relationship after a successful redesign:

    PARTIAL_OVERLAP

not:

    IDENTICAL_FIRING_SET

and not necessarily:

    DISJOINT

## High-level distinction

### BUYING_CLIMAX

Primary semantic role:

    climactic buying effort / possible exhaustion

The event should answer:

    Is buying effort unusually intense late in an upward campaign,
    while the resulting price acceptance is no longer proportionate
    to that effort?

Its defining axis is:

    EFFORT versus RESULT / EXHAUSTION

### UPTHRUST

Primary semantic role:

    failed higher-price probe / rejection / trap

The event should answer:

    Did price probe above an already-visible higher-price reference,
    fail to hold that advance, and return back into or below the
    prior accepted area?

Its defining axis is:

    HIGHER-PRICE PROBE versus REJECTION / ACCEPTANCE

This distinction is more useful to the higher-level behavior interpreter than
two labels for the same high-volume up bar.

## Why this matters for sequence reasoning

The intended professional narrative may contain either or both observations.

Example:

    buying effort expands sharply
        -> BUYING_CLIMAX-style exhaustion evidence

    price then probes higher but cannot hold above prior highs
        -> UPTHRUST-style rejection evidence

Those are related but not identical facts.

At the sequence layer they should be able to contribute separately:

    effort becoming climactic
    rejection of higher prices
    supply appearing
    higher prices failing acceptance

That supports the larger ProVSA goal:

    understand the evolving supply/demand story,
    rather than require a perfect textbook label sequence.

## Current production collision

Both current collectors require:

    Buying Campaign
    Bullish Bar
    Very High Volume
    Above Average Spread

Current confirmations share:

    Wide Spread
    Weak Close

Unique confirmation:

    BUYING_CLIMAX
        Increasing Volume

    UPTHRUST
        Lower Close Than Previous

Because confirmations do not gate emission, the unique clauses currently do
not define event identity.

## First-principles semantic matrix

| Semantic axis | BUYING_CLIMAX | UPTHRUST |
|---|---|---|
| Background | Buying campaign / mature upward effort | Higher-price context / buying campaign or distribution-like background |
| Primary concept | Climactic effort and exhaustion | Failed higher-price probe and rejection |
| Volume | Defining: unusually high / climactic effort | Supporting quality; not necessarily the identity-defining axis |
| Spread | Large result attempt is relevant | Sufficient range to probe/reject is relevant |
| Bar direction | Up/bullish bar is a plausible defining feature | Must not be assumed defining; a rejected probe can close below its open |
| New/higher high | Optional | Defining local/structural price-probe feature |
| Close location | Off-high / poor acceptance strengthens exhaustion | Return away from the probed high is defining |
| Upper rejection | Supporting, not identity-defining | Strongly relevant |
| Previous close relation | Secondary | Secondary confirmation only |
| Previous/high reference | Not defining | Defining reference for rejection |
| Expected overlap | Can overlap with UT | Can overlap with BC |
| Sequence meaning | Buying effort becoming climactic | Higher prices rejected / trap behavior |

## Existing causal fields already available

The current point-in-time `BarContext` exposes:

    spread
    volume
    direction
    close_position

    spread_ratio
    volume_ratio

    open
    high
    low
    close_price

    body
    upper_shadow
    lower_shadow
    close_ratio

    prev_high
    prev_low
    prev_close
    prev_spread

The current `BackgroundContext` also exposes:

    trend
    structural_swings
    structural_pattern
    recent bars
    campaign context

Therefore the redesign does not require a new technical-indicator layer.

## Existing reusable causal helpers

Already present in `evidence/rules.py`:

    is_bullish_bar
    is_very_high_volume
    is_high_volume
    is_above_average_spread
    is_wide_spread

    is_weak_close
    closes_lower
    closes_upper

    makes_higher_high
    closes_lower_than_previous

    volume_increasing

These are all point-in-time predicates.

## Missing semantic helpers worth defining later

The redesign should prefer named semantic predicates over embedding raw
comparisons directly inside collectors.

### 1. Higher-price probe

Concept:

    current high exceeds an already-known reference high

Minimal local representation already available:

    current.high > previous.high

Equivalent existing helper:

    makes_higher_high(current, previous)

This is causal but only references one prior bar.

### 2. Failed local higher-price probe

Concept:

    price trades above the previous high
    but closes back below that prior high

Threshold-free candidate expression:

    current.high > previous.high
    AND
    current.close_price <= previous.high

This captures:

    probe above
    + failure to hold above

without tuning an arbitrary shadow percentage.

A future implementation should use a named helper such as:

    rejects_previous_high(current, previous)

The helper name is illustrative only in L16.

### 3. Failed structural higher-price probe

Stronger concept:

    price probes above the latest confirmed structural swing high
    and closes back below that swing price

The current `BackgroundContext.structural_swings` already provides causal
confirmed structural swings.

This is conceptually closer to:

    rejection at meaningful resistance

than a one-bar previous-high comparison.

However, it is a materially different detector contract and therefore requires
a dedicated causal replay before production consideration.

### 4. Poor acceptance after climactic effort

BUYING_CLIMAX should distinguish:

    large effort

from:

    healthy high-volume continuation

A conceptual requirement is:

    extreme effort
    + failure to finish with strong high-price acceptance

Current causal fields that can represent this include:

    close_position
    close_ratio
    upper_shadow

The semantic concept should be frozen before choosing one exact predicate.

L16 does NOT choose a close-ratio threshold.

## Candidate design families

These are design families for one later causal replay.

They are NOT production rules.

### BUYING_CLIMAX family

Core concept:

    buying campaign
    + climactic buying effort
    + large price-range attempt
    + evidence that acceptance at the high is deteriorating

Existing production components that remain conceptually aligned:

    Buying Campaign
    Bullish Bar
    Very High Volume
    Above Average Spread

Potential missing identity component:

    poor high-price acceptance / close off the high

Important:

    Increasing Volume

should be treated primarily as effort-quality evidence.

L15 showed it is broad enough to occur on roughly 74% of the current common
population, but that fact alone does not make it the semantic identity gate.

### UPTHRUST family

Core concept:

    higher-price probe
    + rejection back into prior accepted range

Candidate local geometry:

    makes_higher_high(current, previous)
    AND
    current.close_price <= previous.high

Potential quality evidence:

    weak close
    upper rejection
    high / very-high volume
    wide spread
    buying-campaign context

Important:

    closes_lower_than_previous(current, previous)

is not sufficient as the defining rejection concept.

L15 showed that using it alone as the unique mandatory differentiator leaves
only 177 events and only 56 genuinely UPTHRUST-only bars.

## Current Bullish Bar requirement on UPTHRUST

This requirement must be considered unresolved.

Current production requires:

    Bullish Bar

But the semantic event is:

    rejection of higher prices

A bar can probe higher and reject those prices while closing below its open.

Therefore:

    bullish direction may be compatible with an upthrust,
    but it should not be assumed to be conceptually mandatory
    without replaying the alternative population.

This is one reason the next validation cannot reuse only the current 4,497
baseline identities.

Bars excluded by the current Bullish Bar gate may be valid semantic candidates.

## Current Very High Volume requirement on UPTHRUST

This also requires explicit design review.

High effort can strengthen an upthrust interpretation because rejection despite
strong activity may indicate supply.

But the identity concept is:

    failed higher-price acceptance

not:

    very-high volume by itself

Therefore L16 classifies Very High Volume for UPTHRUST as:

    quality/context candidate

rather than automatically freezing it as the event's identity-defining axis.

No production relaxation is proposed here.

## Structural versus local rejection

The future causal replay should predeclare one of two contracts before seeing
outcomes.

### Option A — local rejection

Reference:

    previous bar high

Advantages:

- simple;
- causal;
- no new structural machinery;
- directly supported by BarContext.

Limitations:

- previous high may not be meaningful resistance;
- may classify ordinary two-bar reversals as upthrusts.

### Option B — confirmed structural rejection

Reference:

    latest confirmed structural swing high

Advantages:

- closer to meaningful higher-price rejection;
- aligns with ProVSA's existing structural architecture;
- useful to professional sequence interpretation.

Limitations:

- more complex;
- lower expected frequency;
- must carefully use only swings confirmed by the candidate bar;
- requires exact point-in-time replay validation.

L16 does not select between A and B empirically.

## Recommended next validation contract

One and only one causal design replay should follow L16.

It should compare a small predeclared matrix, not search arbitrary thresholds.

Recommended matrix:

### BUYING_CLIMAX candidate

Keep the current effort/background core:

    Buying Campaign
    Bullish Bar
    Very High Volume
    Above Average Spread

Measure separately:

    strong-high acceptance
    middle/off-high acceptance
    weak/lower close

Purpose:

    determine whether the current label contains both
    healthy continuation and actual exhaustion geometry.

Do not optimize a close threshold in this replay.

### UPTHRUST candidate

Primary identity:

    higher-price probe
    + failed acceptance above reference high

Evaluate exactly two predeclared reference definitions:

    local previous high
    confirmed structural swing high

For both, record:

    bar direction
    volume class
    spread class
    close position
    upper-shadow geometry

These are descriptors, not automatically tuned gates.

## What the next replay should answer

Only these questions:

1. Does a rejection-based UPTHRUST contract produce a sufficiently represented
   causal population?

2. Is that population meaningfully distinct from BUYING_CLIMAX?

3. Does BUYING_CLIMAX contain a meaningful split between:
       climactic effort with poor acceptance
   and
       high-volume continuation with strong acceptance?

4. Do the redesigned labels show the expected:
       PARTIAL_OVERLAP
   relationship?

If yes:

    allow one robustness / behavior-value validation.

If no:

    PARK or REJECT the redesign and move on.

## What the next replay must NOT do

Do not search:

    upper-shadow thresholds
    close-ratio cutoffs
    multiple volume thresholds
    multiple spread thresholds
    arbitrary trend-state combinations
    outcome-optimized resistance windows
    many nested confirmation combinations

Do not select the definition that produces the best forward return.

The semantic contract must be justified before outcome inspection.

## Stop rule

L16 keeps the detector stopping policy explicit.

### After semantic replay

If the candidate geometry fails to create clear, sufficiently represented
semantic populations:

    PARK / REJECT
    and move to the next detector.

### If the semantic replay succeeds

Permit exactly one validation stage for:

    robustness
    sequence usefulness
    or forward behavior

Then decide:

    PROMOTE
    REJECT
    PARK

No third exploratory layer.

## Relationship to professional sequence reasoning

The redesign should make these statements separately available:

    "buying effort became climactic"

and:

    "higher prices were rejected"

A later sequence interpreter could then observe:

    strong markup
    -> climactic effort
    -> rejection of higher prices
    -> weak reaction / failed continuation

without relying on duplicate same-bar labels.

This is the purpose of the detector cleanup:

    a sane evidence vocabulary for higher-level behavior reasoning.

## Production decision at L16

No production change.

Current production continues to emit both labels on the same mandatory
population until a separately validated production PR changes the contract.

The current state is recognized as:

    mechanically active
    but semantically collapsed

for this detector pair.

## Next step

Build one causal semantic replay from frozen snapshots using the predeclared
design above.

That replay is allowed to evaluate:

    BUYING_CLIMAX acceptance geometry

and:

    UPTHRUST local rejection
    UPTHRUST structural rejection

It is not allowed to optimize thresholds or inspect outcomes while defining the
candidate populations.

## Safety

L16 changes no:

- BUYING_CLIMAX collector;
- UPTHRUST collector;
- confirmation gating;
- evidence weights;
- professional supply score;
- ranking;
- weekly thesis;
- DailyBehavior;
- qualification/actionability;
- APIs;
- alerts/orders;
- production market-data loading.
