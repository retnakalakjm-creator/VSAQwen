# Scanner Decision Model

## Status

**Type:** Proposed architecture

**State:** PROPOSED — not a frozen production specification.

This document defines the decision layer we intend to develop after the current evidence and incremental-scanner audit work. The model should be improved as real-market evidence and production validation accumulate.

## 1. Core principle

ProVSA is a real-market VSA decision system, not a textbook-pattern detector.

The decision layer must combine imperfect but meaningful VSA evidence with market structure, trend, timing, contradiction, and confidence. It must not require a textbook-perfect pattern before allowing a meaningful setup to qualify.

All decisions must preserve point-in-time semantics and avoid look-ahead leakage.

## 2. Proposed decision flow

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
Qualification
    ↓
Contradiction / Risk Checks
    ↓
Freshness / Timing Checks
    ↓
Final Candidate Decision Score
    ↓
Ranking
```

## 3. Layer responsibilities

### Metrics

Produces quantitative measurements and semantic classifications from price, volume, spread, and related derived metrics.

Metrics do not decide whether a market event is bullish or bearish; VSA interpretation belongs to the evidence layer.

**State:** VALIDATED / existing subsystem.

### Structure and Trend

Provides confirmed swings, swing classification, structural pattern, trend direction/state, smart-money context, and structural progression.

Structure is contextual decision evidence. It must remain causally valid at the decision time.

**State:** VALIDATED / existing subsystem, with some areas still subject to future refinement.

### VSA Evidence

Collects individual VSA events such as stopping volume, shakeout, spring, tests, supply, demand, climax, and structural progression according to their current production status.

Evidence is event-oriented. Evidence from the same bar/direction must not be blindly summed as independent confirmation when the events represent overlapping information.

**State:** VALIDATED / PROVISIONAL depending on event.

### Evidence Aggregation

Groups and normalizes evidence while preserving event identity, direction, role, freshness, and interactions.

Potential roles include:

- primary evidence
- supporting evidence
- effort/result context
- structural context
- contradiction

**State:** PARTIALLY VALIDATED / requires decision-layer audit.

### Professional Scoring

Combines validated evidence and contextual factors into a directional score suitable for professional decision-making.

Important constraints:

- runtime scoring must use the actual production scoring path;
- registry/profile weights must not be treated as equivalent to dynamic runtime weights;
- contradictory evidence must be handled intentionally rather than by naive arithmetic;
- score changes must be tested for actual decision impact, not only numerical movement.

**State:** PROPOSED TARGET FOR AUDIT.

### Qualification

Determines whether a candidate is actionable after scoring and contextual checks.

Qualification should consider the total evidence state rather than a single event.

**State:** PROPOSED TARGET FOR AUDIT.

### Contradiction / Risk Checks

Detects materially conflicting evidence and structural conditions.

A contradiction should not automatically become a rejection. Its effect should depend on the strength, role, recency, and context of the conflicting evidence.

**State:** PROPOSED.

### Freshness / Timing

Ensures that old evidence does not receive the same decision influence as recent evidence when timing materially changes its meaning.

Freshness must remain point-in-time and must not introduce future information.

**State:** PROPOSED.

### Final Candidate Decision Score

Produces the final comparable score used for ranking qualified candidates.

This should remain distinct from raw evidence weights and from diagnostic audit scores.

**State:** PROPOSED.

### Ranking

Orders qualified candidates using the final decision score plus any explicitly validated tie-breakers.

Ranking should favor quality and coherence of evidence, not simply the number of detected events.

**State:** PROPOSED.

## 4. Weighting policy

Weights are not assumed to be correct merely because an event is production-active.

For each event, the project should distinguish:

```text
registry/profile weight
        ↓
runtime dynamic weight
        ↓
empirical decision-value reference
        ↓
production qualification decision
```

An empirical reference weight is calibration evidence, not an automatic production change.

## 5. Contradiction policy

Contradictions should be evaluated as contextual information.

Examples of questions the decision layer must answer:

- Does the contradiction invalidate the primary VSA interpretation?
- Does it merely reduce confidence?
- Is it an expected interaction between related events?
- Is the contradiction stronger or more recent than the evidence it opposes?
- Does applying a penalty actually improve decisions on historical data?

A penalty must not be introduced simply because the numerical score can be made smaller. Counterfactual testing must demonstrate improved decision behavior.

## 6. Qualification policy

Qualification should be multi-factor and should not reduce to a single fixed event threshold.

Candidate qualification should consider:

- directional professional score;
- evidence coherence;
- structural alignment;
- trend context;
- contradictory evidence;
- evidence freshness;
- confidence and completeness;
- explicit rejection conditions that have been empirically justified.

## 7. Ranking policy

The ranking system should distinguish:

```text
qualified ≠ high quality
high score ≠ low risk
many events ≠ independent confirmation
```

Ranking should prefer coherent evidence with strong structure/context and acceptable contradiction/risk characteristics.

## 8. Audit requirements

Every decision-layer change should be validated through the production path.

Before committing an audit/debug harness, verify:

- loop structure;
- data-loading and replay count;
- production-path consistency;
- imports;
- obvious object/API mismatches;
- deterministic behavior;
- no hidden look-ahead.

Performance changes should be accepted only when they provide a meaningful measured benefit without materially increasing architectural complexity or changing VSA semantics.

## 9. Current optimization baseline

The current single production scanner pass is approximately **10 ms** in the existing profiling workload.

Recent optimization work established that further micro-optimization of EvidenceEngine sub-stages is not currently justified when gains are small or inconsistent.

The next priority is therefore decision quality and scoring behavior, not raw micro-performance.

## 10. Immediate next audit target

The next major work item is:

**Audit Professional Scoring → Qualification → Final Candidate Decision.**

The first step is to document the current production behavior, not to change it.

The audit should identify:

1. exact score inputs;
2. event weights and dynamic weighting;
3. aggregation rules;
4. contradiction handling;
5. qualification thresholds;
6. freshness handling;
7. rejection rules;
8. ranking/tie-break logic;
9. which parts are validated versus provisional;
10. where counterfactual decision-value testing is required.

Only after that audit should implementation changes begin.

## 11. Relationship to other project documents

`PROJECT_ARCHITECTURE.md` remains the authoritative current-state architecture document.

This document is the proposed future decision model and may diverge from the current implementation until individual parts are validated.

Event-specific audit documents remain authoritative for the validated status of individual VSA events.

The architectural reference commit `e926e9d8b29f9dda83d8f033dcc2c69e6cf34d79` remains an architectural reference only; it is not an instruction to implement that commit as-is.
