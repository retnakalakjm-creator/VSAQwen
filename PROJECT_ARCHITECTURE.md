# Project Architecture: Local Python Desktop Finance App (Current State)

## 1. Current System Overview

- The repository is a Python-based VSA swing-scanner codebase for market analysis. The active executable workflow remains the command-line scanner; `gui.py` exists but is not currently an operational GUI workflow.
- `main.py` accepts an optional Yahoo Finance symbol and `--limit`, downloads daily OHLCV data, converts it to weekly bars, calculates quantitative metrics, runs the actionable scanner, and prints ranked candidates.
- Yahoo Finance data is cached locally as CSV files under `cache/`.
- The metrics layer performs quantitative preparation and semantic classifications; VSA interpretation belongs to the evidence layer rather than the raw metrics engine.
- The market-structure layer provides swings, structural scoring, progression, trend context, smart-money context, and related models.
- The evidence layer is operational for the currently enabled supply, demand, TEST, Stopping Volume, SHAKEOUT, Spring, and structural-progression paths. `DEMAND_COMING_IN` and `INCREASING_DEMAND` are connected to the production evidence path but remain **provisional** after their audit campaigns. `HIDDEN_DEMAND`, `DEMAND_DRYING_UP`, and `ABSORPTION` are audit-complete but are not connected to the production evidence path.
- Evidence aggregation is event-oriented: evidence is grouped by `(bar_index, direction)`, primary/supporting/effort-result/structural roles are separated, and duplicate observations are not blindly summed.
- Professional scoring combines trend, supply, demand, effort, strength, weakness, and confidence; scanner qualification and ranking operate on the resulting evidence and structural context.
- Weight sensitivity must be evaluated through the actual production scoring path; changing `Evidence.weight` on cached objects alone is insufficient because `ProfessionalScoringEngine` reads `config.SUPPLY_EVIDENCE_WEIGHTS`.
- Production-path readiness validates the actual runtime behavior of the production collector and scorer. It must not assume that registry values or static scoring-map values equal the dynamically emitted Evidence metadata.

## 2. Active Python Tech Stack

- **Language:** Python.
- **Data source:** yfinance.
- **Analysis:** pandas, numpy, and Python standard-library dataclasses/enums/pathlib/argparse utilities.
- **Declared GUI dependency:** PySide6, although the active CLI path does not initialize a GUI.
- **Local storage:** filesystem CSV cache under `cache/` plus configured logging.
- **Other declared dependencies:** openpyxl and reportlab remain declared but are not core components of the current scanner execution path.

## 3. Core Execution Flow

```text
Yahoo Finance daily OHLCV
        ↓
local CSV cache
        ↓
daily_to_weekly()
        ↓
MetricsEngine.calculate()
        ↓
market structure / trend / swings
        ↓
EvidenceEngine.collect()
        ├── supply evidence
        ├── demand evidence
        ├── Spring
        └── structural progression
        ↓
evidence aggregation
        ↓
professional scoring
        ↓
qualification / freshness / contradiction checks
        ↓
scanner ranking
        ↓
actionable candidates
```

All historical VSA audits are expected to respect point-in-time semantics and avoid look-ahead leakage.

## 4. Evidence Architecture

### Supply layer

`evidence/supply.py` currently provides:

- `BUYING_CLIMAX`
- `SUPPLY_COMING_IN`
- `HIDDEN_SUPPLY`
- `INCREASING_SUPPLY`
- `SUPPLY_DRYING_UP`
- `UPTHRUST`
- `NO_DEMAND`

`BUYING_CLIMAX` is production-active and has completed its current production-path audit.

Its weighting has three distinct layers:

- **Registry/profile weight:** `1.00`.
- **Runtime weight:** dynamically calculated by `WeightCalculator._buying_climax_weight(ctx)`.
- **Empirical reference weight:** `0.38`, used only for decision-value calibration and counterfactual analysis.

The production runtime weight is not fixed at `0.38`. The production audit observed runtime weights from `0.9` to `2.0`, all within the validated runtime bounds of `0.50–2.00`.

The current production path has been verified with `181 / 181` campaign-qualified emissions, zero duplicate emissions, zero campaign mismatches, zero runtime-weight bound violations, zero production score-mutation failures, and no production interaction penalty.

