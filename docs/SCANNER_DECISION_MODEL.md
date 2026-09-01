# Scanner Decision Model

## Status

**Type:** Proposed architecture with validated empirical decisions

**State:** EVOLVING — core decision principles are validated; event-specific production rules remain evidence-gated.

This document defines the decision layer after the completed incremental-scanner and VSA event audit work. It is a living decision specification: empirical findings can promote, suppress, or leave individual evidence events provisional without weakening the overall architecture.

## 1. Core principle

ProVSA is a real-market VSA decision system, not a textbook-pattern detector.

The decision layer must combine imperfect but meaningful VSA evidence with market structure, trend, timing, contradiction, and confidence. It must not require a textbook-perfect pattern before allowing a meaningful setup to qualify.

All decisions must preserve point-in-time semantics and avoid look-ahead leakage.

## 2. Decision flow

```text
Market Data
    ↓
Metrics
    ↓
Market Structure / Swings / Trend
    ↓
VSA Evidence Collection
    ↓
Evidence Aggregation
    ↓
Professional Scoring
    ↓
Qualification / Suppression Gates
    ↓
Freshness / Timing / Contradiction Checks
    ↓
Final Candidate Decision Score
    ↓
Ranking
```

The important architectural rule is that **evidence detection, empirical validation, scoring, and actionability are separate decisions**.

## 3. Layer responsibilities

### Metrics

Produces quantitative measurements and semantic classifications from price, volume, spread, and related derived metrics.

Metrics do not decide whether a market event is bullish or bearish; VSA interpretation belongs to the evidence layer.

**State:** VALIDATED / existing subsystem.

### Structure and Trend

Provides confirmed swings, swing classification, structural pattern, trend direction/state, smart-money context, and structural progression.

Structure is contextual decision evidence and must remain causally valid at the decision time.

**State:** VALIDATED / existing subsystem, with future refinement still possible.

### VSA Evidence

Collects individual VSA events according to their validated production status.

Evidence is event-oriented. Evidence from the same bar/direction must not be blindly summed as independent confirmation when events represent overlapping information.

**State:** VALIDATED / PROVISIONAL depending on event.

### Evidence Aggregation

Groups and normalizes evidence while preserving event identity, direction, role, freshness, and interactions.

Potential roles include:

- primary evidence
- supporting evidence
- effort/result context
- structural context
- contradiction
- suppressive evidence

**State:** PARTIALLY VALIDATED.

### Professional Scoring

Combines validated evidence and contextual factors into a directional score suitable for professional decision-making.

Important constraints:

- runtime scoring must use the actual production scoring path;
- registry/profile weights are not assumed to equal runtime dynamic weights;
- contradictory evidence must be handled intentionally rather than by naive arithmetic;
- score changes must be tested for actual decision impact, not only numerical movement;
- an event must not receive a production penalty or bonus solely because raw outcomes look attractive.

**State:** VALIDATED / actively audited.

### Qualification and suppression

Determines whether a candidate remains actionable after scoring and contextual checks.

Qualification is not equivalent to event detection. A valid VSA event may be retained as evidence while being prevented from producing an actionable candidate when empirical testing shows that the event degrades decisions in a specific regime.

**State:** VALIDATED as a decision-layer principle.

### Freshness / Timing

Ensures that old evidence does not receive the same decision influence as recent evidence when timing changes its meaning.

Freshness must remain point-in-time and must not introduce future information.

**State:** VALIDATED / actively audited.

### Ranking

Orders qualified candidates using the final decision score plus explicitly validated tie-breakers.

Ranking should favor coherent evidence with strong structure/context, not simply the number of detected events.

**State:** PRODUCTION TARGET / evolving.

## 4. Evidence validation policy

Every major event follows an evidence-first validation ladder:

```text
point-in-time detector
        ↓
raw outcome audit
        ↓
matched-control audit
        ↓
bootstrap robustness
        ↓
state × direction regime analysis
        ↓
symbol concentration analysis
        ↓
production decision
        ↓
documentation
```

Raw positive returns are **not sufficient** evidence for production promotion.

The matched-control delta is the key incremental-value measure:

```text
Target outcome − matched-control outcome
```

Bootstrap intervals are used to determine whether that incremental effect is robust rather than driven by a small number of cases.

## 5. Validated event findings

### `INCREASING_DEMAND`

The NSE 30-symbol universe audit produced materially different results across regimes and change directions. The matched-control robustness work showed that the event can underperform controls in important buckets.

The event therefore must not be treated as unconditional bullish confirmation. Its interpretation is context-dependent and must remain subject to structure/regime qualification.

The audit also established the importance of unique target/control pairing and horizon-specific analysis.

**Production principle:** do not promote `INCREASING_DEMAND` based on raw event returns alone.

### `DEMAND_COMING_IN`

The raw universe audit produced positive absolute outcomes:

- 3w: approximately **+0.852%**, 54.1% win rate;
- 5w: approximately **+1.509%**, 56.2% win rate;
- 10w: approximately **+2.796%**, 58.8% win rate.

