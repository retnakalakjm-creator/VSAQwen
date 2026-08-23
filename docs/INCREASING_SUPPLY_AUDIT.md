# INCREASING_SUPPLY Audit Record

## Final status

`INCREASING_SUPPLY` is production-active and audit-complete for the current detector and scoring architecture. Its empirical reference weight is `0.85`, while the current production runtime emits it at `1.00`. That discrepancy is documented and has **not** been treated as a production bug.

```text
production path              = YES
collector                     = evidence/supply.py::_collect_increasing_supply
engine collection             = YES (via collect_supply)
direction                    = Bearish / supply
empirical reference weight   = 0.85
registry/profile weight      = 0.85
configured supply-map weight = 0.70
production runtime weight     = 1.00 observed
production interaction penalty = NONE
production status             = ACTIVE / AUDIT-COMPLETE
```

The three weight concepts must remain separate: the registry/reference value is a calibration reference, the configured supply-map value is the static scoring-map entry, and the observed production emission is `1.00`.

## Audit completion

The event completed the current audit-first validation sequence:

1. Candidate audit — PASS
2. Semantic-quality audit — PASS
3. Interaction / contradiction audit — PASS
4. Interaction outcome audit — PASS
5. Decision-value audit — PASS
6. Weight-sensitivity audit — PASS
7. Full scanner ranking replay — PASS after scoring-path correction
8. Production-path readiness audit — PASS

The replay audits were optimized to avoid rebuilding the full evidence engine once for every tested weight. Point-in-time target snapshots are prepared once and reused for the counterfactual scoring loop.

## Frozen candidate population

Across the 8-symbol audit universe:

```text
symbols requested           = 8
symbols with results        = 8
bars / eligible market bars = 11,345
cheap candidates            = 1,022
candidate events            = 528
expected candidate events   = 528
```

The candidate population is frozen for the weight-sensitivity and scanner-ranking audits.

## Frozen detector semantics

The validated point-in-time target semantics are:

1. Down / bearish bar.
2. Increasing volume versus the previous bar.
3. Increasing spread versus the previous bar.

The semantic audit established:

```text
down_bar             = 528 / 528
volume_increasing    = 528 / 528
spread_increasing    = 528 / 528
semantic failures    = 0
point-in-time        = YES
target-bar-only       = YES
production context    = YES
frozen population     = YES
```

The detector semantics were not changed to force textbook-perfect formations. Imperfect but meaningful real-market VSA evidence remains admissible when the frozen rule semantics are satisfied.

## Outcome / decision-value audit

Using the project’s 8-bar forward-return methodology:

```text
candidate events               = 528
positive outcomes              = 335
negative outcomes              = 193
flat outcomes                  = 0
decisive outcomes              = 528
positive decisive rate         = 63.45%
mean 8-bar return              = +3.06%
```

Eligible-market comparison:

```text
eligible market events         = 11,345
eligible positive decisive rate = 60.79%
candidate rate lift             = +2.66 percentage points
eligible mean return            = +3.83%
candidate mean-return lift      = -0.77 percentage points
candidate share of eligible    = 4.65%
```

Conclusion: `INCREASING_SUPPLY` demonstrates incremental **directional classification value**, but not incremental **return-magnitude alpha** in this audit population.

This does not invalidate the event as VSA evidence. It means its strongest demonstrated role is as a supply-pressure component of the scanner decision rather than as a standalone return predictor.

## Interaction / contradiction audit

The same-bar interaction audit on the frozen 528-event population produced:

```text
events                         = 528
events with supply conflict    = 147
supply conflict rate            = 27.84%
demand interaction events       = 30
self-conflict excluded          = YES
target-bar-only                 = YES
production context used         = YES
point-in-time                   = YES
status                          = PASS
```

The audited supply conflict was:

```text
SUPPLY_COMING_IN = 147 events
```

The audited demand interaction was:

```text
STOPPING_VOLUME = 30 events
```

No other same-bar supply or demand interaction was established in this frozen population.

## Interaction outcome

The interaction groups were:

