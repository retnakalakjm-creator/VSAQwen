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

Inside `collect_demand()`, the validated demand-side detectors now include `STOPPING_VOLUME`, `SHAKEOUT`, `NO_SUPPLY`, `TEST`, `DEMAND_COMING_IN`, and `INCREASING_DEMAND`. `SELLING_CLIMAX` is production-integrated at base weight `0.38`. `TEST` and `NO_SUPPLY` remain non-scoring/contextual in their defined roles.

`HIDDEN_DEMAND`, `DEMAND_DRYING_UP`, and `ABSORPTION` are not connected to the production collection path.

## Matrix

| EvidenceCode | Detector / source | Production path | Status | Role | Direction | Base weight | Notes |
|---|---|---:|---|---|---|---:|---|
| `BUYING_CLIMAX` | `evidence/supply.py::_collect_buying_climax` | YES | **Production-active / audit-complete** | Primary weakness / supply | Bearish | **Registry 1.00 / dynamic runtime** | Campaign-qualified production path verified: 181 emissions across 8 symbols, matching 181 expected campaign events; 0 duplicates, 0 campaign mismatches, 0 runtime-weight bound violations, and 0 production score-mutation failures. Runtime weights are calculated dynamically by `WeightCalculator`; observed distribution was 0.9–2.0. Empirical reference weight `0.38` is calibration-only and is not the production runtime weight. |
| `SUPPLY_COMING_IN` | `evidence/supply.py::_collect_supply_coming_in` | YES | **Production-active / audit-complete** | Primary weakness / supply | Bearish | **Registry 1.00 / dynamic runtime** | Production path verified: 189/189 expected emissions across 8 symbols; 0 campaign mismatches, 0 expected-event mismatches, 0 duplicates, 0 runtime-weight violations, 0 calculator/emission weight mismatches, and 0 production score mutation. Runtime weights observed 0.70–1.70. Empirical reference `0.38` is calibration-only. `INCREASING_SUPPLY` overlaps 147/189 events (77.78%) and is outcome-confirming; no interaction penalty is justified. |
| `INCREASING_SUPPLY` | `evidence/supply.py::_collect_increasing_supply` | YES | Active | Primary weakness / supply | Bearish | Existing | Down bar + increasing volume + increasing spread. |
| `HIDDEN_SUPPLY` | `evidence/supply.py::_collect_hidden_supply` | YES | **Active / audit-complete / non-scoring** | Supporting supply | Bearish | Existing | Candidate audit: 139 events, 58.99% positive decisive rate, +2.78% mean 8-bar return. Semantic-quality audit: 0 failures; all 139 had high volume and lower close semantics. Corrected interaction audit found no same-bar supply/demand conflicts after excluding self-conflict. Decision-value audit: positive-rate lift −1.81 pp and mean-return lift −1.05 pp versus eligible market. Current detector remains active, but the audited definition is not promoted as incremental scoring evidence. |
| `SUPPLY_DRYING_UP` | `evidence/supply.py::_collect_supply_drying_up` | YES | Active | Supporting / exhaustion context | Contextual | Existing | Observation only; should not automatically be treated as stronger bearish pressure. |
| `UPTHRUST` | `evidence/supply.py::_collect_upthrust` | YES | Active | Primary trap / supply | Bearish | Existing | Buying campaign + bullish bar + very-high volume + above-average spread; confirmations include wide spread, weak close, lower close than previous. |
| `NO_DEMAND` | `evidence/supply.py::_collect_no_demand` | YES | Active | Demand absence / weakness | Bearish | Existing | Semantically demand-absence evidence, currently collected by the supply module. |
| `SHAKEOUT` | `evidence/demand.py::_collect_shakeout` | YES | Production-integrated / validation-complete | Primary reversal / demand | Bullish | 0.50 | Recovery-anchored event. Candidate requires selling pressure + bearish bar + wide spread + very-high volume + lower low; valid TEST and bullish recovery are required. |
| `NO_SUPPLY` | `evidence/demand.py::_collect_no_supply` | YES | Contextual / validation-complete | Demand-absence context | Bullish | 0.00 | Frozen as a contextual demand-absence probe; no standalone demand pressure or actionability. |
| `STOPPING_VOLUME` | `evidence/demand.py::_collect_stopping_volume` | YES | Production-integrated / validation-complete | Primary demand | Bullish | 1.00 | 59-event point-in-time validation across 8 symbols; 73.58% positive decisive rate. |
| `DEMAND_COMING_IN` | `evidence/demand.py::_collect_demand_coming_in` | YES | **Provisional / audit-complete** | Primary demand | Bullish | **0.38** | Production-path audit: 281 candidate events; all validated production emissions observed at 0.38. Interaction audit found no production conflict penalty. Weight remains provisional and is not yet promoted to production-approved status. |
| `INCREASING_DEMAND` | `evidence/demand.py::_collect_increasing_demand` | YES | **Provisional / audit-complete** | Primary demand | Bullish | **0.85** | 902-point-in-time-event calibration across 8 symbols. Leave-one-symbol-out calibration remained positive. Conflict audit identified a 4.55% same-bar supply-conflict rate; conflict penalty **0.10** is provisional and is not yet an active production scoring rule. |
| `HIDDEN_DEMAND` | No dedicated active production detector | NO | **Audit-complete / non-scoring** | Supporting demand | Bullish | **0.00** | Candidate population: 136 events across 8 symbols. Positive decisive rate 58.82% versus eligible-market 60.68% (−1.86 pp lift); mean-return lift −0.82 pp. Supply-conflict rate 29.41%, entirely `INCREASING_SUPPLY_LIKE`; conflict positive rate was 60.00% versus 58.33% clean, so no conflict penalty or rejection rule is justified. Not promoted into scoring. |
| `DEMAND_DRYING_UP` | No dedicated active production detector | NO | **Audit-complete / non-scoring** | Supporting / exhaustion context | Contextual | **0.00** | Candidate population: 1,068 events across 8 symbols. Positive decisive rate 57.73% versus eligible-market 60.68% (−2.95 pp lift); mean-return lift −0.53 pp. Semantic quality was consistent: both volume and spread declined on all candidates; higher low 81.7%; narrow/average spread 86.7%. Supply-overlap rate 15.36%, driven by `NO_DEMAND_LIKE` (136) and `BUYING_CLIMAX_LIKE` (28). Conflict positive rate 56.10% versus 58.03% clean, so no conflict penalty or rejection rule is justified. Retained as contextual/non-scoring evidence only. |
| `SELLING_CLIMAX` | `evidence/demand.py::_collect_selling_climax` | YES | Production-integrated / audit-complete | Primary demand / reversal | Bullish | `0.38` | Post-integration audit: 153 production emissions; all emitted at 0.38; zero wrong weights, duplicate emissions, campaign mismatches, and score-mutation failures. `STOPPING_VOLUME` interaction is confirming; no conflict penalty established. |
| `TEST` | `evidence/demand.py::_collect_test` | YES | Production-integrated / frozen semantics | Primary confirmation | Bullish | 0.00 | Contextual confirmation only; non-scoring. 47 validated events across 8 symbols. |
| `SPRING` | `evidence/spring.py::collect_spring` | YES | Production-integrated / provisional | Primary trap / reversal | Bullish | 0.75 | Strict point-in-time candidate → low-volume test → bullish follow-through. Same-bar `UPTHRUST`/`BUYING_CLIMAX` reduces Spring quality to 0.50 rather than rejecting it. |
| `ABSORPTION` | No dedicated production detector | NO | **Audit-complete / provisional** | Effort/result / absorption | Contextual | **0.38** | 68 candidate events; 64.71% positive decisive rate. `INCREASING_SUPPLY_LIKE` conflict in 37/68 events (54.41%) materially degraded outcomes; provisional conflict penalty `0.20`. Decision-value lift +4.02 pp on positive rate, but mean-return lift −0.71 pp. No production collector, engine path, registry entry, or score mutation. |
| `EFFORT_GT_RESULT` | `evidence/effort.py` | Disabled engine invocation | Present | Effort/result context | Neutral | — | Separate analytical layer. |
| `RESULT_GT_EFFORT` | `evidence/effort.py` | Disabled engine invocation | Present | Effort/result context | Neutral | — | Separate analytical layer. |
| `EFFORT_RESULT` | No dedicated active detector | NO | Candidate | Effort/result context | Neutral | — | Needs one canonical representation if retained. |
| `SUPPLY_ABSORPTION` | Commented detector block | NO | Candidate | Supply absorption | Contextual | — | Do not implement until semantics are frozen. |
| `SUPPLY_HIGH_VOLUME` | Commented detector block | NO | Candidate | Supply descriptor | Bearish | — | Descriptive rather than standalone primary evidence. |
| `SUPPLY_WIDE_SPREAD` | Commented detector block | NO | Candidate | Supply descriptor | Bearish | — | Descriptive rather than standalone primary evidence. |
| `STRUCTURAL_PROGRESSION_IMPROVING` | `background/structural_progression.py` | YES | Active | Structural context | Bullish | Separate layer | Not a raw primary VSA event. |
| `STRUCTURAL_PROGRESSION_WEAKENING` | `background/structural_progression.py` | YES | Active | Structural context | Bearish | Separate layer | Not a raw primary VSA event. |

