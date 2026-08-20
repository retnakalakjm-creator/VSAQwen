# ABSORPTION Audit Record

## Status

`ABSORPTION` is **audit-complete / provisional / non-production**.

The event is not collected by the production `EvidenceEngine`, is not registered in `evidence/evidence_registry.py`, and does not mutate production scoring or ranking.

```text
base weight        = 0.38   # provisional audit value only
conflict penalty   = 0.20   # provisional audit policy only
rejection          = NO
production path    = NO
```

## Candidate semantics

The audit-only candidate definition is:

1. Bearish/down bar.
2. High volume.
3. Above-average spread.
4. Close in the upper portion of the bar.
5. Lower low than the previous bar.

This represents selling effort with a comparatively resilient result and is treated as an effort/result absorption concept rather than an automatically actionable bullish event.

## Candidate outcome audit

- Symbols requested: `8`
- Symbols with results: `8`
- Candidate events: `68`
- Positive: `44`
- Negative: `24`
- Flat: `0`
- Decisive: `68`
- Positive decisive rate: `64.71%`
- Mean 8-bar return: `+3.08%`
- Failures: `0`

## Semantic-quality audit

The 68 candidates were internally consistent with the intended structural definition:

- Upper close: `68 / 68`
- Lower low: `68 / 68`
- High volume classification: `16 / 68`
- Wide spread classification: `16 / 68`
- Semantic failures: `0`

The high-volume and wide-spread classifications are therefore confirmation descriptors rather than universal requirements beyond the candidate definition already used.

## Interaction / contradiction audit

The 68 candidates were compared against same-bar supply and demand evidence families.

### Supply-side interaction

- Events with supply conflict: `37 / 68`
- Conflict rate: `54.41%`
- `INCREASING_SUPPLY_LIKE`: `37`
- `SUPPLY_COMING_IN_LIKE`: `0`
- `HIDDEN_SUPPLY_LIKE`: `0`
- `UPTHRUST_LIKE`: `0`
- `NO_DEMAND_LIKE`: `0`
- `BUYING_CLIMAX_LIKE`: `0`

The supply overlap is concentrated entirely in `INCREASING_SUPPLY_LIKE`.

### Demand-side interaction

All `68 / 68` candidates also interacted with `STOPPING_VOLUME_LIKE`.

This is treated as compatible contextual confirmation rather than contradiction: both events describe substantial selling effort whose result shows resilience.

Other audited demand interactions were zero.

## Conflict-outcome audit

The `INCREASING_SUPPLY_LIKE` overlap was materially harmful to historical outcome quality.

- Conflict events: `37`
- Clean events: `31`
- Conflict positive decisive rate: `59.46%`
- Clean positive decisive rate: `70.97%`
- Positive-rate gap: `-11.51` percentage points
- Conflict mean return: `-0.58%`
- Clean mean return: `+7.44%`
- Mean-return gap: `-8.02` percentage points

This supports applying a quality penalty to conflicted absorption observations in audit modelling.

## Conflict-penalty sensitivity

Tested penalties:

```text
0.00 -> effective conflict weight 1.00
0.05 -> effective conflict weight 0.95
0.10 -> effective conflict weight 0.90
0.15 -> effective conflict weight 0.85
0.20 -> effective conflict weight 0.80
```

The sensitivity audit recommended the maximum tested penalty:

```text
conflict_penalty = 0.20   # provisional audit policy only
rejection = NO
```

## Decision-value audit

The candidate population compared with the eligible-market baseline produced:

- Candidate positive decisive rate: `64.71%`
- Eligible-market positive decisive rate: `60.68%`
- Positive-rate lift: `+4.02` percentage points
- Candidate mean return: `+3.08%`
- Eligible-market mean return: `+3.78%`
- Mean-return lift: `-0.71` percentage points
- Candidate share of eligible events: `0.61%`

Clean absorption events were substantially stronger than conflicted events, so the signal appears to contain useful information when supply-increase conflict is absent.

Weight sensitivity tested:

```text
0.00
0.25
0.30
0.38
0.45
0.50
```

At the provisional base weight of `0.38`:

```text
clean effective weight    = 0.38
conflict effective weight = 0.304
```

The `0.38` value is therefore retained as a conservative provisional audit weight, not as a production-approved weight.

## Production-path readiness

A dedicated readiness audit established:

```text
collector_contains_target       = False
engine_collect_mentions_target = False
registry_contains_target       = False
base_weight                    = 0.38
conflict_penalty               = 0.20
clean_effective_weight         = 0.38
conflict_effective_weight      = 0.304
true_ranking_impact_status      = NOT_APPLICABLE_PRODUCTION_PATH_ABSENT
synthetic_ranking_safe_weight   = True
production_score_mutation       = False
status                         = PASS
```

This is the decisive architectural boundary. No live ranking-impact result is claimed because `ABSORPTION` is not in the production evidence path.

## Final audit decision

```text
ABSORPTION
    base weight        = 0.38   # provisional
    conflict penalty   = 0.20   # provisional
    rejection          = NO
    production path    = NO
    registry           = NO
    collector          = NO
    scoring mutation   = NO
    status             = AUDIT_COMPLETE / PROVISIONAL
```

The event remains eligible for future production promotion, but promotion requires a canonical production detector, registry registration, production-path verification, and genuine ranking/regression validation. No audit-only weight should be interpreted as an active production scoring rule.
