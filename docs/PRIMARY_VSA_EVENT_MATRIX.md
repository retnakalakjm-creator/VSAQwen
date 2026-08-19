# Primary VSA Event Matrix

This document is the production-coverage inventory for the VSA event layer on `main`.

It is a specification/diagnostic artifact only. It does not itself change detector logic, evidence weights, qualification rules, or scanner behavior.

## Canonical event specifications

The `docs/specifications/` directory is the canonical per-event rulebook. A per-event specification is created only after its semantics, validation evidence, and production status are sufficiently frozen.

Current canonical specifications:

- `001_stopping_volume.md` — production-integrated / validation-complete.
- `002_shakeout.md` — production-integrated / validation-complete.
- `003_test.md` — production-integrated contextual confirmation / non-scoring.
- `004_spring.md` — production-integrated / provisional.
- `005_no_supply.md` — contextual / validation-complete for its current non-scoring role.

## Production collection path

`EvidenceEngine.collect()` currently invokes:

- `collect_supply()`
- `collect_demand()`
- `collect_spring()`
- `collect_structural_progression()`

Inside `collect_supply()`, these detectors are active for eligible bars:

- `BUYING_CLIMAX`
- `SUPPLY_COMING_IN`
- `HIDDEN_SUPPLY`
- `INCREASING_SUPPLY`
- `SUPPLY_DRYING_UP`
- `UPTHRUST`
- `NO_DEMAND`

Inside `collect_demand()`, the validated demand-side detectors now include `STOPPING_VOLUME`, `SHAKEOUT`, `NO_SUPPLY`, `TEST`, `DEMAND_COMING_IN`, and `INCREASING_DEMAND`. `SELLING_CLIMAX` remains disabled. `TEST` and `NO_SUPPLY` remain non-scoring/contextual in their defined roles.

## Matrix

