# Primary VSA Event Matrix

This document is the current production-coverage inventory for the VSA event layer on `main`.

It is a specification/diagnostic artifact only. It does not change detector logic, evidence weights, qualification rules, ranking, actionability, API responses, or live scanner behavior.

## Source-of-truth order

When older audit notes disagree, use this order:

1. Current production source code.
2. Canonical per-event specifications in `docs/specifications/`.
3. The analysis-only contract catalog in `audit/vsa_events.py`.
4. Event-specific audit records such as `ABSORPTION_AUDIT.md` and `NO_DEMAND_AUDIT.md`.
5. This high-level matrix.
6. Older embedded historical notes.

The previous version of this file embedded long historical audit sections. Those records are intentionally not duplicated here. Use the event-specific audit documents and canonical specs for detailed historical evidence.

## Canonical event specifications

The `docs/specifications/` directory is the canonical per-event rulebook. A per-event specification is created only after semantics, validation evidence, and production status are sufficiently frozen.

Current canonical specifications:

- `001_stopping_volume.md` — production-integrated / validation-complete.
- `002_shakeout.md` — production-integrated / validation-complete.
- `003_test.md` — production-integrated contextual confirmation / non-scoring.
- `004_spring.md` — production-integrated / provisional.
- `005_no_supply.md` — contextual / validation-complete for its current non-scoring role.

## Current production collection path

`EvidenceEngine.collect()` currently invokes:

- `collect_supply()`
- `collect_demand()`
- `collect_spring()`
- `collect_structural_progression()`

Inside `collect_supply()`, these VSA supply-side detectors are active for eligible bars:

- `BUYING_CLIMAX`
- `SUPPLY_COMING_IN`
- `HIDDEN_SUPPLY`
- `INCREASING_SUPPLY`
- `SUPPLY_DRYING_UP`
- `UPTHRUST`
- `NO_DEMAND`

Inside `collect_demand()`, these demand-side detectors are active for eligible bars:

- `STOPPING_VOLUME`
- `SELLING_CLIMAX`
- `INCREASING_DEMAND`
- `DEMAND_COMING_IN`
- `TEST`
- `SHAKEOUT`
- `NO_SUPPLY`
- `ABSORPTION`

`collect_spring()` runs separately through `EvidenceEngine.collect()`.

`collect_structural_progression()` is active but is not a raw primary VSA event detector.

## Causality and recognition policy

Most detectors are current-bar events: they emit evidence on the current candidate bar using current, previous, and already-available context.

`SHAKEOUT` and `SPRING` are delayed-recognition events. Their validation may inspect bars after the original candidate, but production collection slices the available metrics through the current recovery/confirmation bar. They are therefore recovery/confirmation-anchored, not candidate-bar look-ahead.

Shared detector confirmations are diagnostic quality observations unless a future PR explicitly promotes a confirmation into a mandatory emission gate.

## Current matrix

