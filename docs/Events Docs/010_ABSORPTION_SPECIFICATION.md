# Specification: ABSORPTION

**Version:** 1.0 (Provisional)  
**Status:** Audit-Complete, Non-Production (August 21, 2026)  
**Audit Events:** 68 identified (comprehensive audit complete)  
**Provisional Weight:** 0.38 (audit-only, NOT in production)  
**Conflict Penalty:** 0.20 (provisional, for INCREASING_SUPPLY conflicts)

---

## Purpose

Detect professional absorption of volume without significant price movement.

Absorption represents large volume activity that doesn't result in proportional price movement.

**Advanced VSA observation** for understanding professional quiet accumulation/distribution.

---

## Classical Definition (Tom Williams)

Absorption occurs when:
- Large volume activity
- Limited price movement (narrow spread)
- Effort doesn't match result
- Professional buying/selling without showing hand
- Price remains stable despite high activity

Mark of professional money moving large positions.

---

## Wyckoff Interpretation

Absorption = Professional Quiet Positioning

Indicates:
- Smart money accumulating/distributing quietly
- Volume present but contained (no panic)
- Preparation for aggressive move
- Hidden preparation phase

Part of accumulation/distribution characterized by effort-result mismatch.

---

## Professional Interpretation

Significant volume without aggressive pressure.

Professional money positioning quietly.

Buyers or sellers entering without tipping hand.

Setup for eventual aggressive move when position complete.

---

## Detection Conditions

### Condition 1: Neutral or Minimal Price Bar
- Close near open
- Narrow spread
- Minimal daily range
- Price action relatively unchanged

### Condition 2: High Volume
- Volume Percentile >= ABSORPTION_MIN_VOLUME_PERCENTILE
- Significant activity level
- Clear professional-scale participation

### Condition 3: Effort-Result Mismatch
- High volume but narrow spread (KEY characteristic)
- Price not moving proportionally to volume
- Suggests absorption rather than directional buying/selling

---

## Output (Conceptual - Not Yet in Production)

**Event Type:** SmartMoneyEvidence (not implemented)

**Properties:**
- Code: ABSORPTION
- Category: EFFORT/RESULT (neither demand nor supply directly)
- Direction: NEUTRAL (ambiguous without context)
- Role: Contextual observation only
- Strength: MODERATE (effort-result observation)

**Interpretation:**
Professional money present and active.
Position building underway.
Aggressive move likely coming.

---

## Confidence Calculation

Composite of:
- Volume Percentile (50% weight) - proves activity level
- Spread narrowness (35% weight) - indicates containment
- Price stability (15% weight) - shows effort-result mismatch

Higher volume + narrower spread + stable price = higher confidence in absorption

---

## Why Absorption Is Not in Production

### Implementation Status

- Collector: NOT in production (`evidence/supply.py`)
- Registry: NOT registered (not in `evidence_registry.py`)
- Production path: ABSENT
- Production scoring: ZERO contribution
- Detector location: Conceptual only

### Rationale for Non-Implementation

1. **Semantic Ambiguity**
   - Absorption doesn't specify direction (bullish or bearish)
   - Could be accumulation (bullish) or distribution (bearish)
   - Requires context for actionability

2. **Effort-Result Complexity**
   - Part of broader VSA framework (separate analysis layer)
   - Doesn't fit primary event detection model
   - Should be observation/context, not automatic evidence

3. **Implementation Deferral**
   - Other patterns (BUYING_CLIMAX, SUPPLY_COMING_IN) more immediately actionable
   - Absorption requires higher-level interpretation
   - Can be derived from combinations of primary patterns

---

## False Positives to Avoid

### DO NOT Detect (Conceptual Guidelines):

1. **High Volume + Wide Spread**
   - Opposite of absorption (effort = result)
   - This is climactic activity, not absorption
   - Aggressive, not quiet

2. **Narrow Spread + Low Volume**
   - Not significant enough
   - Insufficient activity for professional scale
   - Normal market, not absorption

3. **Gap/Limit Move**
   - Price moved significantly despite appearing narrow
   - Technical data artifact, not absorption
   - Excluded by spread threshold

4. **Open vs Close Misalignment**
   - Doji or similar patterns with large wicks
   - Spread shows effort even if close near open
   - Different pattern type

---

## Detection Semantics (Conceptual)

**Core Rule:** Professional activity without proportional price impact.

