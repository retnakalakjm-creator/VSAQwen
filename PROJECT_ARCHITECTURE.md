# Project Architecture: Local Python Desktop Finance App (Current State)

## 1. Current System Overview

- The repository is a Python-based VSA swing-scanner codebase for market analysis. The active executable workflow remains the command-line scanner; `gui.py` exists but is not currently an operational GUI workflow.
- `main.py` accepts an optional Yahoo Finance symbol and `--limit`, downloads daily OHLCV data, converts it to weekly bars, calculates quantitative metrics, runs the actionable scanner, and prints ranked candidates.
- Yahoo Finance data is cached locally as CSV files under `cache/`.
- The metrics layer performs quantitative preparation and semantic classifications; VSA interpretation belongs to the evidence layer rather than the raw metrics engine.
- The market-structure layer provides swings, structural scoring, progression, trend context, smart-money context, and related models.
- The evidence layer is operational for the currently enabled supply, demand, TEST, Stopping Volume, SHAKEOUT, Spring, and structural-progression paths. `DEMAND_COMING_IN` and `INCREASING_DEMAND` are connected to the production evidence path but remain **provisional** after their audit campaigns. `HIDDEN_DEMAND` is audit-complete but is not connected to the production evidence path.
- Evidence aggregation is event-oriented: evidence is grouped by `(bar_index, direction)`, primary/supporting/effort-result/structural roles are separated, and duplicate observations are not blindly summed.
- Professional scoring combines trend, supply, demand, effort, strength, weakness, and confidence; scanner qualification and ranking operate on the resulting evidence and structural context.

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

Some additional supply-descriptor blocks remain intentionally disabled until their semantics are frozen.

### Demand layer

`evidence/demand.py` currently provides active demand/context events including:

- `STOPPING_VOLUME`
- `SHAKEOUT`
- `NO_SUPPLY`
- `TEST`
- `DEMAND_COMING_IN`
- `INCREASING_DEMAND`

`SELLING_CLIMAX` remains disabled. `HIDDEN_DEMAND` remains an audit-only candidate and has no active production detector.

### Other evidence layers

- `evidence/spring.py` handles Spring candidate/test/confirmation validation.
- `evidence/effort.py` contains effort-result analysis, but its engine invocation is currently disabled.
- `background/structural_progression.py` provides structural context and is kept separate from raw primary VSA evidence.

## 5. Current Validated / Provisional VSA Event State

| Event | Production path | Status | Base weight | Current interaction policy |
|---|---:|---|---:|---|
| `STOPPING_VOLUME` | YES | Production-integrated / validation-complete | `1.00` | No special penalty established |
| `SHAKEOUT` | YES | Production-integrated / validation-complete | `0.50` | Existing contextual interaction policy |
| `TEST` | YES | Production-integrated / non-scoring | `0.00` | Contextual only |
| `NO_SUPPLY` | YES | Contextual / validation-complete | `0.00` | Does not independently create actionability |
| `SPRING` | YES | Production-integrated / provisional | `0.75` | Same-bar `UPTHRUST`/`BUYING_CLIMAX` reduces Spring quality; does not reject |
| `DEMAND_COMING_IN` | YES | **Provisional / audit-complete** | **0.38** | No conflict penalty established; rejection `NO` |
| `INCREASING_DEMAND` | YES | **Provisional / audit-complete** | **0.85** | **Provisional conflict penalty `0.10`; rejection `NO`** |
| `HIDDEN_DEMAND` | NO | **Audit-complete / non-scoring** | **0.00** | No conflict penalty; rejection `NO`; not promoted into scoring |

The word **provisional** is intentional. A production-connected event can be exercised through the live evidence path without being treated as fully production-approved scoring logic. `HIDDEN_DEMAND` is intentionally excluded from the production path because its current audited candidate population did not demonstrate incremental decision value.

## 6. DEMAND_COMING_IN Current Audit State

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

## 7. INCREASING_DEMAND Current Audit State

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

## 8. HIDDEN_DEMAND Current Audit State

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

## 9. Evidence Aggregation and Scoring Policy

Evidence is grouped by `(bar_index, EvidenceDirection)`. Within an event:

- primary evidence provides the anchor contribution;
- supporting evidence modifies the event rather than blindly stacking full weights;
- effort/result and structural evidence have their own contribution roles;
- duplicate observations are not treated as independent primary signals.

Interaction audits are a separate quality layer. A contradiction does **not** automatically invalidate a detector. The project requires empirical evidence that the conflict is repeatedly harmful before applying a quality penalty, and a rejection rule requires substantially stronger evidence.

For the current provisional events, audit conclusions are documented separately from active production scoring until the project explicitly promotes them. `HIDDEN_DEMAND` remains non-scoring and unregistered in production because its decision-value audit was negative.

## 10. VSA Methodology Constraints

The project is designed for real-market VSA, not textbook-pattern detection.

Therefore:

- point-in-time evidence is mandatory;
- future bars may be used for audit outcomes, never for detector decisions;
- imperfect but meaningful VSA evidence is acceptable;
- detector semantics must remain faithful to strict VSA methodology;
- contextual evidence should not be promoted to standalone actionability without incremental-value evidence;
- conflicts should reduce quality only when validated by outcomes;
- adding or tuning a numeric weight never substitutes for semantic validation.

## 11. Audit-First Promotion Workflow

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

## 12. Repository Documentation Policy

- `docs/PRIMARY_VSA_EVENT_MATRIX.md` is the master event-status index.
- `docs/specifications/` is the canonical per-event semantic rulebook.
- Dedicated audit records in `docs/` preserve completed event reasoning and frozen provisional decisions.
- `PROJECT_ARCHITECTURE.md` describes the actual current code path and distinguishes production-integrated behavior from provisional audit policy.
- `Chat summary/` preserves the project train of thought, prior bugs, design decisions, and audit rationale.

No architecture document should claim a detector is production-approved merely because its enum, registry entry, or audit script exists.

## 13. Immediate Current State

The system currently has a functioning end-to-end path from market data through metrics, structure, evidence, professional scoring, qualification, ranking, and actionable scanner output.

The current demand-side milestone is:

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
```

`DEMAND_COMING_IN` and `INCREASING_DEMAND` are not promoted to fully production-approved scoring status by the completion of these audits. `HIDDEN_DEMAND` is explicitly not promoted into scoring because the audited candidate population showed negative incremental value versus the eligible-market baseline. The next candidate event must continue through the same audit-first process.
