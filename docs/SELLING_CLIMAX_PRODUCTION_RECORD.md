# SELLING_CLIMAX Production Record

## Final status

`SELLING_CLIMAX` is now production-integrated on `main`.

```text
production path        = YES
collector              = evidence/demand.py::_collect_selling_climax
engine collection      = YES (via collect_demand)
registry               = YES
base weight            = 0.38
production status      = ACTIVE
```

## Audit completion

The event completed the full audit-first promotion sequence:

1. Candidate audit — PASS
2. Semantic-quality audit — PASS
3. Interaction / contradiction audit — PASS
4. Interaction outcome audit — PASS
5. Decision-value audit — PASS
6. Production-path readiness audit — PASS
7. Post-integration production audit — PASS

## Decision-value evidence

- candidate events: `153`
- positive outcomes: `98`
- negative outcomes: `55`
- positive decisive rate: `64.05%`
- eligible-market positive decisive rate: `60.68%`
- positive-rate lift: `+3.37` percentage points
- candidate mean 8-bar return: `+4.24%`
- eligible-market mean 8-bar return: `+3.78%`
- mean-return lift: `+0.46` percentage points
- candidate share of eligible events: `1.37%`

## Interaction evidence

`STOPPING_VOLUME` is treated as a confirming interaction rather than a contradiction.

- clean `SELLING_CLIMAX`: `114` events
- `SELLING_CLIMAX + STOPPING_VOLUME`: `39` events
- clean positive decisive rate: `61.40%`
- stopping-volume interaction positive decisive rate: `71.79%`
- clean mean return: `+4.16%`
- stopping-volume interaction mean return: `+4.46%`
- same-bar `SELLING_CLIMAX + SHAKEOUT`: structurally impossible under current recovery-anchored semantics

Supply overlap is interpreted as semantic overlap inherent to the selling-climax definition, not an automatic contradiction. No supply conflict penalty was introduced.

## Post-integration verification

The real production engine was exercised against the validated candidate population.

```text
cheap candidates       = 570
engine replays         = 570
production emissions   = 153
expected weight        = 0.38
wrong weight           = 0
duplicate emissions    = 0
score mutation errors  = 0
campaign mismatches    = 0
runtime errors         = 0
status                 = PASS
```

This verifies that the production collector emits the expected `SELLING_CLIMAX` evidence at weight `0.38`, without duplicate emission or unintended score mutation.

## Promotion decision

`SELLING_CLIMAX` is no longer provisional or frozen. It is an active production demand/reversal event at base weight `0.38`.

Future changes to its semantics or weight must begin a new audit cycle rather than bypassing the audit-first promotion process.
