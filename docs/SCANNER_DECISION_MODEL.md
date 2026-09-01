# Scanner Decision Model

## Status

**Type:** Production decision architecture with validated empirical policies

**State:** EVOLVING — core decision principles and the current four-event production policy boundary are validated; future event-specific changes remain evidence-gated.

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
production-path audit
        ↓
ranking / actionability impact
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

## 5. Current validated event policies

### `DEMAND_COMING_IN`

`DEMAND_COMING_IN` is production-connected and remains a **frozen provisional runtime-weight event**.

Current policy:

```text
production path        = YES
runtime emitted weight = 0.38
professional weight    = no standalone config-map entry
conflict penalty        = 0.00
rejection               = NO
qualification change    = NO
actionability change    = NO
```

The production ranking-impact audit is now valid and confirms meaningful, non-dominant influence:

```text
symbols requested      = 8
symbols with results   = 8
target events          = 967
bias changes           = 198
bias change rate       = 20.48%
all emitted weights    = 0.38
failures               = 0
status                 = PASS
```

This confirms that the actual runtime event weight is `0.38` and that DCI participates materially in ranking/bias calculations. It does not show that another weight is superior. The existing `UP + CORRECTING` suppressive gate therefore remains the production qualification rule for the adverse regime.

**Production principle:** `DEMAND_COMING_IN` is context-dependent demand evidence with controlled ranking influence, not unconditional standalone bullish alpha.

### `INCREASING_DEMAND`

`INCREASING_DEMAND` remains a valid VSA observation and is **confirmation-only** for professional pressure scoring.

It has no professional demand weight. When it is the only bullish directional VSA evidence in the current scoring window, actionable confidence is retained only when:

1. trend direction is `UP`;
2. trend state is `HEALTHY`;
3. no opposing bearish directional VSA evidence is present.

This preserves the observation without allowing it to create an unconditional bullish upgrade.

**Production principle:** `INCREASING_DEMAND` is structural/contextual confirmation, not independent professional demand pressure.

### `DEMAND_DRYING_UP`

`DEMAND_DRYING_UP` remains **research-only / not production-integrated**.

The raw detector produced positive absolute returns, but matched-control results were negative at 3 and 5 weeks and directionally negative at 10 weeks. The detector is not emitted by the production evidence path, so those historical results do not justify a production weight, penalty, suppression rule, or rejection rule.

Current policy:

```text
production path        = NO
professional weight    = NONE
production penalty     = NONE
production suppression = NONE
production rejection   = NONE
```

**Production principle:** DDU must not be treated as an active production decision input until it is intentionally integrated and re-audited through the production path.

### `ABSORPTION`

`ABSORPTION` is **production-connected but non-scoring**.

Canonical production semantics require:

1. bearish/down bar;
2. high volume;
3. above-average spread;
4. upper close;
5. lower low than the previous bar.

Current policy:

```text
production path        = YES
runtime scoring weight = 0.00
hard rejection         = NO
soft conflict penalty  = 0.20 research-only / not applied
ranking mutation       = NO
actionability mutation = NO
```

The genuine production-path counterfactual tested weights `0.00` through `0.38` and showed deterministic monotonic score sensitivity but zero actionable gains/losses at every tested weight. Therefore no validated downstream ranking/actionability benefit exists yet.

**Production principle:** `ABSORPTION` is retained as explicit contextual production evidence, but its research counterfactual weight and conflict penalty must not leak into runtime scoring.

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
+ production-path impact
= production evidence
```

## 13. Production safety gate

The current four-event policy boundary is protected by explicit regression tests and a full repository regression run.

Final observed gate result:

```text
python -m pytest -q
210 passed
```

This means the current production scoring boundary is regression-safe. It does **not** authorize a new scoring promotion.

Production-policy changes require both:

```text
validated empirical decision/ranking evidence
                 +
full regression pass
```

The regression guard specifically preserves:

- `INCREASING_DEMAND` without professional demand weight;
- `DEMAND_COMING_IN` without a silent professional demand-map weight;
- `DEMAND_DRYING_UP` outside the production scoring map;
- `ABSORPTION = 0.00` in the production effort weight map;
- the existing DCI and increasing-demand gates;
- zero-weight ABSORPTION invariance for professional effort scoring.

## 14. Current production policy matrix

| Evidence | Production path | Professional scoring | Actionability / qualification | Current status |
| --- | --- | --- | --- | --- |
| `DEMAND_COMING_IN` | YES | Runtime `0.38` | Existing correcting + bullish suppression | Frozen provisional |
| `INCREASING_DEMAND` | YES | Confirmation-only | Sole bullish evidence retained only in `UP + HEALTHY` without bearish evidence | Frozen |
| `DEMAND_DRYING_UP` | NO | None | None | Research-only |
| `ABSORPTION` | YES | Runtime `0.00` | No validated contribution | Frozen non-scoring |

Detailed policy evidence is maintained in:

- `docs/PRODUCTION_SCORING_MILESTONE.md`
- `docs/DEMAND_COMING_IN_DECISION_SYNTHESIS.md`
- `docs/CONDITIONAL_INCREASING_DEMAND.md`
- `docs/DEMAND_DRYING_UP_FINDINGS.md`
- `docs/ABSORPTION_AUDIT.md`

## 15. Relationship to other documents

`PROJECT_ARCHITECTURE.md` remains the authoritative current-state architecture document.

`SCANNER_STATE_DESIGN.md` defines causal/incremental state and boundary requirements, including the decision-state information that must remain reproducible at an incremental boundary.

`PRODUCTION_SCORING_MILESTONE.md` defines the frozen production policy boundary and regression gate.

Event-specific audit and findings documents contain the detailed empirical evidence.

This document defines how those validated findings should influence the decision architecture.

## 16. Current next target

The four-event production scoring/ranking milestone is complete and regression-safe.

No immediate weight promotion is authorized. The next engineering milestone should introduce new validated production value rather than retuning these frozen policies without new evidence.
