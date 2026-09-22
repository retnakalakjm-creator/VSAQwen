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
| `BUYING_CLIMAX` | `evidence/supply.py::_collect_buying_climax` | YES | Production-active / promoted semantics | Primary weakness / supply | Bearish | Registry `1.00`; dynamic runtime weight | Promoted contract keeps buying-campaign + bullish-bar + very-high-volume + above-average-spread effort core and requires non-strong high-price acceptance (`close_position` not `UPPER`/`ON_HIGH`). Frozen post-change target: 887 events. |
| `SUPPLY_COMING_IN` | `evidence/supply.py::_collect_supply_coming_in` | YES | Target-bar detector semantics frozen / M12 PARKED; scoring architecture unchanged | Primary weakness / supply | Bearish | Registry `1.00`; empirical reference `0.38`; dynamic runtime weight | M12 retained the six-clause identity including mandatory buying-campaign context, confirmed distinctness from `INCREASING_SUPPLY`, found no confirmation-layer issue, and found no target-bar detector correction. Production emission remains unchanged. |
| `INCREASING_SUPPLY` | `evidence/supply.py::_collect_increasing_supply` | YES | Detector semantics frozen / M12 PARKED; scoring architecture unchanged | Primary weakness / supply | Bearish | Registry/reference `0.85`; configured supply map `0.70`; runtime evidence weight `1.00` | M12 retained the three-clause relative-expansion identity, confirmed distinctness from `SUPPLY_COMING_IN`, found no confirmation-layer issue, and found no obvious detector correction. Production emission remains unchanged. |
| `HIDDEN_SUPPLY` | `evidence/supply.py::_collect_hidden_supply` | YES | Detector semantics frozen / M12 PARKED; standalone scoring not promoted | Supporting supply | Bearish | No dedicated professional supply-map weight; supporting evidence remains collected | M12 retained the three-clause current-bar identity (up bar + high volume + lower close), confirmed distinctness from neighboring supply detectors, found no confirmation-layer issue, and found no obvious detector correction. Production emission remains unchanged. |
| `SUPPLY_DRYING_UP` | `evidence/supply.py::_collect_supply_drying_up` | YES | Detector semantics frozen / M12 PARKED; scoring architecture unchanged | Supporting / exhaustion context | Bullish/contextual | Registry/profile `0.90`; configured supply-map `0.60`; runtime evidence weight `1.00` by default calculator path | M12 retained the three-clause low-effort selling identity, confirmed its intentional nested relationship with `NO_SUPPLY`, found no confirmation-layer issue, and found no obvious detector correction. Production emission remains unchanged. |
| `UPTHRUST` | `evidence/supply.py::_collect_upthrust` | YES | Production-active / promoted semantics | Supply / distribution / trap | Bearish | Registry `1.00`; professional supply-map weight `0.90`; dynamic runtime weight | Promoted contract is a probe above the latest causally confirmed structural swing high followed by a close back at/below that high. Old bullish-bar/very-high-volume identity gates are removed; they remain descriptive context. Frozen post-change target: 10,526 events. |
| `NO_DEMAND` | `evidence/supply.py::_collect_no_demand` | YES | Detector semantics frozen / M12 PARKED; scoring architecture unchanged | Demand absence / weakness | Bearish | Registry `1.00`; configured supply-map weight `0.60`; dynamic runtime weight | M12 retained the four-clause identity, confirmed distinctness from other low-effort signals, verified `Volume Decreasing` and `Weak Close` remain diagnostic/non-gating, and found no obvious detector correction. Production emission remains unchanged. |
| `STOPPING_VOLUME` | `evidence/demand.py::_collect_stopping_volume` | YES | Detector semantics frozen / M12 PARKED; production-active | Primary demand | Bullish | Profile `1.00`; professional demand-map `1.00`; emitted `Evidence.weight` `1.00` via default calculator path | M12 retained the five-clause stopping/absorption identity, confirmed distinctness from `SELLING_CLIMAX`, verified all four confirmations remain diagnostic/non-gating, and found no obvious detector correction. Production emission remains unchanged. |
| `SELLING_CLIMAX` | `evidence/demand.py::_collect_selling_climax` | YES | Detector semantics frozen / M12 PARKED; production-active | Primary demand / reversal | Bullish | Profile/emitted `Evidence.weight` `0.38`; no M12 weight change | M12 retained the four-clause climactic-effort identity, confirmed distinctness from `STOPPING_VOLUME`, verified `Wide Spread`, `Strong Close`, and `Increasing Volume` remain diagnostic/non-gating, and found no obvious detector correction. Production emission remains unchanged. |
| `INCREASING_DEMAND` | `evidence/demand.py::_collect_increasing_demand` | YES | Detector semantics frozen / M12 PARKED; scoring provisional | Primary demand | Bullish | Base/reference `0.85`; provisional conflict penalty `0.10` remains study-only | M12 stop-rule review retained the four-clause production identity, confirmed distinctness from `DEMAND_COMING_IN`, found no confirmation-layer issue, and found no obvious detector correction. Production emission remains unchanged. |
| `DEMAND_COMING_IN` | `evidence/demand_coming_in.py::collect_demand_coming_in` | YES | Detector semantics frozen / M12 PARKED; scoring frozen provisional | Primary demand | Bullish | Base/reference `0.38`; no production conflict penalty | M12 stop-rule review retained the four-clause production identity, confirmed distinctness from `INCREASING_DEMAND`, found no confirmation-layer issue, and found no obvious detector correction. Production emission remains unchanged. |
| `TEST` | `evidence/demand.py::_collect_test` | YES | Production-integrated / frozen semantics | Primary confirmation | Bullish | Non-scoring contextual role | Canonical spec exists. Contextual confirmation only; no score weight promotion. |
| `SHAKEOUT` | `evidence/demand.py::_collect_shakeout` and `evidence/campaign.py::validate_shakeout` | YES | Detector semantics frozen / M12 PARKED; production-active | Primary reversal / demand | Bullish | Profile `1.00`; professional demand-map `0.50`; emitted runtime weight dynamic via quality/context | M12 retained the recovery-anchored candidate→TEST→recovery identity, verified candidate-time campaign/structure causality and current-recovery anchoring, found no production detector correction, and corrected stale spec wording about unused recovery count settings. Production emission remains unchanged. |
| `NO_SUPPLY` | `evidence/demand.py::_collect_no_supply` | YES | Production-active / audit-complete / contextual-non-scoring | Demand absence / weakness | Bullish | Registry `1.00`; no professional scoring-map entry; dynamic runtime weight | Canonical spec exists. Source requirement label says `Bullish Environment` but production predicate uses `ctx.is_bearish_environment()`. This naming mismatch is documented and unchanged. |
| `ABSORPTION` | `evidence/absorption.py::collect_absorption` | YES | Production-connected / non-scoring / frozen | Effort/result / absorption | Bullish/contextual | Production scoring weight `0.00`; empirical `0.38` and conflict penalty `0.20` are research-only | Collected through `EvidenceEngine.collect -> collect_demand -> collect_absorption`. It is connected but non-scoring; this replaces older stale no-production-path wording. |
| `SPRING` | `evidence/spring.py::collect_spring` | YES | Detector semantics frozen / M12 causality corrected; scoring provisional | Primary trap / reversal | Bullish | Base/reference `0.75` | Candidate-time structural causality corrected and frozen: support lows must be confirmed by the candidate bar. Frozen 30-symbol replay changed Spring only (254 -> 309; +55), with exact non-Spring parity. Same-bar `UPTHRUST` or `BUYING_CLIMAX` still reduces Spring quality instead of rejecting the event. |
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
- `docs/DAILY_EVENT_STOPPING_VOLUME_DETECTOR_VERDICT.md`
- `docs/specifications/002_shakeout.md`
- `docs/DAILY_EVENT_SHAKEOUT_DETECTOR_VERDICT.md`
- `docs/specifications/003_test.md`
- `docs/specifications/004_spring.md`
- `docs/DAILY_EVENT_SPRING_CANDIDATE_CAUSALITY_CORRECTION.md`
- `docs/specifications/005_no_supply.md`
- `docs/ABSORPTION_AUDIT.md`
- `docs/SELLING_CLIMAX_PRODUCTION_RECORD.md`
- `docs/DAILY_EVENT_SELLING_CLIMAX_DETECTOR_VERDICT.md`
- `docs/NO_DEMAND_AUDIT.md`
- `docs/DAILY_EVENT_NO_DEMAND_DETECTOR_VERDICT.md`
- `docs/UPTHRUST_AUDIT.md`
- `docs/BUYING_CLIMAX_AUDIT.md`
- `docs/DEMAND_COMING_IN_AUDIT.md`
- `docs/DAILY_EVENT_DEMAND_COMING_IN_DETECTOR_VERDICT.md`
- `docs/INCREASING_DEMAND_AUDIT.md`
- `docs/DAILY_EVENT_INCREASING_DEMAND_DETECTOR_VERDICT.md`
- `docs/SUPPLY_COMING_IN_AUDIT.md`
- `docs/DAILY_EVENT_SUPPLY_COMING_IN_DETECTOR_VERDICT.md`
- `docs/DAILY_EVENT_HIDDEN_SUPPLY_DETECTOR_VERDICT.md`
- `docs/INCREASING_SUPPLY_AUDIT.md`
- `docs/DAILY_EVENT_INCREASING_SUPPLY_DETECTOR_VERDICT.md`
- `docs/SUPPLY_DRYING_UP_AUDIT.md`
- `docs/DAILY_EVENT_SUPPLY_DRYING_UP_DETECTOR_VERDICT.md`


## BUYING_CLIMAX / UPTHRUST production-correction policy

M12 established and then closed the semantic-collision research thread.

Canonical pre-change state:

    BUYING_CLIMAX     4,497
    UPTHRUST          4,497
    overlap           4,497

Final promoted semantics:

    BUYING_CLIMAX
        climactic buying effort
        +
        non-strong high-price acceptance

    UPTHRUST
        probe above latest causally confirmed structural swing high
        +
        close back at/below that high

Frozen production-parity targets:

    BUYING_CLIMAX       887
    UPTHRUST         10,526
    overlap             129

Post-merge policy:

    promoted semantic contracts are active on main
    frozen replay matched the promoted candidates exactly
    non-target emission drift was zero
    Spring-only downstream quality changes were fully explained
    contribution impact was reviewed
    DailyBehavior mapping remains unchanged

See:

    docs/DAILY_EVENT_BC_UPTHRUST_PRODUCTION_CORRECTION.md