## BUYING_CLIMAX audit record

### Production semantics

`BUYING_CLIMAX` is a supply-side weakness / climactic event requiring a valid buying campaign context together with:

1. Bullish bar.
2. Very-high volume.
3. Above-average spread.

Additional confirmations include wide spread, weak close, and increasing volume.

The detector deliberately remains faithful to real-market VSA evidence rather than requiring textbook-perfect climactic structure.

### Production-path verification

- symbols requested: `8`
- cheap candidates: `432`
- engine replays: `432`
- expected campaign events: `181`
- production emissions: `181`
- campaign mismatch: `0`
- duplicate emissions: `0`
- runtime weight bounds: `0.50–2.00`
- runtime weights observed: `0.9–2.0`
- runtime weights out of bounds: `0`
- production interaction penalty configured: `NO`
- production score mutation: `NO`
- errors: `0`
- audit status: `PASS`

### Weight provenance

There are three distinct concepts and they must not be conflated:

```text
registry/profile weight       = 1.00
empirical reference weight    = 0.38
production runtime weight     = dynamic
```
Interaction / contradiction audit:

- INCREASING_DEMAND + UPTHRUST = 119 events
- UPTHRUST only                 = 53 events
- other combinations             = 9 events
- positive decisive rate: 57.12% vs 60.79%
- mean 8-bar return:      3.15%  vs 3.83%
- interaction penalty = 0.20
- status              = PROVISIONAL / ANALYSIS-ONLY
- production penalty  = NO