| EvidenceCode | Detector / source | Production path | Status | Role | Direction | Scoring / weight state | Notes |
|---|---|---:|---|---|---|---|---|
| `BUYING_CLIMAX` | `evidence/supply.py::_collect_buying_climax` | YES | Production-active / audit-complete | Primary weakness / supply | Bearish | Registry `1.00`; dynamic runtime weight | Campaign-qualified event. Confirmations are non-mandatory. Prior audit found no production penalty or global weight change. |
| `SUPPLY_COMING_IN` | `evidence/supply.py::_collect_supply_coming_in` | YES | Production-active / audit-complete | Primary weakness / supply | Bearish | Registry `1.00`; dynamic runtime weight | Point-in-time production emissions validated. Interaction with `INCREASING_SUPPLY` is documented as outcome-confirming; no production penalty. |
| `INCREASING_SUPPLY` | `evidence/supply.py::_collect_increasing_supply` | YES | Active / audit-complete | Primary weakness / supply | Bearish | Registry/reference `0.85`; configured supply map `0.70`; runtime evidence weight `1.00` | Scoring/ranking sensitivity confirmed. No qualification/actionability change and no interaction penalty. |
| `HIDDEN_SUPPLY` | `evidence/supply.py::_collect_hidden_supply` | YES | Active / audit-complete / non-scoring | Supporting supply | Bearish | Non-scoring audit conclusion | Current detector remains active, but the audited definition is not promoted as standalone scoring evidence. |
| `SUPPLY_DRYING_UP` | `evidence/supply.py::_collect_supply_drying_up` | YES | Active / audit-complete | Supporting / exhaustion context | Contextual | Configured supply-map weight `0.60`; runtime evidence weight observed as context-dependent | Production-valid contextual evidence. No global promotion, interaction penalty, or rejection rule introduced. |
| `UPTHRUST` | `evidence/supply.py::_collect_upthrust` | YES | Production-active / audit-complete | Supply / distribution / trap | Bearish | Registry `1.00`; professional supply-map weight `0.90`; dynamic runtime weight | Mandatory: buying campaign, bullish/up bar, very-high volume, above-average spread. Confirmations are non-mandatory. No production penalty or global weight change. |
| `NO_DEMAND` | `evidence/supply.py::_collect_no_demand` | YES | Production-active / audit-complete | Demand absence / weakness | Bearish | Registry `1.00`; configured supply-map weight `0.60`; dynamic runtime weight | Correct collector is supply-side. Mandatory: bullish environment, bullish/up bar, low volume, narrow spread. Confirmations are non-mandatory. |
| `STOPPING_VOLUME` | `evidence/demand.py::_collect_stopping_volume` | YES | Production-integrated / validation-complete | Primary demand | Bullish | Registry/profile `1.00`; dynamic runtime weight | Canonical spec exists. Confirmations are non-mandatory. Point-in-time validation is complete. |
| `SELLING_CLIMAX` | `evidence/demand.py::_collect_selling_climax` | YES | Production-integrated / audit-complete | Primary demand / reversal | Bullish | Base/scoring reference `0.38`; dynamic runtime weight | Post-integration audit validated production emissions and no score mutation failure. Interaction with `STOPPING_VOLUME` is confirming. |
| `INCREASING_DEMAND` | `evidence/demand.py::_collect_increasing_demand` | YES | Provisional / audit-complete | Primary demand | Bullish | Base/reference `0.85`; provisional conflict penalty `0.10` remains study-only | Production-connected and calibrated, but conflict penalty is not active production scoring unless promoted by a later PR. |
| `DEMAND_COMING_IN` | `evidence/demand_coming_in.py::collect_demand_coming_in` | YES | Provisional / audit-complete | Primary demand | Bullish | Base/reference `0.38`; no production conflict penalty | Production path validated. Not yet promoted to fully production-approved status. |
| `TEST` | `evidence/demand.py::_collect_test` | YES | Production-integrated / frozen semantics | Primary confirmation | Bullish | Non-scoring contextual role | Canonical spec exists. Contextual confirmation only; no score weight promotion. |
| `SHAKEOUT` | `evidence/demand.py::_collect_shakeout` and `evidence/campaign.py::validate_shakeout` | YES | Production-integrated / validation-complete | Primary reversal / demand | Bullish | Base/reference `0.50` | Recovery-anchored event. Candidate requires selling pressure, bearish/down bar, wide spread, very-high volume, lower low, valid test, and valid recovery. |
| `NO_SUPPLY` | `evidence/demand.py::_collect_no_supply` | YES | Production-active / audit-complete / contextual-non-scoring | Demand absence / weakness | Bullish | Registry `1.00`; no professional scoring-map entry; dynamic runtime weight | Canonical spec exists. Source requirement label says `Bullish Environment` but production predicate uses `ctx.is_bearish_environment()`. This naming mismatch is documented and unchanged. |
| `ABSORPTION` | `evidence/absorption.py::collect_absorption` | YES | Production-connected / non-scoring / frozen | Effort/result / absorption | Bullish/contextual | Production scoring weight `0.00`; empirical `0.38` and conflict penalty `0.20` are research-only | Collected through `EvidenceEngine.collect -> collect_demand -> collect_absorption`. It is connected but non-scoring; this replaces older stale no-production-path wording. |
| `SPRING` | `evidence/spring.py::collect_spring` | YES | Production-integrated / provisional | Primary trap / reversal | Bullish | Base/reference `0.75` | Confirmation-anchored event. Same-bar `UPTHRUST` or `BUYING_CLIMAX` reduces Spring quality instead of rejecting the event. |
| `HIDDEN_DEMAND` | No dedicated active production detector | NO | Audit-complete / non-scoring | Supporting demand | Bullish | `0.00` audit conclusion | Current candidate definition was not promoted into production scoring or collection. |
| `DEMAND_DRYING_UP` | No dedicated active production detector | NO | Audit-complete / contextual-non-scoring | Supporting / exhaustion context | Contextual | `0.00` audit conclusion | Current candidate definition remains contextual/non-scoring and is not promoted into production collection. |
| `EFFORT_GT_RESULT` | `evidence/effort.py` | Disabled engine invocation | Present / inactive in production collection | Effort/result context | Neutral | None | Separate analytical layer; `EvidenceEngine.collect()` does not currently invoke `_collect_effort()`. |
| `RESULT_GT_EFFORT` | `evidence/effort.py` | Disabled engine invocation | Present / inactive in production collection | Effort/result context | Neutral | None | Separate analytical layer; `EvidenceEngine.collect()` does not currently invoke `_collect_effort()`. |
| `EFFORT_RESULT` | No dedicated active detector | NO | Candidate | Effort/result context | Neutral | None | Needs one canonical representation if retained. |
| `SUPPLY_ABSORPTION` | Commented / inactive detector concept | NO | Candidate | Supply absorption | Contextual | None | Do not implement until semantics are frozen. |
| `SUPPLY_HIGH_VOLUME` | Commented / inactive detector concept | NO | Candidate descriptor | Supply descriptor | Bearish | None | Descriptive rather than standalone primary evidence. |
| `SUPPLY_WIDE_SPREAD` | Commented / inactive detector concept | NO | Candidate descriptor | Supply descriptor | Bearish | None | Descriptive rather than standalone primary evidence. |
| `STRUCTURAL_PROGRESSION_IMPROVING` | `background/structural_progression.py` | YES | Active | Structural context | Bullish | Separate layer | Active background evidence, not a raw primary VSA event. |
| `STRUCTURAL_PROGRESSION_WEAKENING` | `background/structural_progression.py` | YES | Active | Structural context | Bearish | Separate layer | Active background evidence, not a raw primary VSA event. |