The interaction study identified INCREASING_DEMAND + UPTHRUST
as a materially weaker BUYING_CLIMAX combination.

A dedicated UPTHRUST counterfactual study tested hypothetical
0.02–0.10 deductions at the professional supply-score layer.
The deductions moved net_strength toward zero rather than
producing the intended weakening effect.

Therefore the interaction remains analysis-only:
no production interaction penalty and no global UPTHRUST
weight change are configured.

Some additional supply-descriptor blocks remain intentionally disabled until their semantics are frozen.

### Demand layer

`evidence/demand.py` currently provides active demand/context events including:

- `STOPPING_VOLUME`
- `SHAKEOUT`
- `NO_SUPPLY`
- `TEST`
- `DEMAND_COMING_IN`
- `INCREASING_DEMAND`

`SELLING_CLIMAX` is production-integrated and active at a base weight of 0.38 after completing candidate, semantic-quality, interaction, outcome, decision-value, readiness, and post-integration audits.
`HIDDEN_DEMAND` and `DEMAND_DRYING_UP` remain audit-only candidates and have no active production detectors.

### Other evidence layers

- `evidence/spring.py` handles Spring candidate/test/confirmation validation.
- `evidence/effort.py` contains effort-result analysis, but its engine invocation is currently disabled.
- `background/structural_progression.py` provides structural context and is kept separate from raw primary VSA evidence.
- `ABSORPTION` has completed an analysis-only audit as an effort/result / absorption candidate, but it has no production collector, engine collection path, or registry entry.

## 5. Current Validated / Provisional VSA Event State

| Event | Production path | Status | Base weight | Current interaction policy |
|---|---:|---|---:|---|
| `STOPPING_VOLUME` | YES | Production-integrated / validation-complete | `1.00` | No special penalty established |
| `SHAKEOUT` | YES | Production-integrated / validation-complete | `0.50` | Existing contextual interaction policy |
| `TEST` | YES | Production-integrated / non-scoring | `0.00` | Contextual only |
| `NO_SUPPLY` | YES | **Production-active / audit-complete / contextual-non-scoring** | `0.00 / no scoring-map entry` | `SUPPLY_DRYING_UP` overlap is contextual; `TEST` overlap is confirming/contextual; no penalty; rejection `NO` |
| `SPRING` | YES | Production-integrated / provisional | `0.75` | Same-bar `UPTHRUST`/`BUYING_CLIMAX` reduces Spring quality; does not reject |
| `DEMAND_COMING_IN` | YES | **Provisional / audit-complete** | **0.38** | No conflict penalty established; rejection `NO` |
| `INCREASING_DEMAND` | YES | **Provisional / audit-complete** | **0.85** | **Provisional conflict penalty `0.10`; rejection `NO`** |
| `HIDDEN_DEMAND` | NO | **Audit-complete / non-scoring** | **0.00** | No conflict penalty; rejection `NO`; not promoted into scoring |
| `DEMAND_DRYING_UP` | NO | **Audit-complete / non-scoring** | **0.00** | No conflict penalty; rejection `NO`; contextual/exhaustion role only |
| `ABSORPTION` | NO | **Audit-complete / provisional** | **0.38** | **Provisional conflict penalty `0.20`; rejection `NO`; no production path** |
| `SELLING_CLIMAX` | YES | Production-integrated / audit-complete | `0.38` | No conflict penalty; STOPPING_VOLUME interaction is confirming |
| `BUYING_CLIMAX` | YES | **Production-active / audit-complete** | **1.00 registry / dynamic runtime** | **Runtime 0.9–2.0 observed; empirical 0.38 is calibration-only; `INCREASING_DEMAND + UPTHRUST` remains diagnostic/study-only; no production interaction penalty is justified; no global UPTHRUST weight change is configured.|
| `SUPPLY_COMING_IN` | YES | **Production-active / audit-complete** | **1.00 registry / dynamic runtime** | **Runtime 0.70–1.70 observed; empirical 0.38 is calibration-only; `INCREASING_SUPPLY` overlap is confirming and carries no production penalty** |
| `NO_DEMAND` | YES | **Production-active / audit-complete** | `0.60` | No interaction penalty; rejection `NO`; dynamic Evidence.weight is separate from scoring-map weight |
| `UPTHRUST` | YES | **Production-active / audit-complete** | `Registry 1.00 / supply scoring-map 0.90 / dynamic runtime` | Mandatory production semantics PASS. 289 production emissions from 1,319 cheap candidates. `BUYING_CLIMAX` overlaps all 289 events; `INCREASING_DEMAND` overlaps 224. Exact pure interaction = 212 events. Historical interaction degradation observed, but explicit penalty rejected because counterfactual supply deductions move net-strength in the wrong direction. |
| `SUPPLY_DRYING_UP` | YES | **Production-active / audit-complete** | `Contextual supply exhaustion` | `1.00 registry / 0.60 professional supply-map / dynamic runtime Evidence.weight` | Production semantics: DOWN BAR + LOW VOLUME + NARROW SPREAD; confirmations non-mandatory. Audit: 547 cheap candidates → 225 production emissions; semantic failures 0; duplicate emissions 0. Decision value: 61.78% positive decisive rate vs 60.79% eligible market (+0.99 pp); mean 8-bar return +3.56% vs +3.83% market (-0.26 pp). Interactions: TEST 43, NO_SUPPLY 19, NO_SUPPLY + TEST 4, clean 159. No production interaction bonus/penalty, no rejection rule, no global weight promotion. Production readiness: PASS; runtime Evidence.weight observed 1.00–1.00, mean 1.00. |

