# VSA Event Documentation Consistency Audit

## Status

Docs-only consistency correction record.

This document reconciles the older event-audit notes with the current production source and the `audit.vsa_events` catalog. It does not change detector logic, scoring, ranking, qualification, actionability, API output, or live scanner behavior.

## Source of truth order

Use this order when older docs disagree:

1. Current production source code.
2. Canonical per-event specs in `docs/specifications/`.
3. Event-specific audit records such as `ABSORPTION_AUDIT.md`.
4. `PRIMARY_VSA_EVENT_MATRIX.md` as a high-level inventory.
5. Older embedded notes in the primary matrix body.

## Corrected observations

### ABSORPTION

Current source and `ABSORPTION_AUDIT.md` agree that `ABSORPTION` is production-connected and non-scoring/frozen:

```text
detector              = evidence/absorption.py::collect_absorption
collection path       = EvidenceEngine.collect -> collect_demand -> collect_absorption
production path       = YES
production scoring    = NO
runtime weight        = 0.00
empirical weight      = 0.38 research/audit reference only
conflict penalty      = 0.20 research/counterfactual only
production mutation   = NO
```

Older `PRIMARY_VSA_EVENT_MATRIX.md` language that says `ABSORPTION` has no dedicated production detector, no production path, no registry entry, or no collector is stale relative to the current code and `ABSORPTION_AUDIT.md`.

Policy:

```text
ABSORPTION status = PRODUCTION-CONNECTED / NON-SCORING / FROZEN
```

### NO_DEMAND

Current source defines `NO_DEMAND` under the supply collector:

```text
detector        = evidence/supply.py::_collect_no_demand
collection path = EvidenceEngine.collect -> collect_supply -> _collect_no_demand
```

Older `NO_DEMAND_AUDIT.md` top summary text saying `evidence/demand.py::_collect_no_demand` and `collect_demand` is a documentation-path typo. The event remains supply-side bearish VSA evidence.

Policy:

```text
NO_DEMAND collector = evidence/supply.py::_collect_no_demand
```

## No production change

These are documentation consistency corrections only. They must not be interpreted as new validation, new calibration, or a production promotion.

Future work should update `PRIMARY_VSA_EVENT_MATRIX.md` directly during the next consolidated documentation refresh so the high-level matrix and embedded historical sections no longer contain stale ABSORPTION wording.