## Explicit corrections from the prior matrix

### ABSORPTION

Older matrix language said `ABSORPTION` had no dedicated production detector, no production path, no registry entry, or no collector. That wording is stale.

Current policy:

```text
ABSORPTION status = PRODUCTION-CONNECTED / NON-SCORING / FROZEN
```

This does not promote its empirical audit weight into production scoring. `0.38` and the `0.20` conflict penalty remain research/counterfactual values only.

### NO_DEMAND

Older audit summary text listed the collector as `evidence/demand.py::_collect_no_demand` / `collect_demand`. That was a documentation-path typo.

Current policy:

```text
NO_DEMAND collector = evidence/supply.py::_collect_no_demand
NO_DEMAND collection path = EvidenceEngine.collect -> collect_supply -> _collect_no_demand
```

## Promotion policy

An event is not production-approved merely because an audit found a positive empirical return, hit-rate lift, or provisional weight. Production promotion requires:

1. A dedicated detector or explicit production collection path.
2. Causal, point-in-time recognition semantics.
3. Source-level tests or replay tests proving no look-ahead leakage.
4. Outcome validation across sufficient symbols/history.
5. Interaction/conflict review.
6. Scoring/ranking impact review.
7. A separate PR that explicitly changes production scoring or detection behavior.

## Related documents

- `audit/vsa_events.py`
- `docs/vsa_event_causality_audit_policy.md`
- `docs/vsa_event_docs_consistency_audit.md`
- `docs/specifications/001_stopping_volume.md`
- `docs/specifications/002_shakeout.md`
- `docs/specifications/003_test.md`
- `docs/specifications/004_spring.md`
- `docs/specifications/005_no_supply.md`
- `docs/ABSORPTION_AUDIT.md`
- `docs/NO_DEMAND_AUDIT.md`
- `docs/UPTHRUST_AUDIT.md`
- `docs/BUYING_CLIMAX_AUDIT.md`
- `docs/DEMAND_COMING_IN_AUDIT.md`
- `docs/INCREASING_DEMAND_AUDIT.md`
- `docs/SUPPLY_COMING_IN_AUDIT.md`
