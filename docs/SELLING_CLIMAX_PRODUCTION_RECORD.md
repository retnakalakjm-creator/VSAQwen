# SELLING_CLIMAX Production Record

## Final status

`SELLING_CLIMAX` is production-integrated on `main` with **detector semantics frozen / M12 PARKED**.

```text
production path        = YES
collector              = evidence/demand.py::_collect_selling_climax
engine collection      = YES (via collect_demand)
registry               = YES
profile/emitted weight = 0.38
detector status         = FROZEN / M12 PARKED
production status       = ACTIVE
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

## M12 detector closure

The M12 stop-rule review retained the current four-clause mandatory identity,
confirmed distinctness from `STOPPING_VOLUME`, verified that the three
confirmations remain diagnostic/non-gating, and found no obvious production-safe
detector correction.

```text
semantic contract      RETAIN
distinctness           PASS
confirmation behavior  PASS
obvious detector fix   NONE

M12 detector status    PARKED
detector semantics     FROZEN
production emission    UNCHANGED
```

Current source explicitly emits `SELLING_CLIMAX` at `Evidence.weight = 0.38`
through `evidence.helpers.add_evidence()`; this is not a dynamic runtime weight.

`SELLING_CLIMAX` remains an active production demand/reversal event.

See `docs/DAILY_EVENT_SELLING_CLIMAX_DETECTOR_VERDICT.md`.

Future changes to its semantics or weight must begin a new audit cycle rather
than bypassing the audit-first process.