This is observed as:
- High volume (professional scale)
- Narrow spread (price contained)
- Minimal close movement (effort-result mismatch)

**Conceptual nature:**
- Harder to define than directional patterns
- Requires auxiliary context for use
- Better suited for higher-level analysis

---

## What ABSORPTION Must NOT Claim

ABSORPTION alone must NOT imply:
- Accumulation (could be distribution)
- Bullish continuation (ambiguous)
- Demand dominance (could be either side)
- Trade entry signal (requires context)
- Pending breakout (could be any direction)

Those require:
- Directional confirmation (DEMAND_COMING_IN or SUPPLY_COMING_IN)
- Price structure analysis
- Campaign/structural context
- Subsequent price validation

---

## Audit Findings (Complete)

### Candidate Events Identified

**68 total events across 8 symbols**

### Semantic Quality Audit

- Upper close characteristic: 68/68 (100%)
- Lower low characteristic: 68/68 (100%)
- High volume: 16/68 (23.5%)
- Wide spread: 16/68 (23.5%)
- Semantic failures: 0

### Conflict Analysis

**Supply-side conflicts:**
- Conflicted events: 37/68 (54.41%)
- Conflict type: INCREASING_SUPPLY_LIKE (100%)
- Clean events: 31/68 (45.59%)

**Demand-side interactions:**
- All 68 events show STOPPING_VOLUME_LIKE demand presence

### Conflict Outcome Audit

**Performance by Event Type:**

| Type | Events | Positive Rate | Mean Return |
|------|--------|---------------|-------------|
| Conflicted (INCREASING_SUPPLY) | 37 | 59.46% | -0.58% |
| Clean (no conflict) | 31 | 70.97% | +7.44% |
| All Events | 68 | 64.71% | +3.08% |

**Performance Gap:**
- Win rate gap: -11.51 percentage points (conflicts worse)
- Return gap: -8.02 percentage points (conflicts worse)

### Conflict Penalty Testing

**Provisional Penalty:** 0.20 (for INCREASING_SUPPLY conflicts)

**Effect of Penalty:**
- Improves aggregate positive rate: 64.71% → 65.29% (modest)
- Addresses weaker conflicted subset

**Decision:** Rejection NOT justified
- Clean population shows useful behavior (70.97% positive)
- Penalty approach more appropriate than outright rejection
- Keeps valid observation accessible with quality discount

---

## Decision-Value Audit

**Candidate Metrics:**
- Positive decisive rate: 64.71%
- Market baseline: 60.68%
- Lift: +4.02 percentage points

**Return Metrics:**
- Mean 8-bar return: +3.08%
- Market baseline: +3.78%
- Gap: -0.71 percentage points

**Clean Population Only:**
- Positive rate: 70.97% (good)
- Mean return: +7.44% (very good)
- Candidate share: 45.59% of events

**Conclusion:** 
Clean population is useful; conflicted population is weaker. Pattern shows promise but below-baseline overall due to conflict component.

---

## Production-Readiness Audit

**Implementation Status:**
- Collector contains target: FALSE
- Engine collection path mentions target: FALSE
- Registry contains target: FALSE
- Production path: ABSENT

**Weight Safety:**
- Clean effective weight at proposed base: 0.38
- Conflict effective weight at proposed penalty: 0.304 (0.38 × 0.80)
- True ranking impact: NOT_APPLICABLE (no production path)
- Synthetic weight safety: PASS (no production mutation)

**Conclusion:**
No production path exists, so real ranking impact cannot be measured. Synthetic safety check passes because there's nothing to mutate. Pattern remains conceptual/audit-only.

---

## Scoring Decision (Frozen)

```
ABSORPTION = 0.38          (provisional audit value only)
conflict_penalty = 0.20    (provisional audit policy, INCREASING_SUPPLY)
rejection = NO
status = AUDIT_COMPLETE / PROVISIONAL
production_path = NO
registry = NO
collector = NO
production_mutation = NO
production_scoring = NOT APPLIED
```

---

## Why Absorption Is Difficult to Implement

### 1. Semantic Ambiguity
- Absorption could be accumulation (bullish) or distribution (bearish)
- Direction not specified by pattern itself
- Requires external context for interpretation

### 2. Conceptual Layering
- Effort/result is separate from event detection layer
- Belongs to higher analytical framework
- Could be derived from combinations of other patterns