| EvidenceCode | Detector / source | Production path | Status | Role | Direction | Base weight | Notes |
|---|---|---:|---|---|---|---:|---|
| `BUYING_CLIMAX` | `evidence/supply.py::_collect_buying_climax` | YES | Active | Primary weakness / supply | Bearish | Existing | Buying campaign + bullish bar + very-high volume + above-average spread; confirmations include wide spread, weak close, increasing volume. |
| `SUPPLY_COMING_IN` | `evidence/supply.py::_collect_supply_coming_in` | YES | Active | Primary weakness / supply | Bearish | Existing | Down bar + high volume + above-average spread + weak close + increasing volume. |
| `INCREASING_SUPPLY` | `evidence/supply.py::_collect_increasing_supply` | YES | Active | Primary weakness / supply | Bearish | Existing | Down bar + increasing volume + increasing spread. |
| `HIDDEN_SUPPLY` | `evidence/supply.py::_collect_hidden_supply` | YES | Active | Supporting supply | Bearish | Existing | Up bar + high volume + lower close. |
| `SUPPLY_DRYING_UP` | `evidence/supply.py::_collect_supply_drying_up` | YES | Active | Supporting / exhaustion context | Contextual | Existing | Observation only; should not automatically be treated as stronger bearish pressure. |
| `UPTHRUST` | `evidence/supply.py::_collect_upthrust` | YES | Active | Primary trap / supply | Bearish | Existing | Buying campaign + bullish bar + very-high volume + above-average spread; confirmations include wide spread, weak close, lower close than previous. |
| `NO_DEMAND` | `evidence/supply.py::_collect_no_demand` | YES | Active | Demand absence / weakness | Bearish | Existing | Semantically demand-absence evidence, currently collected by the supply module. |
| `SHAKEOUT` | `evidence/demand.py::_collect_shakeout` | YES | Production-integrated / validation-complete | Primary reversal / demand | Bullish | 0.50 | Recovery-anchored event. Candidate requires selling pressure + bearish bar + wide spread + very-high volume + lower low; valid TEST and bullish recovery are required. |
| `NO_SUPPLY` | `evidence/demand.py::_collect_no_supply` | YES | Contextual / validation-complete | Demand-absence context | Bullish | 0.00 | Frozen as a contextual demand-absence probe; no standalone demand pressure or actionability. |
| `STOPPING_VOLUME` | `evidence/demand.py::_collect_stopping_volume` | YES | Production-integrated / validation-complete | Primary demand | Bullish | 1.00 | 59-event point-in-time validation across 8 symbols; 73.58% positive decisive rate. |
| `DEMAND_COMING_IN` | `evidence/demand.py::_collect_demand_coming_in` | YES | **Provisional / audit-complete** | Primary demand | Bullish | **0.38** | Production-path audit: 281 candidate events; all validated production emissions observed at 0.38. Interaction audit found no production conflict penalty. Weight remains provisional and is not yet promoted to production-approved status. |
| `INCREASING_DEMAND` | `evidence/demand.py::_collect_increasing_demand` | YES | **Provisional / audit-complete** | Primary demand | Bullish | **0.85** | 902-point-in-time-event calibration across 8 symbols. Leave-one-symbol-out calibration remained positive. Conflict audit identified a 4.55% same-bar supply-conflict rate; conflict penalty **0.10** is provisional and is not yet an active production scoring rule. |
| `HIDDEN_DEMAND` | No dedicated active production detector | NO | Candidate / missing | Supporting demand | Bullish | — | Requires explicit detector specification and audit campaign. |
| `DEMAND_DRYING_UP` | No dedicated active production detector | NO | Candidate / missing | Supporting / exhaustion context | Contextual | — | Must remain distinct from bearish absence-of-demand evidence. |
| `SELLING_CLIMAX` | `evidence/demand.py::_collect_selling_climax` | NO | Audit-complete / frozen | Primary demand / reversal | Bullish | — | Detector exists but remains disabled; audit did not establish a defensible production weight. |
| `TEST` | `evidence/demand.py::_collect_test` | YES | Production-integrated / frozen semantics | Primary confirmation | Bullish | 0.00 | Contextual confirmation only; non-scoring. 47 validated events across 8 symbols. |
| `SPRING` | `evidence/spring.py::collect_spring` | YES | Production-integrated / provisional | Primary trap / reversal | Bullish | 0.75 | Strict point-in-time candidate → low-volume test → bullish follow-through. Same-bar `UPTHRUST`/`BUYING_CLIMAX` reduces Spring quality to 0.50 rather than rejecting it. |
| `ABSORPTION` | No dedicated production detector | NO | Candidate | Effort/result / absorption | Contextual | — | Must have one canonical production detector before scoring. |
| `EFFORT_GT_RESULT` | `evidence/effort.py` | Disabled engine invocation | Present | Effort/result context | Neutral | — | Separate analytical layer. |
| `RESULT_GT_EFFORT` | `evidence/effort.py` | Disabled engine invocation | Present | Effort/result context | Neutral | — | Separate analytical layer. |
| `EFFORT_RESULT` | No dedicated active detector | NO | Candidate | Effort/result context | Neutral | — | Needs one canonical representation if retained. |
| `SUPPLY_ABSORPTION` | Commented detector block | NO | Candidate | Supply absorption | Contextual | — | Do not implement until semantics are frozen. |
| `SUPPLY_HIGH_VOLUME` | Commented detector block | NO | Candidate | Supply descriptor | Bearish | — | Descriptive rather than standalone primary evidence. |
| `SUPPLY_WIDE_SPREAD` | Commented detector block | NO | Candidate | Supply descriptor | Bearish | — | Descriptive rather than standalone primary evidence. |
| `STRUCTURAL_PROGRESSION_IMPROVING` | `background/structural_progression.py` | YES | Active | Structural context | Bullish | Separate layer | Not a raw primary VSA event. |
| `STRUCTURAL_PROGRESSION_WEAKENING` | `background/structural_progression.py` | YES | Active | Structural context | Bearish | Separate layer | Not a raw primary VSA event. |

## DEMAND_COMING_IN audit record

### Frozen audited semantics

The audited event is bullish demand evidence defined point-in-time by the validated detector semantics used in the audit campaign.

Production-path validation:

