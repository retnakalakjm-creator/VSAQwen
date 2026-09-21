# M12 / L14 — NO_SUPPLY Research Verdict

## Status

NO_SUPPLY research is closed for the current M12 daily-event audit cycle.

Production behavior remains unchanged.

This document is the authoritative closure record for the L4-L13 NO_SUPPLY
investigation and should be read before reopening detector work.

Final disposition:

    production detector change        NO
    environment predicate change      NO
    confirmation gate change          NO
    weight/scoring change             NO
    qualification/actionability       NO

    research status                   PARKED
    reason                            semantics unresolved and
                                      outcome behavior not robust enough

## Why this investigation existed

L2/L4 found that the production NO_SUPPLY detector had several semantic issues:

1. requirement label / predicate mismatch:

       label:
           Bullish Environment

       predicate:
           bearish environment

2. mandatory:

       Narrow Spread

   and confirmation:

       Weak Spread

   were effectively redundant.

3. confirmations were present but non-gating.

4. the source confirmation label:

       Weak Selling Result

   was not an effort/result calculation.

   It was:

       is_weak_close(bar)

The purpose of L5-L13 was to determine whether any obvious semantic correction
was justified before changing production.

The answer is:

    no production correction is justified from the current evidence.

## Canonical source foundation

All canonical NO_SUPPLY studies ultimately descend from the frozen daily input
snapshot:

    basket:
        milestone6_standard_india_large_cap_30

    symbols:
        30

    provider:
        yfinance

    period:
        max

    cutoff:
        2026-09-18

    snapshot manifest SHA-256:
        45bb7123d2b3b570cf58241f09cb6175f6052d792f92728b194fc587762fb8ff

Production market-data loading remains separate and unchanged.

## Evidence chain

### L4 / detector semantics

Production NO_SUPPLY requirements:

    bearish environment
    bearish bar
    low volume
    narrow spread

Confirmations:

    weak spread
    volume decreasing
    weak selling result

Findings:

- "Bullish Environment" label used a bearish predicate.
- Weak Spread was redundant with mandatory Narrow Spread.
- Weak Selling Result was a close-position predicate, not a validated
  effort/result concept.

No production change was made.

### L5 / correction design

The detector correction design identified three NO_SUPPLY issues:

- environment label/predicate mismatch;
- redundant Weak Spread confirmation;
- confirmation semantics requiring causal validation.

The environment predicate could not be changed safely from static inspection.

### L6 / environment replay

The current bearish-environment detector was causally reproduced exactly.

Canonical counts:

    common signature:
        Bearish Bar + Low Volume + Narrow Spread
        3,584

    CURRENT / bearish environment:
        777

    ALTERNATE / bullish environment:
        1,732

    overlap:
        0

    neither:
        1,075

The alternate population was more than twice as large.

This established that changing the environment predicate would materially
redefine the detector rather than merely fix a label.

### L7 / direct forward outcomes

CURRENT and ALTERNATE forward outcomes were measured.

The direct comparison was confounded because:

    CURRENT
        DOWN environment

    ALTERNATE
        UP environment

Therefore L7 was not sufficient to choose an environment predicate.

### L8 / same-environment matching

Every L6 target was matched 1:1 without replacement to a nearby same-symbol,
same-trend-direction bearish control.

Canonical:

    source targets:
        2,509

    matched:
        2,509

    unmatched:
        0

The common signature:

    Bearish Bar
    + Low Volume
    + Narrow Spread

underperformed matched controls in both environments.

Clean event-weighted return deltas:

CURRENT / DOWN:

    H1     -0.043 pp
    H3     -0.261 pp
    H5     -0.327 pp
    H10    -0.421 pp
    H20    -0.450 pp

ALTERNATE / UP:

    H1     -0.074 pp
    H3     -0.222 pp
    H5     -0.348 pp
    H10    -0.346 pp
    H20    -0.392 pp

Therefore the broad common signature was not supported as a positive matched
return signal.

### L9 / confirmation strata

Weak Spread passed for all canonical NO_SUPPLY targets and was confirmed
redundant.

Meaningful confirmation dimensions were:

    Volume Decreasing
    Weak Selling Result

The important subgroup was:

    WEAK_RESULT_ONLY

meaning:

    weak_selling_result = true
    volume_decreasing   = false

Canonical population:

    CURRENT / DOWN:
        122

    ALTERNATE / UP:
        305

    total:
        427

The inclusive Volume Decreasing gate remained negative across horizons in both
environments.