However, matched-control analysis showed only small incremental advantages:

- 3w: **+0.143%**;
- 5w: **+0.101%**;
- 10w: **+0.318%**.

Bootstrap robustness did not establish a strong universal effect. Regime analysis also showed substantial variation, including materially negative correcting/bullish buckets.

The production gate was therefore retained as a **suppressive qualification rule** for the validated adverse regime rather than treating `DEMAND_COMING_IN` as unconditional bullish confirmation.

The post-gate leakage audit across the 30-symbol universe found:

```text
symbols requested: 30
symbols scanned: 30
blocked actionable cases expected: 0
```

This validates that the production gate is not leaking actionable cases through the targeted suppression condition.

**Production principle:** `DEMAND_COMING_IN` is context-dependent evidence with an empirically validated suppression gate; it is not standalone bullish alpha.

### `DEMAND_DRYING_UP`

The raw event audit initially looked strongly bullish:

- 3w: **+1.635%**, 62.0% win rate;
- 5w: **+2.508%**, 60.8% win rate;
- 10w: **+4.047%**, 62.3% win rate.

Matched-control analysis reversed that interpretation:

- 3w: **-1.207%** target-control delta;
- 5w: **-1.575%**;
- 10w: **-0.499%**.

The 5,000-iteration bootstrap audit produced:

- 3w: **-1.208%**, 95% interval **[-2.458%, -0.050%]**;
- 5w: **-1.576%**, 95% interval **[-2.997%, -0.181%]**;
- 10w: **-0.497%**, 95% interval **[-2.616%, +1.661%]**.

Therefore the 3- and 5-week negative incremental effect is robust. The 10-week effect is directionally negative but not statistically decisive under this bootstrap test.

**Current production status:** `DEMAND_DRYING_UP` remains audit-only / zero production weight until state × direction and symbol-concentration analysis are completed. The empirical evidence strongly argues against unconditional bullish weighting and supports investigation of suppressive use.

## 6. Matched-control policy

Matched-control audits must prevent control reuse within the same symbol/horizon bucket where the audit design requires unique controls.

A control is not allowed to be selected merely because it has a similar raw outcome. Matching must use information available at the event decision point.

The control framework exists to separate:

```text
absolute market outcome
        from
incremental event information
```

## 7. Bootstrap policy

Robustness audits use the paired target-control return delta and percentile bootstrap intervals.

The standard robustness configuration is:

```text
bootstrap iterations = 5000
confidence interval  = 95% percentile interval
```

A wholly negative interval supports robust target underperformance in that bucket. A wholly positive interval supports robust target outperformance. Intervals crossing zero remain inconclusive.

Small buckets must not be promoted to production rules merely because their point estimate is large.

## 8. Regime and symbol policy

Event value must be evaluated by:

- trend state;
- trend direction;
- change direction where applicable;
- horizon;
- symbol concentration.

A universal production weight is inappropriate when the event's effect changes sign across regimes.

The minimum-case threshold is a stability flag, not proof of causality.

## 9. Weighting policy

Weights follow this hierarchy:

```text
registry/profile weight
        ↓
runtime dynamic weight
        ↓
empirical decision-value reference
        ↓
production qualification / suppression decision
```

An empirical reference is calibration evidence, not an automatic production weight.

For events with robust negative incremental value, the next step is to test whether a **context-specific suppression penalty** improves decisions. No global penalty should be introduced before regime validation.

## 10. Contradiction policy

Contradictions are contextual information.

A contradiction may:

- invalidate an interpretation;
- reduce confidence;
- suppress actionability;
- or be expected because two events describe the same underlying market behavior.

The effect must depend on strength, role, freshness, and regime.

## 11. Point-in-time and audit integrity

All event and decision audits must preserve the production information boundary.

The audit harness must not use:

- future bars to classify an event unless the production detector explicitly models a confirmation delay;
- post-event information in matching;
- future trend state;
- future score values;
- duplicated controls that distort uncertainty estimates.

The audit runner itself is part of the research methodology and must be tested before trusting its output.

## 12. Decision-quality rule

The project optimizes for **incremental decision value**, not attractive raw statistics.

Therefore:

```text
raw return ≠ event alpha
win rate ≠ event alpha
high MFE ≠ event alpha

matched-control delta
+ robustness
+ regime consistency
+ symbol breadth
= production evidence
```

## 13. Current next target

`DEMAND_DRYING_UP` is the active research event.

The remaining validation sequence is:

```text
DEMAND_DRYING_UP
        ↓
state × direction analysis
        ↓
symbol concentration
        ↓
production decision
        ↓
documentation
```

Only after those steps should any production suppression or weighting change be considered.

## 14. Relationship to other documents

`PROJECT_ARCHITECTURE.md` remains the authoritative current-state architecture document.

`SCANNER_STATE_DESIGN.md` defines causal/incremental state and boundary requirements.

Event-specific audit and findings documents contain the detailed empirical evidence.

This document defines how those validated findings should influence the decision architecture.