Frozen decision

- production path       = YES
- registry weight       = 1.00
- runtime weight        = dynamic
- empirical reference   = 0.38
- interaction penalty   = 0.20 provisional / non-production
- rejection             = NO
- production mutation   = NO

## HIDDEN_SUPPLY audit record

### Frozen audited semantics

The existing `HIDDEN_SUPPLY` detector is defined point-in-time as:

1. Up/bullish bar.
2. High volume.
3. Lower close / close on low.

The audit preserved the existing semantics and did not add textbook-only spread or campaign requirements.

Candidate / outcome audit:

- candidate events: `139`
- symbols with events: `8 / 8`
- positive outcomes: `82`
- negative outcomes: `57`
- flat outcomes: `0`
- decisive outcomes: `139`
- positive decisive rate: `58.99%`
- mean 8-bar return: `+2.78%`

Semantic-quality audit:

- candidate events: `139`
- high volume: `139 / 139`
- very high volume: `60 / 139`
- lower close: `137 / 139`
- close on low: `2 / 139`
- semantic failures: `0`

Interaction / contradiction audit:

- events: `139`
- supply-conflict events after self-conflict exclusion: `0 / 139`
- supply-conflict rate: `0.00%`
- `SUPPLY_COMING_IN_LIKE`: `0`
- `INCREASING_SUPPLY_LIKE`: `0`
- `UPTHRUST_LIKE`: `0`
- `NO_DEMAND_LIKE`: `0`
- `BUYING_CLIMAX_LIKE`: `0`
- demand interaction events: `0`
- self-conflict excluded: `YES`