WEAK_RESULT_ONLY showed materially better matched behavior and became the only
NO_SUPPLY subgroup worth deeper study.

### L10 / robustness and corrected source semantics

The 427-event WEAK_RESULT_ONLY population was tested with:

- event-weighted estimates;
- symbol-normalized estimates;
- 30-symbol clustered bootstrap;
- leave-one-symbol-out;
- direct production predicate semantics.

No close-to-close return bootstrap interval was robustly above zero.

The strongest repeatable finding was favorable excursion:

CURRENT H1/H3/H5 MFE:
    cluster-bootstrap intervals excluded zero
    under both event-weighted and symbol-normalized estimands.

ALTERNATE also showed robust early MFE in the full-history aggregate.

Therefore WEAK_RESULT_ONLY looked more like:

    short-term excursion / opportunity-shape evidence

than:

    robust fixed-horizon terminal-return evidence

#### Important semantic correction

The original research wording interpreted:

    volume_decreasing(current, previous)

as a raw-volume comparison.

That interpretation was wrong.

Production uses:

    BarContext.volume

and that field is:

    VolumeClass

Therefore:

    volume_decreasing
        -> current VolumeClass ordinal
           < previous VolumeClass ordinal

and:

    NOT volume_decreasing
        -> current VolumeClass ordinal
           >= previous VolumeClass ordinal

WEAK_RESULT_ONLY therefore means:

    bearish bar
    AND low-volume production classification
    AND narrow spread
    AND close position in LOWER or ON_LOW
    AND current VolumeClass is not lower than previous VolumeClass

It does NOT require:

    current raw volume >= previous raw volume

L12 corrected the semantic audit, tests, and documentation.

### L11 / temporal stability

The 427-event candidate was partitioned into fixed calendar eras:

    EARLY_HISTORY
    2010_2014
    2015_2019
    2020_2022
    2023_2026

CURRENT / DOWN early MFE was broadly durable.

H1:
    positive in 5/5 eras
    under both estimands

H5:
    positive in 5/5 eras
    under both estimands

H3:
    positive in 4/5 eras event-weighted
    positive in 5/5 eras symbol-normalized

ALTERNATE / UP was not temporally stable.

In 2023-2026:

    H1 MFE:
        negative

    H3 MFE:
        negative

    H5 MFE:
        negative

under both event-weighted and symbol-normalized views.

The latest ALTERNATE population had:

    42 targets
    24 symbols

so the failure was not attributable to one symbol.

### L12 / ALTERNATE context profile

L12 compared:

    ALTERNATE prior history through 2022:
        263 targets

with:

    ALTERNATE 2023-2026:
        42 targets

using only predeclared production-derived context.

No large one-dimensional continuous context shift explained the failure.

Notable categorical changes included:

Trend state:

    HEALTHY
        67.68% -> 80.95%
        +13.27 pp

    EXHAUSTED
        16.35% -> 4.76%
        -11.59 pp

VolumeClass:

    ULTRA_LOW
        20.53% -> 35.71%
        +15.18 pp

    VERY_LOW
        34.22% -> 23.81%
        -10.41 pp

VolumeClass relation:

    SAME_CLASS
        64.64% -> 73.81%
        +9.17 pp

    HIGHER_CLASS
        35.36% -> 26.19%
        -9.17 pp

SAME_CLASS historically had weaker H1/H3/H5 MFE than HIGHER_CLASS.

However, the mix shift was far too small to explain the full 2023-2026
deterioration.

Therefore SAME_CLASS was a plausible weakening factor, not a sufficient
explanation.

### L13 / VolumeClass relation x era

L13 tested SAME_CLASS and HIGHER_CLASS separately by era.

2023-2026:

SAME_CLASS:

    31 targets
    19 symbols

    H1 MFE    -0.308 / -0.282 pp
    H3 MFE    -0.199 / -0.168 pp
    H5 MFE    -0.566 / -0.483 pp

HIGHER_CLASS:

    11 targets
    9 symbols

    H1 MFE    -0.012 / -0.128 pp
    H3 MFE    -0.141 / -0.490 pp
    H5 MFE    +0.379 / +0.188 pp

Values are:

    event-weighted / symbol-normalized

Interpretation:

- SAME_CLASS fails at H1/H3/H5.
- HIGHER_CLASS also loses the H1/H3 MFE edge.
- HIGHER_CLASS remains positive at H5.

The descriptive interaction contrast changed sign across horizons and
estimands.

Therefore there was no stable evidence that SAME_CLASS uniquely caused the
recent ALTERNATE failure.

## Final detector interpretation

### Broad NO_SUPPLY signature