The word **provisional** is intentional. A production-connected event can be exercised through the live evidence path without being treated as fully production-approved scoring logic. `HIDDEN_DEMAND`, `DEMAND_DRYING_UP`, and `ABSORPTION` are intentionally excluded from the production path until their production detectors and scoring integration are separately justified.


## 6A. SUPPLY_COMING_IN Current Audit State

`SUPPLY_COMING_IN` has completed its current audit-first production validation sequence.

Production verification:

- candidate events: `189`
- production emissions: `189`
- campaign mismatch: `0`
- expected-event mismatch: `0`
- duplicate emissions: `0`
- runtime weight range: `0.70–1.70`
- runtime calculator/emission agreement: `100%`
- runtime out-of-bounds: `0`
- production interaction penalty: `NONE`
- production score mutation: `False`
- audit status: `PASS`

Decision-value evidence:

- positive decisive rate: `62.96%`
- eligible-market positive decisive rate: `60.74%`
- positive-rate lift: `+2.22 pp`
- mean 8-bar return: `+3.76%`
- eligible-market mean return: `+3.81%`
- mean-return lift: `-0.05 pp`

Interaction evidence:

- `INCREASING_SUPPLY` overlap: `147 / 189` (`77.78%`)
- clean events: `42`
- overlap events: `147`
- overlap positive decisive rate: `65.31%`
- clean positive decisive rate: `54.76%`
- overlap mean return: `+3.81%`
- clean mean return: `+3.61%`

The overlap is therefore treated as confirming supply pressure rather than a contradiction requiring a penalty.

Frozen production state:

```text
collector          = YES
registry            = 1.00
runtime weighting   = dynamic
empirical ref       = 0.38
interaction penalty = NONE
production change   = NONE
status              = PRODUCTION-ACTIVE
```

## 6B. BUYING_CLIMAX Current Audit State

`BUYING_CLIMAX` is connected to the production supply evidence path and has completed its current production-path verification.

Production verification:

- campaign-qualified events: `181`
- production emissions: `181`
- campaign mismatch: `0`
- duplicate emissions: `0`
- runtime-weight bounds: `0.50–2.00`
- observed runtime-weight range: `0.9–2.0`
- runtime-weight violations: `0`
- production interaction penalty: `NOT CONFIGURED`
- production score mutation: `False`
- audit status: `PASS`

The static registry value of `1.00` must not be confused with the runtime value. Runtime scoring is context-dependent.

The empirical `0.38` value comes from counterfactual decision-value testing. It is **not** the current production weight.

The interaction study found:
- INCREASING_DEMAND + UPTHRUST interaction remains diagnostic/study-only.
- No production penalty is configured.
- No global UPTHRUST weight change is configured.

Frozen production state:

```text
collector          = YES
registry           = 1.00
runtime weighting  = dynamic
empirical ref      = 0.38
production change  = NONE
status             = PRODUCTION-ACTIVE
```
## 6C. SUPPLY_DRYING_UP Current Audit State