The original interaction audit incorrectly counted `HIDDEN_SUPPLY` as a conflict with itself. That was corrected before using the result. Same-bar self-overlap is not considered contradiction.

Decision-value audit:

- candidate positive decisive rate: `58.99%`
- eligible-market positive decisive rate: `60.80%`
- positive-rate lift: `-1.81` percentage points
- candidate mean return: `+2.78%`
- eligible-market mean return: `+3.83%`
- mean-return lift: `-1.05` percentage points
- candidate share of eligible events: `1.22%`

The current `HIDDEN_SUPPLY` definition does not demonstrate incremental decision value over the eligible-market baseline. No positive production score weight is justified from this audit campaign.

### Scoring decision

```text
base weight        = 0.00   # audit conclusion; no incremental scoring value
conflict_penalty   = 0.00
rejection          = NO
status             = AUDIT_COMPLETE / NON_SCORING
production path    = YES
production change  = NO
```

This is not a rejection of the VSA concept or of the existing detector implementation. The current detector remains in the production collection path, but the audited definition is not promoted as additional standalone scoring value.

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

## HIDDEN_DEMAND audit record

### Candidate semantic definition

The audited candidate was the semantic counterpart of the existing `HIDDEN_SUPPLY` structure:

1. Bearish/down bar.
2. High volume.
3. Strong close.

The audit did not add spread or other textbook-only gates beyond this counterpart definition.

Candidate / outcome audit:

- candidate events: `136`
- symbols with events: `8 / 8`
- positive 8-bar outcomes: `80`
- negative 8-bar outcomes: `56`
- flat outcomes: `0`
- positive decisive rate: `58.82%`
- mean 8-bar return: `+2.97%`

Semantic-quality audit:

- events: `136`
- volume increasing: `82`
- higher low: `30`
- non-climactic volume: `66`
- semantic audit failures: `0`

Interaction audit:

- supply-conflict events: `40 / 136`
- conflict rate: `29.41%`
- conflict class: `INCREASING_SUPPLY_LIKE` only (`40`)
- all other audited supply conflict classes: `0`

Conflict outcome audit:

- conflict events: `40`
- clean events: `96`
- conflict positive decisive rate: `60.00%`
- clean positive decisive rate: `58.33%`
- conflict mean return: `-0.34%`
- clean mean return: `+4.34%`
- mean-return gap: `-4.68` percentage points
- positive-rate gap: `+1.67` percentage points

Conflict penalty sensitivity recommended `0.00`; rejection was not justified. The conflict overlap is materially present, but its positive-hit rate is not inferior to clean events, so the project does not convert the structural overlap into a scoring penalty.

Decision-value audit:

- candidate positive decisive rate: `58.82%`
- eligible-market positive decisive rate: `60.68%`
- positive-rate lift: `-1.86` percentage points
- candidate mean return: `+2.97%`
- eligible-market mean return: `+3.78%`
- mean-return lift: `-0.82` percentage points
- candidate share of eligible events: `1.22%`

### Scoring decision

```text
HIDDEN_DEMAND = 0.00
conflict_penalty = 0.00
rejection = NO
status = AUDIT_COMPLETE / NON_SCORING
production_path = NO
```

This is not a rejection of the VSA concept. It is a decision not to promote the current detector candidate into the scoring layer because the audited population did not demonstrate incremental value over the eligible market baseline.