Current common signature:

    bearish bar
    low volume
    narrow spread

Result:

    not validated as positive matched decision evidence

### Current bearish environment

The current environment predicate should NOT be changed solely because its
human-facing label says "Bullish Environment."

The alternate bullish predicate materially changes the event population and did
not establish a superior robust outcome contract.

### Weak Spread confirmation

Status:

    redundant

Reason:

    mandatory Narrow Spread already guarantees the same observed condition in
    the canonical population.

This is a semantic/documentation defect, but removing or restructuring the
confirmation is not being bundled into production during M12.

### Volume Decreasing confirmation

Status:

    not supported as a mandatory production gate

The production predicate compares VolumeClass ordinal, not raw volume.

The confirmation-selected population did not establish a robust positive edge.

### Weak Selling Result confirmation

Actual source predicate:

    is_weak_close(bar)

meaning:

    close_position in {LOWER, ON_LOW}

The label should not be interpreted as a validated effort/result relationship.

### WEAK_RESULT_ONLY

Status:

    research-interest subgroup only

Evidence:

- promising favorable-excursion behavior;
- particularly durable in CURRENT / DOWN;
- not supported by robust terminal-return inference;
- ALTERNATE / UP is temporally unstable;
- simple VolumeClass relation does not explain that instability.

It is not production-ready.

## Production decision

Do not change:

- NO_SUPPLY environment predicate;
- mandatory requirements;
- confirmation gating;
- evidence profile or weight;
- scoring/ranking;
- DailyBehavior mapping;
- qualification;
- actionability;
- API behavior;
- alerts;
- orders.

The current production detector is not being declared empirically optimal.

The decision is narrower:

    current evidence does not support a safer replacement contract.

## Why research stops here

Continuing from L13 into unrestricted combinations such as:

    trend state x relation x era
    structural pattern x trend state x era
    VolumeClass x trend state x structural pattern
    arbitrary indicator additions

would create rapidly shrinking subgroups and increasing multiple-comparison /
data-mining risk.

That would no longer serve the primary M12 objective efficiently:

    validate the correctness and distinctness of the daily detector system.

The NO_SUPPLY thread has already produced enough evidence to make the current
production decision:

    no change.

## Reopening criteria

Do not reopen NO_SUPPLY merely because another descriptive subgroup looks
interesting.

Reopen only when at least one of the following is true.

### 1. Independent out-of-sample evidence

A new frozen sample that was not used to discover WEAK_RESULT_ONLY confirms a
specific candidate contract.

Prefer:

- later unseen history;
- a separately frozen basket;
- or both.

### 2. Explicit product requirement

A future execution layer needs a clearly defined short-horizon reaction signal
and chooses to evaluate WEAK_RESULT_ONLY prospectively.

That study must define the execution rule before reading future outcomes.

### 3. Detector semantic redesign

There is an explicit proposal to redesign NO_SUPPLY semantics from VSA first
principles.

That proposal must specify:

- intended market concept;
- mandatory bar structure;
- intended background context;
- confirmation meaning;
- non-overlap with neighboring detectors.

It should not be reverse-engineered solely from historical subgroup performance.

### 4. New independently justified context variable

A broader regime/context state becomes part of ProVSA for reasons independent
of this NO_SUPPLY study.

Only then may NO_SUPPLY be retested conditionally on that state without
inventing a one-off detector-specific feature.

## M12 handoff

NO_SUPPLY is now parked.

The next higher-priority system-level finding is:

    BUYING_CLIMAX
    and
    UPTHRUST

have an identical canonical daily firing set in L2.

Canonical frozen L2:

    BUYING_CLIMAX unique events:
        4,497

    UPTHRUST unique events:
        4,497

    overlap:
        4,497

    relationship:
        IDENTICAL_FIRING_SET

The next detector audit should therefore return to the M12 system objective and
determine whether this identity is:

- intentional aliasing;
- duplicated mandatory semantics;
- missing differentiating confirmation/gate;
- or an accidental detector collapse.

That issue has higher system-level priority than further slicing NO_SUPPLY.

## Closure

NO_SUPPLY has been investigated deeply enough for the current milestone.

The research conclusion is not:

    NO_SUPPLY is good

or:

    NO_SUPPLY is bad.

The conclusion is:

    the current detector has semantic defects,
    obvious corrections are not empirically justified,
    one subgroup has interesting excursion behavior,
    but the evidence is not robust enough for production promotion.

Therefore:

    freeze the evidence,
    leave production unchanged,
    move to the next detector correctness defect.