`SUPPLY_DRYING_UP` is production-valid and audit-complete. Its production
definition is `DOWN BAR + LOW VOLUME + NARROW SPREAD`; there are no mandatory
confirmation requirements.

The frozen audit population contains 225 production emissions from 547 cheap
candidates. The event shows a modest +0.99 percentage-point positive-decisive
rate lift versus the eligible market, but a -0.26 percentage-point mean-return
lift. This supports its contextual supply-exhaustion role but does not justify
promoting its professional scoring weight.

Same-bar interaction analysis found `TEST` (43), `NO_SUPPLY` (19), and
`NO_SUPPLY + TEST` (4). These remain diagnostic/study-only relationships;
no interaction bonus, penalty, rejection rule, or qualification change is
introduced.

## 7. DEMAND_COMING_IN Current Audit State

`DEMAND_COMING_IN` completed its audit cycle before being frozen at a provisional base weight of `0.38`.

Key findings:

- 281 candidate/production events across 8 symbols.
- Production emissions were observed at weight `0.38`.
- Candidate positive decisive rate: `66.19%` versus eligible-market `60.68%`.
- Decision lift: `+5.52` percentage points.
- At weight `0.38`, bias changed on `12 / 281` events (`4.27%`).
- Interaction audit did not establish a meaningful supply-side conflict penalty.
- Final qualification did not justify full promotion; the bias-changing sample was too small and had worse positive hit rate despite stronger return magnitude.

Frozen audit policy:

```text
base weight        = 0.38
conflict penalty   = 0.00
rejection          = NO
status             = PROVISIONAL
```

## 8. INCREASING_DEMAND Current Audit State

`INCREASING_DEMAND` is connected to the production evidence path using the validated point-in-time detector definition:

1. Bullish bar.
2. High volume.
3. Above-average spread.
4. Increasing volume versus the previous bar.

The detector intentionally allows imperfect but meaningful real-market VSA evidence rather than forcing textbook-perfect patterns.

Production-path verification:

- production hits: `905`
- symbols with production hits: `8 / 8`
- observed emitted weights: `[0.85]`

Calibration:

- calibration population: `902` events / 8 symbols.
- beneficial decision changes: `26`
- harmful decision changes: `15`
- net benefit: `+11`
- benefit/harm ratio: `1.7333`
- leave-one-symbol-out minimum net benefit: `+6`

Interaction audit:

- conflicts: `41 / 902`
- conflict rate: `4.55%`
- hidden-supply-like conflicts: `41`
- buying-climax-like conflicts: `16`
- upthrust-like conflicts: `1`
- supply-coming-in-like conflicts: `0`
- increasing-supply-like conflicts: `0`
- no-demand-like conflicts: `0`

Conflict outcome audit:

- usable events: `899`
- conflict events: `41`
- clean events: `858`
- conflict mean return: `+0.72%`
- clean mean return: `+3.83%`
- conflict return gap: `-3.11` percentage points
- conflict positive rate: `51.22%`
- clean positive rate: `59.44%`
- positive-rate gap: `-8.22` percentage points

Penalty sensitivity recommended a provisional `0.10` conflict penalty, equivalent to an effective conflict-event weight of `0.765` while clean events retain `0.85`.

Important: this `0.10` penalty is an **audit conclusion**, not a claim that the production scoring engine already applies it.

Frozen audit policy:

```text
base weight        = 0.85
conflict penalty   = 0.10   # provisional audit policy
rejection          = NO
status             = PROVISIONAL
```

## 9. HIDDEN_DEMAND Current Audit State

`HIDDEN_DEMAND` remains an audit-only candidate and is not connected to the production evidence path.

Candidate semantic definition:

1. Bearish/down bar.
2. High volume.
3. Strong close.

This was intentionally derived as the semantic counterpart of the existing `HIDDEN_SUPPLY` structure without adding a spread gate or other textbook-only requirements.

Audit findings:

- candidate population: `136` events across 8 symbols.
- positive decisive rate: `58.82%`.
- mean 8-bar return: `+2.97%`.
- semantic-quality population: `136` events; volume increasing `82`, higher low `30`, non-climactic volume `66`.
- supply conflicts: `40 / 136` (`29.41%`), all `INCREASING_SUPPLY_LIKE`.
- conflict positive decisive rate: `60.00%` versus `58.33%` for clean events.
- conflict mean return: `-0.34%` versus `+4.34%` for clean events.
- conflict penalty sensitivity recommended `0.00`; rejection was not justified.
- eligible-market positive decisive rate: `60.68%`.
- decision lift: `-1.86` percentage points.
- mean-return lift: `-0.82` percentage points.
- candidate share of eligible events: `1.22%`.