### 3. Implementation Complexity
- Requires specific thresholds for effort-result ratio
- May need market-regime adjustment
- Interaction with climax patterns requires care

### 4. Volume Normalization
- "High volume with narrow spread" is relative
- Needs dynamic thresholds
- Market volatility affects interpretation

---

## Relationship to Other Patterns

### With BUYING_CLIMAX
- Opposite concept: Climax = high volume + high pressure (result)
- Absorption = high volume + low pressure (no result)
- Could both occur in sequence (climax followed by absorption)

### With SUPPLY_COMING_IN
- Supply Coming In = high volume + wide spread (effort = result)
- Absorption = high volume + narrow spread (effort ≠ result)
- Different effort-result relationships

### With HIDDEN_SUPPLY
- Hidden Supply = effort hidden, revealed through weak close
- Absorption = effort hidden, revealed through volume-spread mismatch
- Different observation methodology

---

## Real-Market Examples (Conceptual)

### Example 1: Accumulation Absorption
```
Volume: 90 percentile (high)
Spread: 20 percentile (narrow)
Close: Stable near open
Subsequent: Price rallies significantly
Result: Accumulation confirmed by breakout
Interpretation: Quiet buying before breakout
```

### Example 2: Distribution Absorption
```
Volume: 92 percentile (very high)
Spread: 15 percentile (very narrow)
Close: Stable
Subsequent: Price breaks down
Result: Distribution confirmed by breakdown
Interpretation: Quiet selling before reversal
```

### Example 3: Mixed Absorption
```
Volume: 85 percentile (high)
Spread: 35 percentile (moderate)
Close: Neutral
Subsequent: Consolidates, direction unclear
Result: Absorption present but directionless
Interpretation: Professional activity, direction TBD
```

---

## Audit Policy for Conceptual Patterns

**Project-wide principle:**
- Interaction results treated as evidence-quality information
- Not automatic detector invalidation
- Contradictions reduce confidence only with repeatable outcome deterioration
- Rejection requires strong evidence

**Application to ABSORPTION:**
- Conflicted events show weaker performance (11.51 pp gap)
- But clean population is strong (70.97% positive)
- Penalty approach (0.20) acknowledged quality difference
- Rejection would discard useful information

---

## Future Path to Production (If Pursued)

### Prerequisites for Implementation

1. **Semantic Clarity**
   - Develop directional sub-types (accumulation vs distribution)
   - OR position as neutral observation in higher framework
   - Determine if standalone detector or composite signal

2. **Interaction Refinement**
   - Test 0.20 penalty in production context
   - Evaluate INCREASING_SUPPLY interaction specifically
   - Confirm quality discount justified

3. **Implementation Design**
   - Decide on collector vs higher-layer observation
   - Determine registry treatment
   - Plan integration with primary event layer

4. **Production Testing**
   - Real ranking impact audit (not synthetic)
   - Cross-symbol validation
   - Regression testing against baseline

### Timeline (Speculative)

- **Phase 1:** Finalize semantic framework (1-2 weeks)
- **Phase 2:** Implement directional sub-types (1-2 weeks)
- **Phase 3:** Production path development (1-2 weeks)
- **Phase 4:** Integration and validation (1-2 weeks)
- **Phase 5:** Production deployment (conditional)

Total: 6-10 weeks if pursued (currently: deferred)

---

## Current Status

**Implementation:** NOT ACTIVE (audit-only, conceptual)

**Detector:** Does not exist in production

**Registry:** Not registered

**Weight:** 0.38 (audit-only, not applied)

**Conflict Penalty:** 0.20 (provisional, not in production)

**Scoring Contribution:** ZERO (not in production path)

**Actionability:** None (audit/research only)

---

**Status:** AUDIT-COMPLETE, FROZEN (August 21, 2026)  
**Confidence Level:** MODERATE (clean subset is good, conflicts weaken)  
**Production Ready:** NO (implementation deferred)  
**Weight:** 0.38 provisional (not applied)  
**Timeline:** Deferred (revisit if business requirements change)

---

## Key Takeaway

Absorption is a valid VSA observation with audit-validated results. Clean population shows strong performance (70.97%), but conflicted events (INCREASING_SUPPLY) are weaker. The pattern remains audit-only pending future business decision to promote to production. Current project focus on primary direction-specific patterns (BUYING_CLIMAX, SUPPLY_COMING_IN, etc.) takes priority over this conceptual middle-layer pattern.