## DEMAND_DRYING_UP audit record

### Candidate semantic definition

The audit-only candidate definition was intentionally narrow and contextual:

1. Bullish/up bar.
2. Volume declining versus the previous bar.
3. Spread declining versus the previous bar.

The event is interpreted as **demand effort drying**, not automatically as bullish or bearish primary evidence, and it remains distinct from bearish `NO_DEMAND`.

Candidate / outcome audit:

- candidate events: `1,068`
- symbols with events: `8 / 8`
- positive 8-bar outcomes: `616`
- negative 8-bar outcomes: `451`
- flat outcomes: `1`
- decisive outcomes: `1,067`
- positive decisive rate: `57.73%`
- mean 8-bar return: `+3.25%`

Semantic-quality audit:

- events: `1,068`
- both volume and spread declining: `1,068 / 1,068`
- higher low: `873 / 1,068` (`81.7%`)
- narrow/average spread: `926 / 1,068` (`86.7%`)
- semantic audit failures: `0`

Interaction audit:

- supply-conflict events: `164 / 1,068`
- conflict rate: `15.36%`
- `NO_DEMAND_LIKE`: `136`
- `BUYING_CLIMAX_LIKE`: `28`
- all other audited supply conflict classes: `0`

The overlap is interpreted primarily as contextual semantic overlap, not automatic contradiction: `DEMAND_DRYING_UP` describes weakening demand effort, while `NO_DEMAND` and `BUYING_CLIMAX` describe stronger weakness/exhaustion conditions.

Conflict outcome audit:

- conflict events: `164`
- clean events: `904`
- conflict positive decisive rate: `56.10%`
- clean positive decisive rate: `58.03%`
- conflict mean return: `+2.57%`
- clean mean return: `+3.37%`
- positive-rate gap: `-1.93` percentage points
- mean-return gap: `-0.80` percentage points

No conflict penalty or rejection rule is justified from this modest outcome deterioration.

Decision-value audit:

- candidate positive decisive rate: `57.73%`
- eligible-market positive decisive rate: `60.68%`
- positive-rate lift: `-2.95` percentage points
- candidate mean return: `+3.25%`
- eligible-market mean return: `+3.78%`
- mean-return lift: `-0.53` percentage points
- candidate share of eligible events: `9.55%`

The broad candidate population does not demonstrate incremental decision value over the eligible-market baseline. Therefore the current definition is retained only as contextual/non-scoring evidence.

### Scoring decision

```text
DEMAND_DRYING_UP = 0.00
conflict_penalty = 0.00
rejection = NO
status = AUDIT_COMPLETE / NON_SCORING
production_path = NO
```

This is not a rejection of the VSA concept itself. It is a decision not to promote the current candidate definition into the scoring layer because its audited outcome does not demonstrate incremental value.

## ABSORPTION audit record

### Candidate semantic definition

The audited `ABSORPTION` candidate was:

1. Down/bearish bar.
2. High volume.
3. Above-average spread.
4. Upper close.
5. Lower low than the previous bar.

Candidate / outcome audit:

- candidate events: `68`
- symbols with events: `8 / 8`
- positive outcomes: `44`
- negative outcomes: `24`
- decisive outcomes: `68`
- positive decisive rate: `64.71%`
- mean 8-bar return: `+3.08%`

Semantic-quality audit:

- upper close: `68 / 68`
- lower low: `68 / 68`
- high volume: `16 / 68`
- wide spread: `16 / 68`
- semantic failures: `0`

Interaction / contradiction audit:

- supply-conflict events: `37 / 68`
- conflict rate: `54.41%`
- conflict class: `INCREASING_SUPPLY_LIKE` only (`37`)
- other audited supply conflict classes: `0`
- demand interaction events: `68 / 68`
- demand interaction class: `STOPPING_VOLUME_LIKE` (`68`)

Conflict outcome audit:

- conflict events: `37`
- clean events: `31`
- conflict positive decisive rate: `59.46%`
- clean positive decisive rate: `70.97%`
- positive-rate gap: `-11.51` percentage points
- conflict mean return: `-0.58%`
- clean mean return: `+7.44%`
- mean-return gap: `-8.02` percentage points

Conflict penalty sensitivity recommended `0.20`; rejection was **not** justified.

Decision-value audit:

- candidate positive decisive rate: `64.71%`
- eligible-market positive decisive rate: `60.68%`
- positive-rate lift: `+4.02` percentage points
- candidate mean return: `+3.08%`
- eligible-market mean return: `+3.78%`
- mean-return lift: `-0.71` percentage points
- clean candidate positive decisive rate: `70.97%`
- conflict candidate positive decisive rate: `59.46%`
- candidate share of eligible events: `0.61%`

The clean population shows useful directional behavior, but the `INCREASING_SUPPLY_LIKE` overlap is materially harmful. The audited provisional policy is therefore to keep the event as a candidate with reduced effective weight under conflict, rather than reject the underlying VSA concept.

Production-readiness audit:

- collector contains target: `False`
- engine collection path mentions target: `False`
- registry contains target: `False`
- clean effective weight at proposed base: `0.38`
- conflict effective weight at proposed penalty: `0.304`
- true ranking impact: `NOT_APPLICABLE_PRODUCTION_PATH_ABSENT`
- synthetic weight safety: `PASS`
- production score mutation: `False`

The canonical local registry is `evidence/evidence_registry.py`. `ABSORPTION` is intentionally absent from that registry and from the production collector.

### Scoring decision

```text
ABSORPTION = 0.38          # provisional audit value only
conflict_penalty = 0.20    # provisional audit policy
rejection = NO
status = AUDIT_COMPLETE / PROVISIONAL
production_path = NO
registry = NO
collector = NO
production_mutation = NO
```

This is an audit conclusion, not a production scoring change. A future promotion requires a dedicated production detector, registry entry, production-path verification, and real ranking-impact audit.

## Project-wide audit policy for these events

The project treats interaction results as evidence-quality information, not automatic detector invalidation. A contradictory observation reduces confidence/quality only when the historical outcome audit shows a repeatable deterioration, and rejection requires materially stronger evidence than a modest conflict association.

The current `DEMAND_COMING_IN`, `INCREASING_DEMAND`, `HIDDEN_DEMAND`, `DEMAND_DRYING_UP`, and `ABSORPTION` audit campaigns therefore freeze weights and interaction findings separately from production approval.

## Immediate conclusions

1. `STOPPING_VOLUME`, `SHAKEOUT`, `TEST`, and `NO_SUPPLY` have their established production/contextual roles.
2. `SPRING` remains production-integrated but provisional at base weight `0.75`.
3. `DEMAND_COMING_IN` is production-connected at base weight `0.38`, but remains provisional.
4. `INCREASING_DEMAND` is production-connected at base weight `0.85`, but remains provisional.
5. `INCREASING_DEMAND` has a provisional interaction penalty of `0.10`; no rejection rule is justified.
6. `HIDDEN_DEMAND` is audit-complete but remains non-scoring at `0.00`; its current candidate definition is not promoted into the production evidence path.
7. `DEMAND_DRYING_UP` is audit-complete but remains contextual/non-scoring at `0.00`; no conflict penalty or rejection rule is justified.
8. `ABSORPTION` is audit-complete and provisionally valued at `0.38` with a `0.20` conflict penalty, but remains unregistered and uncollected in production.
9. The `ABSORPTION` readiness audit found no real ranking impact to measure because its production path is absent; synthetic weight safety passed without mutating production scoring.
10. Neither `DEMAND_COMING_IN`, `INCREASING_DEMAND`, nor `ABSORPTION` is promoted to fully production-approved status by these audit results.
11. Future evidence events must follow the same audit-first process rather than inheriting weights or interaction penalties automatically.