Decision:

```text
base weight        = 0.00
conflict penalty   = 0.00
rejection          = NO
status             = AUDIT_COMPLETE / NON_SCORING
production path    = NO
```

This is not a rejection of the VSA concept itself. It is a decision not to promote the current candidate into the scoring layer because its audited outcome does not demonstrate incremental value over the eligible-market baseline.

## 10. DEMAND_DRYING_UP Current Audit State

`DEMAND_DRYING_UP` remains an audit-only contextual candidate and is not connected to the production evidence path.

Candidate semantic definition:

1. Bullish/up bar.
2. Volume declining versus the previous bar.
3. Spread declining versus the previous bar.

The event is interpreted as **demand effort drying**, not automatically as bullish or bearish primary evidence, and remains distinct from bearish `NO_DEMAND`.

Audit findings:

- candidate population: `1,068` events across 8 symbols.
- positive decisive rate: `57.73%`.
- mean 8-bar return: `+3.25%`.
- semantic-quality population: `1,068` events; both volume and spread declined on all candidates; higher low `873` (`81.7%`); narrow/average spread `926` (`86.7%`).
- supply-overlap events: `164 / 1,068` (`15.36%`).
- overlap classes: `NO_DEMAND_LIKE` `136`; `BUYING_CLIMAX_LIKE` `28`; all other audited supply classes `0`.
- conflict positive decisive rate: `56.10%` versus `58.03%` for clean events.
- conflict mean return: `+2.57%` versus `+3.37%` for clean events.
- positive-rate gap: `-1.93` percentage points.
- mean-return gap: `-0.80` percentage points.
- no conflict penalty or rejection rule was justified.
- eligible-market positive decisive rate: `60.68%`.
- decision lift: `-2.95` percentage points.
- mean-return lift: `-0.53` percentage points.
- candidate share of eligible events: `9.55%`.

Decision:

```text
base weight        = 0.00
conflict penalty   = 0.00
rejection          = NO
status             = AUDIT_COMPLETE / NON_SCORING
production path    = NO
```

This is not a rejection of the VSA concept itself. It is a decision not to promote the current candidate definition into the scoring layer because its audited outcome does not demonstrate incremental value over the eligible-market baseline.

## 11. ABSORPTION Current Audit State

`ABSORPTION` has completed its analysis-only candidate, semantic-quality, interaction/contradiction, conflict-outcome, conflict-penalty, decision-value, and production-readiness audit sequence. It is **not** connected to the production evidence path.

Candidate semantic definition:

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
- supply-conflict rate: `54.41%`
- supply conflict class: `INCREASING_SUPPLY_LIKE` (`37`)
- other audited supply conflict classes: `0`
- demand interactions: `68 / 68`
- demand interaction class: `STOPPING_VOLUME_LIKE` (`68`)

Conflict-outcome audit:

- conflict events: `37`
- clean events: `31`
- conflict positive decisive rate: `59.46%`
- clean positive decisive rate: `70.97%`
- positive-rate gap: `-11.51` percentage points
- conflict mean return: `-0.58%`
- clean mean return: `+7.44%`
- mean-return gap: `-8.02` percentage points

Conflict penalty sensitivity recommended the maximum tested penalty of `0.20`; rejection was **not** justified.

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

The evidence supports keeping `ABSORPTION` as a candidate rather than rejecting it. The clean population has meaningful directional value, while `INCREASING_SUPPLY_LIKE` overlap is materially harmful. A provisional base weight of `0.38` and conflict penalty of `0.20` were selected for further evaluation.

Production-readiness audit:

- collector contains target: `False`
- engine collect path mentions target: `False`
- registry contains target: `False`
- clean effective weight at proposed base: `0.38`
- conflict effective weight at proposed penalty: `0.304`
- true ranking impact: `NOT_APPLICABLE_PRODUCTION_PATH_ABSENT`
- synthetic weight safety: `PASS`
- production score mutation: `False`