| Group | Events | Positive decisive rate | Mean 8-bar return |
|---|---:|---:|---:|
| Clean | 289 | 61.25% | +2.22% |
| Other supply | 133 | 66.17% | +3.98% |
| Other demand | 92 | 67.39% | +4.50% |
| `SUPPLY_COMING_IN + SELLING_CLIMAX` | 14 | 57.14% | +2.11% |

The broader interaction population is outcome-confirming rather than a reason for blanket rejection or penalty. The 14-event `SUPPLY_COMING_IN + SELLING_CLIMAX` pocket is weaker, but it is too small to justify a global interaction penalty.

Frozen interaction policy:

```text
interaction penalty = NONE
rejection rule       = NO
```

## Weight-sensitivity audit

Counterfactual weights tested:

```text
0.70, 0.75, 0.80, 0.85, 0.90, 1.00
```

The weight must be changed through `config.SUPPLY_EVIDENCE_WEIGHTS` because `ProfessionalScoringEngine` reads the live configuration map; changing `Evidence.weight` objects alone does not create a valid scoring counterfactual.

The corrected replay demonstrated real downstream sensitivity:

| Weight | Mean production-capped supply score | Final scores changed | Within-symbol rank positions changed | Actionability changed |
|---:|---:|---:|---:|---:|
| 0.70 | 0.9273 | baseline | baseline | baseline |
| 0.75 | 0.9394 | 381 / 528 | 98 / 528 | 0 |
| 0.80 | 0.9515 | 381 / 528 | 173 / 528 | 0 |
| **0.85** | **0.9636** | **381 / 528** | **213 / 528** | **0** |
| 0.90 | 0.9758 | 381 / 528 | 237 / 528 | 0 |
| 1.00 | 1.0000 | 381 / 528 | 297 / 528 | 0 |

Additional wiring verification showed:

```text
raw supply contribution changed when weight changed = YES, 528 / 528
production-capped supply score changed             = 128 / 528
final scanner score changed                        = 381 / 528
actionability changed                              = 0 / 528
qualification changed                              = 0 / 528
scoring-path wiring check                           = PASS
```

The tested weight therefore affects professional strength, confidence, and ranking, but did not change qualification or actionability in the frozen 528-event population.

## Empirical reference vs production runtime

The final calibrated distinction is:

```text
registry / empirical reference = 0.85
configured supply-map          = 0.70
production runtime emission    = 1.00
```

The production-path readiness audit established:

```text
cheap candidates              = 1,022
production emissions          = 528
expected emissions            = 528
runtime weight observed min   = 1.00
runtime weight observed max   = 1.00
runtime weight observed mean  = 1.00
runtime weight matches emission = YES
duplicate emissions            = 0
semantic failures              = 0
production score mutation      = NO
failures                       = 0
status                         = PASS
```

The observed `1.00` runtime behavior is therefore a verified property of the current production path, not an audit wiring failure.

## Frozen production decision

```text
INCREASING_SUPPLY

production collector          = YES
production emission           = YES
registry / empirical reference = 0.85
configured supply-map         = 0.70
runtime emission              = 1.00
interaction penalty           = NONE
rejection rule                = NO
qualification impact          = NONE observed across tested weights
actionability impact          = NONE observed across tested weights
ranking / strength impact     = YES
production weight change      = NONE
status                        = PRODUCTION-ACTIVE / AUDIT-COMPLETE
```

The audit campaign does **not** justify changing the production runtime from `1.00` to `0.85` at this time. Keep `0.85` recorded as the empirical calibration reference and preserve `1.00` as the current verified runtime behavior.

## Audit principles preserved

- Real-market VSA evidence may be imperfect; textbook purity is not required.
- Detector semantics remain unchanged during scoring calibration.
- Weight tuning changes scoring only; it does not change event detection.
- Interaction overlap is not automatically a contradiction.
- Empirical reference weights and production runtime weights are separate concepts.
- Production-path audits must verify actual emitted runtime behavior rather than assuming the registry value is the runtime value.