- candidate events: `281`
- production emissions: validated
- emitted weight: `[0.38]`
- symbols with production hits: `8 / 8`
- production path: `TARGET_COLLECTED_AND_WEIGHTED_038`

Decision-value audit:

- candidate positive decisive rate: `66.19%`
- eligible-market positive decisive rate: `60.68%`
- lift: `+5.52` percentage points
- candidate share of eligible events: `2.51%`

Weight-sensitivity audit showed controlled decision impact. At weight `0.38`, bias changed on `12 / 281` events (`4.27%`), with no uncontrolled explosion in bullish classifications.

Final qualification audit did not justify production promotion: the 12 bias-changing events had stronger mean return magnitude but lower positive hit rate than unchanged events. Therefore the event remains provisional.

Interaction audit found no meaningful conflict penalty requirement. No rejection rule was justified.

### Scoring decision

```text
DEMAND_COMING_IN = 0.38   # provisional
conflict_penalty = 0.00   # no penalty established
rejection = NO
```

## INCREASING_DEMAND audit record

### Frozen audited semantics

`INCREASING_DEMAND` is the validated point-in-time demand detector used by the current production path. Its audited mandatory conditions are:

1. Bullish bar.
2. High volume.
3. Above-average spread.
4. Increasing volume versus the previous bar.

The audit deliberately preserves imperfect but meaningful real-market VSA evidence rather than imposing textbook-only conformity.

Production-path validation:

- production hits: `905`
- symbols with production hits: `8 / 8`
- observed emitted weights: `[0.85]`
- registry weight: `0.85`

Calibration record:

- point-in-time calibration population: `902`
- beneficial decision changes: `26`
- harmful decision changes: `15`
- net benefit: `+11`
- benefit/harm ratio: `1.7333`
- leave-one-symbol-out minimum net benefit: `+6`

Interaction audit:

- conflict population: `41 / 902`
- conflict rate: `4.55%`
- hidden supply-like conflicts: `41`
- buying-climax-like conflicts: `16`
- upthrust-like conflicts: `1`
- supply-coming-in-like conflicts: `0`
- increasing-supply-like conflicts: `0`
- no-demand-like conflicts: `0`

Conflict outcome audit:

- usable demand events: `899`
- conflict events: `41`
- clean events: `858`
- conflict mean return: `+0.72%`
- clean mean return: `+3.83%`
- mean-return gap: `-3.11` percentage points
- conflict positive rate: `51.22%`
- clean positive rate: `59.44%`
- positive-rate gap: `-8.22` percentage points

Penalty-sensitivity audit recommended a provisional `0.10` penalty. This implies an effective conflict-event weight of:

```text
0.85 * (1.00 - 0.10) = 0.765
```

The penalty is an **audit decision only** at this stage; it has not been promoted into the production scoring path by this document update.

### Scoring decision

```text
INCREASING_DEMAND = 0.85       # provisional base weight
conflict_penalty = 0.10        # provisional audit policy
rejection = NO
```

## Project-wide audit policy for these events

The project treats interaction results as evidence-quality information, not automatic detector invalidation. A contradictory observation reduces confidence/quality only when the historical outcome audit shows a repeatable deterioration, and rejection requires materially stronger evidence than a modest conflict association.

The current `DEMAND_COMING_IN` and `INCREASING_DEMAND` audit campaigns therefore freeze provisional weights and interaction findings separately from production approval.

## Immediate conclusions

1. `STOPPING_VOLUME`, `SHAKEOUT`, `TEST`, and `NO_SUPPLY` have their established production/contextual roles.
2. `SPRING` remains production-integrated but provisional at base weight `0.75`.
3. `DEMAND_COMING_IN` is production-connected at base weight `0.38`, but remains provisional.
4. `INCREASING_DEMAND` is production-connected at base weight `0.85`, but remains provisional.
5. `INCREASING_DEMAND` has a provisional interaction penalty of `0.10`; no rejection rule is justified.
6. Neither new demand event is promoted to fully production-approved status by these audit results.
7. Future evidence events must follow the same audit-first process rather than inheriting weights or interaction penalties automatically.