Important: the proposed `0.38` base weight and `0.20` conflict penalty are **audit conclusions only**. They are not production scoring settings. The local production registry is `evidence/evidence_registry.py`; the absence of an `ABSORPTION` registry entry is intentional at this stage.

Frozen audit policy:

```text
base weight        = 0.38   # provisional audit value
conflict penalty   = 0.20   # provisional audit policy
rejection          = NO
production path    = NO
registry            = NO
collector           = NO
production mutation = NO
status              = AUDIT_COMPLETE / PROVISIONAL
```
## 12. INCREASING_SUPPLY weighting provenance

`INCREASING_SUPPLY` has three distinct weight concepts:

- **Evidence registry/profile:** `0.85` — empirical/reference calibration metadata.
- **Configured supply evidence map:** `0.70` — current configuration entry.
- **Production runtime emission:** `1.00` — verified actual emitted `Evidence.weight`.

The production runtime value is the authoritative scanner value. The `0.85` empirical value is not automatically promoted into production scoring.

The production-path readiness audit verified:

- 1,022 cheap candidates
- 528 expected / observed production emissions
- 0 duplicate emissions
- 0 semantic failures
- runtime emission weight consistently `1.00`
- no production configuration mutation

Counterfactual scanner replay across `0.70–1.00` confirmed that `INCREASING_SUPPLY` weight affects final score and within-symbol ranking, but did not alter qualification or actionability in the frozen 528-event population.

No interaction penalty is currently configured in production.

## 12A. NO_SUPPLY weighting provenance
`NO_SUPPLY` has no professional scoring-map entry.

Its emitted Evidence.weight is runtime metadata produced by WeightCalculator.
That runtime weight must not be interpreted as a configurable professional
scoring weight.

Weight-sensitivity audits are therefore NOT APPLICABLE to NO_SUPPLY unless
a professional scoring-map entry is deliberately introduced through a
separate production-design decision.

`NO_SUPPLY` audit conclusion:

- semantic validation = PASS
- interaction validation = PASS
- interaction-outcome validation = PASS
- decision-value = no incremental value demonstrated
- professional scoring promotion = NO
- interaction penalty = NO
- rejection rule = NO
- production path = YES
- production role = contextual / non-scoring

## 13. Evidence Aggregation and Scoring Policy

Evidence is grouped by `(bar_index, EvidenceDirection)`. Within an event:

- primary evidence provides the anchor contribution;
- supporting evidence modifies the event rather than blindly stacking full weights;
- effort/result and structural evidence have their own contribution roles;
- duplicate observations are not treated as independent primary signals.

Interaction audits are a separate quality layer. A contradiction does **not** automatically invalidate a detector. The project requires empirical evidence that the conflict is repeatedly harmful before applying a quality penalty, and a rejection rule requires substantially stronger evidence.

For the current provisional events, audit conclusions are documented separately from active production scoring until the project explicitly promotes them. `HIDDEN_DEMAND` and `DEMAND_DRYING_UP` remain non-scoring and unregistered in production because their decision-value audits were negative. `ABSORPTION` remains unregistered because its production path is intentionally absent; its provisional weight and conflict penalty are documented only for future promotion work.

## 14. VSA Methodology Constraints

The project is designed for real-market VSA, not textbook-pattern detection.

Therefore:

- point-in-time evidence is mandatory;
- future bars may be used for audit outcomes, never for detector decisions;
- imperfect but meaningful VSA evidence is acceptable;
- detector semantics must remain faithful to strict VSA methodology;
- contextual evidence should not be promoted to standalone actionability without incremental-value evidence;
- conflicts should reduce quality only when validated by outcomes;
- adding or tuning a numeric weight never substitutes for semantic validation.

## 15. Audit-First Promotion Workflow

Every new provisional VSA event should follow this sequence:

```text
semantic definition
    ↓
point-in-time detector validation
    ↓
semantic-quality audit
    ↓
decision-value / outcome audit
    ↓
interaction / contradiction audit
    ↓
conflict-outcome audit
    ↓
weight sensitivity
    ↓
production-path verification
    ↓
regression / ranking safety
    ↓
final qualification decision
    ↓
documentation freeze
```

A failed audit script is never treated as evidence about the event itself. The script must first reproduce the validated event population.

### Interaction/Penalty Policy
## SUPPLY_DRYING_UP Interaction Policy

SUPPLY_DRYING_UP has demonstrated modest hit-rate selectivity versus the
eligible market, but not superior mean-return magnitude.

`SUPPLY_DRYING_UP + TEST` improves hit rate while reducing average return.
`SUPPLY_DRYING_UP + NO_SUPPLY` has a slightly higher hit rate but materially
weaker follow-through magnitude.

These relationships remain diagnostic evidence. They do not authorize automatic
interaction bonuses, penalties, or qualification changes.

The 4-event `NO_SUPPLY + TEST` subgroup is too small for calibration.

## UPTHRUST Interaction Penalty Decision

The audit established a real historical degradation for the
`UPTHRUST + BUYING_CLIMAX + INCREASING_DEMAND` population.

This does not authorize a production penalty by itself.

Counterfactual replay showed that subtracting a fixed amount from the supply
score causes the professional `net_strength` to move toward zero. Under the
current scoring architecture, that is the opposite of the intended effect of
a penalty.

Therefore the interaction remains observational/diagnostic evidence and is not
converted into a production penalty.

No change is made to:

- `SUPPLY_EVIDENCE_WEIGHTS[UPTHRUST]`
- global UPTHRUST scoring
- qualification logic
- actionability logic
- production emission logic

### Evidence emission weight vs professional scoring weight

These are separate concepts and must not be conflated.

`Evidence.weight` is emission-time metadata. It is calculated by
`WeightCalculator` from the point-in-time `BackgroundContext` and may
therefore vary from bar to bar.

`config.SUPPLY_EVIDENCE_WEIGHTS` and
`config.DEMAND_EVIDENCE_WEIGHTS` are the separate static scoring maps
consumed by `ProfessionalScoringEngine`.

Registry/profile weight is immutable reference metadata and is not proof
of the runtime emission weight or the effective scoring weight.

Therefore:

Evidence.weight != necessarily configured scoring-map weight
Evidence.weight != necessarily registry/profile weight

### Requirements vs confirmations

Detector `requirements` are emission gates.

Detector `confirmations` are additional VSA evidence-quality information
and are not mandatory unless the event specification explicitly declares
them as requirements.

A failed confirmation must therefore not be classified as a detector
semantic failure by an audit.

This distinction is required so audit logic does not accidentally
strengthen production detector semantics.

### Audit replay invariant

Weight-sensitivity audits must not rebuild detector semantics for every
counterfactual weight.

The safe pattern is:

historical data
    -> point-in-time candidate/emission state
    -> freeze validated target population
    -> vary live scoring-map weight
    -> recalculate scoring/ranking only

`TrendAnalyzer` and `EvidenceEngine` must remain outside the weight loop
whenever their inputs are weight-independent.

Qualification and actionability must not be replayed per weight when the
qualification logic is demonstrably weight-independent.


## 16. Repository Documentation Policy

- `docs/PRIMARY_VSA_EVENT_MATRIX.md` is the master event-status index.
- `docs/specifications/` is the canonical per-event semantic rulebook.
- Dedicated audit records in `docs/` preserve completed event reasoning and frozen provisional decisions.
- `PROJECT_ARCHITECTURE.md` describes the actual current code path and distinguishes production-integrated behavior from provisional audit policy.
- `Chat summary/` preserves the project train of thought, prior bugs, design decisions, and audit rationale.

No architecture document should claim a detector is production-approved merely because its enum, registry entry, or audit script exists.

## 17. Immediate Current State

The system currently has a functioning end-to-end path from market data through metrics, structure, evidence, professional scoring, qualification, ranking, and actionable scanner output.

The current demand/absorption milestone is:

```text
DEMAND_COMING_IN
    base weight = 0.38
    conflict penalty = 0.00
    status = PROVISIONAL

INCREASING_DEMAND
    base weight = 0.85
    conflict penalty = 0.10  # provisional audit policy
    status = PROVISIONAL

HIDDEN_DEMAND
    base weight = 0.00
    conflict penalty = 0.00
    status = AUDIT_COMPLETE / NON_SCORING
    production path = NO

DEMAND_DRYING_UP
    base weight = 0.00
    conflict penalty = 0.00
    status = AUDIT_COMPLETE / NON_SCORING
    production path = NO

ABSORPTION
    base weight = 0.38  # provisional audit value only
    conflict penalty = 0.20  # provisional audit policy
    status = AUDIT_COMPLETE / PROVISIONAL
    production path = NO
    registry = NO
    collector = NO
SELLING_CLIMAX
    base weight = 0.38
    conflict penalty = 0.00
    production path = YES
    registry = YES
    collector = YES
    post-integration audit = PASS
    status = PRODUCTION-ACTIVE
NO_DEMAND
    scoring-map weight = 0.60
    registry/reference weight = 1.00
    runtime Evidence.weight = dynamic (0.70–1.50 observed)
    interaction penalty = 0.00
    status = PRODUCTION-ACTIVE / AUDIT-COMPLETE
    production path = YES
NO_SUPPLY
    production path = YES
    role = CONTEXTUAL / NON-SCORING
    registry/reference weight = 1.00
    professional scoring-map entry = NONE
    runtime Evidence.weight = dynamic
    observed runtime Evidence.weight = 0.90–1.50
    runtime bounds = 0.50–2.00
    interaction = SUPPLY_DRYING_UP on 23/23
    TEST interaction = 4/23
    interaction penalty = NONE
    rejection = NO
    decision-value lift = +0.07 pp
    mean-return lift = -2.81 pp
    status = PRODUCTION-ACTIVE / AUDIT-COMPLETE
UPTHRUST
    production path = YES
    role = ACTIVE SUPPLY TRAP
    registry/reference weight = 1.00
    professional supply-map weight = 0.90
    runtime Evidence.weight = dynamic
    observed runtime Evidence.weight = 0.80–2.00
    observed mean runtime weight = 1.2194

    candidate population = 1,319
    production emissions = 289
    normal detector rejections = 1,030
    semantic failures = 0
    duplicate emissions = 0

    decision-value:
        positive decisive rate = 59.03%
        eligible market rate = 60.80%
        lift = -1.77 pp

        mean 8-bar return = +2.81%
        eligible market mean = +3.83%
        lift = -1.02 pp

    dominant interaction:
        UPTHRUST + BUYING_CLIMAX + INCREASING_DEMAND
        events = 212
        positive decisive rate = 56.87%
        mean return = +2.27%

    reference:
        UPTHRUST + BUYING_CLIMAX
        events = 65
        positive decisive rate = 66.15%
        mean return = +4.56%

    interaction counterfactual:
        tested penalties = 0.02, 0.04, 0.06, 0.08, 0.10
        result = directionally incorrect for penalty purpose
        production penalty = NONE

    production decision:
        no global UPTHRUST weight change
        no interaction penalty
        no rejection rule

SUPPLY_DRYING_UP
    modest hit-rate selectivity
    not a scoring-promotion candidate
    production path = YES
    production role = CONTEXTUAL SUPPLY EXHAUSTION

    registry/reference weight = 1.00
    professional SUPPLY_EVIDENCE_WEIGHTS weight = 0.60
    runtime Evidence.weight = dynamic emission metadata
    observed runtime weight = 1.00

   

    candidate population = 547
    production emissions = 225
    normal detector rejections = 322

    semantic requirements:
        DOWN BAR
        LOW VOLUME
        NARROW SPREAD

    semantic failures = 0
    duplicate emissions = 0

    decision value:
        positive decisive rate = 61.78%
        eligible market rate = 60.79%
        lift = +0.99 pp

        mean 8-bar return = +3.56%
        eligible market mean = +3.83%
        lift = -0.26 pp

    interactions:
        clean = 159
        TEST = 43
        NO_SUPPLY = 19
        NO_SUPPLY + TEST = 4

    interaction policy:
        diagnostic/study-only
        no bonus
        no penalty
        no rejection rule

    production readiness:
        PASS
        point-in-time = TRUE
        target-bar only = TRUE
        production context = TRUE
        production emission authority = TRUE
        production-path mutation = FALSE                        
```

`DEMAND_COMING_IN` and `INCREASING_DEMAND` are not promoted to fully production-approved scoring status by the completion of these audits. `HIDDEN_DEMAND` and `DEMAND_DRYING_UP` are explicitly not promoted into scoring because their audited candidate populations showed negative incremental value versus the eligible-market baseline. `ABSORPTION` is also not promoted into production: its clean candidate population showed positive directional value, but its `INCREASING_SUPPLY_LIKE` conflict population materially degraded outcomes, and the event currently has no production collection or registry path. The next candidate event must continue through the same audit-first process.

