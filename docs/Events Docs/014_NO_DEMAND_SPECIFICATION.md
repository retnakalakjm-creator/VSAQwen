# Specification: NO_DEMAND

**Version:** 1.0  
**Status:** Production-Active (August 2026)  
**Audit Status:** Implementation exists, semantic classification pending  
**Role:** Contextual observation (non-scoring)  
**Direction:** Bearish context (absence of demand)

---

## Purpose

Detect bars where demand evidence is absent or minimal during price action.

NO_DEMAND represents the absence of significant buyer participation, which is bearish context.

**Contextual observation** for understanding market participation levels.

---

## Classical Definition (Tom Williams)

NO_DEMAND occurs when:
- Price bars appear without strong buying interest
- Close may be weak or neutral
- Limited evidence of professional buying
- Lower prices show no demand support
- Volume may be low or variable
- Sellers maintain control by default

Absence of buyers, not active selling necessary.

---

## Wyckoff Interpretation

NO_DEMAND = Absence of Accumulation Phase Activity

Indicates:
- No accumulation underway
- Distribution may be concluding
- Equilibrium/consolidation context
- Not yet price ready to move up
- Waiting phase before next cycle

Absence of demand is bearish bias.

---

## Professional Interpretation

There are no buyers stepping in to defend prices.

Professional money is not accumulating.

Market is waiting for demand or will decline.

Default bearish bias without buying interest.

---

## Detection Conditions (Observation-Based)

### Condition 1: No Strong Bullish Demand Evidence
- No DEMAND_COMING_IN detected
- No HIDDEN_DEMAND detected
- No buying pressure visible
- Absence of accumulation signals

### Condition 2: Absence of Multiple Demand Patterns
- Not supporting multiple demand evidence types
- Weak or no demand confluence
- Limited professional buying signals
- Scattered or absent buyer positioning

### Condition 3: Contextual Bearish Bias
- Supply patterns may be present
- Or neutral without strong direction
- Default context = demand is missing
- Bears maintain control by absence of buyers

---

## Output

**Event Type:** ContextualObservation (not SmartMoneyEvidence)

**Properties:**
- Code: NO_DEMAND
- Category: CONTEXTUAL (classification)
- Direction: BEARISH (absence = weakness)
- Role: Context flag, not evidence
- Strength: MODERATE (absence may be temporary)

**Interpretation:**
No professional buyers visible.
Price not being defended.
Demand vacuum present.
Bearish bias until proven otherwise.

---

## Weight (NON-SCORING)

**Scoring Weight:** 0.00 (contextual only)

**Status:** Non-scoring observation

**Rationale:** 
- Absence patterns don't score
- Presence of supply patterns do
- NO_DEMAND is complement to supply evidence
- Used for context, not direct scoring

---

## Relationship to Demand Patterns

NO_DEMAND is the absence of:
- DEMAND_COMING_IN (buyers entering)
- HIDDEN_DEMAND (quiet accumulation)
- DEMAND_DRYING_UP (buyers leaving)
- INCREASING_DEMAND (demand escalating)

**Key Distinction:**
- DEMAND_DRYING_UP = demand WAS present, now fading
- NO_DEMAND = demand was NOT present

Different concepts requiring different semantics.

---

## False Positives to Avoid

### DO NOT Detect:

1. **During Hidden Demand Bars**
   - Quiet accumulation present but hidden
   - Should not flag as NO_DEMAND
   - Requires explicit HIDDEN_DEMAND detection exclusion

2. **Strong Supply Bar**
   - May have supply but demand appears absent
   - Supply is active, not just "no demand"
   - Classify as supply context, not NO_DEMAND

3. **Consolidation with Balanced Action**
   - Supply and demand both quiet
   - Neither is "absent"
   - Should not flag as NO_DEMAND

4. **Demand Building Bars**
   - Early accumulation signals present
   - May appear subtle but real
   - Don't classify as NO_DEMAND

---

## Detection Semantics

**Core Rule:** Buyer participation is not evident.

This is observed as:
- No demand patterns detected
- No professional buying signals
- No accumulation evidence
- Demand vacuum exists

---

## What NO_DEMAND Must NOT Claim

NO_DEMAND alone must NOT imply:
- Guaranteed decline
- Support will fail
- Breakdown imminent
- No reversal possible
- Buyers never entering

Those require:
- Supply patterns present
- Extended absence (multiple bars)
- Structural support levels tested
- Qualification validation
- Follow-through selling

---

## Interaction with Supply Patterns

### With SELLING_CLIMAX
- Sequence: NO_DEMAND context + SELLING_CLIMAX = Supply peak without demand support
- Indicates bearish exhaustion

### With SUPPLY_COMING_IN
- Sequence: NO_DEMAND context + SUPPLY_COMING_IN = Supply unopposed
- Indicates aggressive breakdown likely

### With INCREASING_SUPPLY
- Sequence: NO_DEMAND context + INCREASING_SUPPLY = Supply escalation unopposed
- Indicates sustained supply pressure

### With SUPPLY_DRYING_UP
- Sequence: NO_DEMAND context + SUPPLY_DRYING_UP = Equilibrium/consolidation
- Neither buyers nor sellers present

---

## Context Rules

### In Downtrend
- NO_DEMAND = Trend continuing unopposed
- Price likely to decline further
- Support levels at risk
- Reversal deferred

### At Support Levels
- NO_DEMAND = Support failing
- No buyers defending
- Breakdown likely
- Lower levels may test

### After Large Selloff
- NO_DEMAND = Capitulation complete
- No one wants to buy
- Climax condition met
- Reversal may follow

### During Consolidation
- NO_DEMAND = Consolidation extending
- Neither side dominant
- Breakout deferred
- Equilibrium holding

---

## Validation Framework

### Post-Detection Validation (1-8 bars forward)

1. **Demand Entry**
   - Buyers appear: Reversal likely
   - Hidden demand emerges: Accumulation begins
   - No demand: Bearish pressure continues

2. **Price Progression**
   - Lower closes: NO_DEMAND bias confirmed
   - Holds support: Consolidation
   - Reversal up: Capitulation or hidden demand

3. **Supply Response**
   - Supply continues: Breakdown likely
   - Supply fades: Consolidation
   - Supply absent: Demand may enter

4. **Volume Context**
   - Low volume: Consolidation
   - Escalating volume: Supply continuing
   - Volume climax: Potential reversal

---

## Real-Market Examples

### Example 1: NO_DEMAND in Downtrend
```
Context: Downtrend for 5 bars
Bar: Down bar, close weak
Demand patterns: None detected
Result: NO_DEMAND flagged
Follow-up: 2 more bars down, no demand enters
Outcome: Trend continues, downtrend supported
Inference: Absence of buyers confirms bearish bias
```

### Example 2: NO_DEMAND at Support
```
Context: Price at support level
Bar: At support, close neutral/weak
Demand: No buyers evident
Result: NO_DEMAND flagged
Follow-up: Break below support
Outcome: Buyers didn't defend, breakdown confirmed
Inference: Support failed due to demand absence
```

### Example 3: NO_DEMAND Before Reversal
```
Context: Downtrend ending
Bar: Down bar, very low volume
Demand: Completely absent
Result: NO_DEMAND flagged
Follow-up: Bar 2: Hidden demand appears
Outcome: Reversal begins, accumulation revealed
Inference: Demand was hidden, not truly absent
```

---

## Production Status

**Detection:** ACTIVE (contextual observation collector)

**Scoring Weight:** 0.00 (non-scoring)

**Qualification:** May flag context (not affect actionability)

**Contextual Use:** YES (identifies demand vacuum)

**Actionability:** Indirectly (context for other patterns)

**Status:** PRODUCTION-ACTIVE, NON-SCORING

---

## Implementation Notes

**Current Detector:** `evidence/demand.py::_collect_no_demand()` (presumed production active)

**Called In:** `EvidenceEngine.collect()` → `collect_demand()` (production path)

**Output Role:** Contextual flag, not SmartMoneyEvidence

**Semantic Classification:** DRAFT (awaiting audit clarification)

---

## Semantic Clarification Needed

**Critical Issue:** NO_DEMAND semantics require clarification

Possible interpretations:
1. **Absence Definition:** What patterns constitute "no demand"?
   - Complete absence of all demand patterns?
   - Absence of primary demand patterns?
   - Below-threshold demand evidence?

2. **Hidden Demand Problem:** 
   - HIDDEN_DEMAND by definition is not visible
   - How to distinguish NO_DEMAND from hidden-but-present demand?
   - Requires explicit exclusion logic

3. **Contextual vs Scoring:**
   - Is NO_DEMAND contextual observation or evidence?
   - If contextual, weight 0.00 is correct
   - If evidence, requires different treatment

**Audit Need:** Semantic quality audit must address these issues

---

## Expected Audit Path

### Short-term (Pending)
- [ ] Semantic clarity audit (definition refinement)
- [ ] Hidden demand interaction audit
- [ ] Contextual vs scoring classification

### Medium-term (Pending)
- [ ] Candidate audit (scanner representation)
- [ ] Qualification impact analysis
- [ ] False positive validation

### Timeline
- **Semantic audit:** 1-2 days (critical path)
- **Full audit:** ~3-5 days
- **Status decision:** Upon audit completion

---

## Possible Issues to Resolve

1. **Definition Ambiguity**
   - Clarify: Complete absence vs low presence
   - Specify: Which patterns trigger/exclude NO_DEMAND
   - Determine: Threshold for "no demand" classification

2. **Hidden Demand Conflict**
   - Can both be true simultaneously?
   - How to distinguish in real-time?
   - Requires explicit detection logic

3. **Scoring vs Context**
   - If weight 0.00, why flag at all?
   - Or does it affect qualification differently?
   - Purpose in production must be defined

4. **Validation Difficulty**
   - Hard to prove absence
   - Easy to mistake consolidation for NO_DEMAND
   - Requires careful test-case definition

---

## Related Patterns

- **DEMAND_COMING_IN** - Opposite (demand entering)
- **HIDDEN_DEMAND** - Related (demand present but hidden)
- **DEMAND_DRYING_UP** - Related (demand fading)
- **INCREASING_DEMAND** - Opposite (demand escalating)
- **SELLING_CLIMAX** - Often concurrent (supply peak without demand)

---

## Key Principle

NO_DEMAND = Absence of buyer participation visible in market.

Not active selling (that's supply patterns).
Not consolidation (that's balanced action).
Just: No one is buying.

Context flag that prices lack support.

---

## Audit Requirements

**CRITICAL:** Semantic audit must address:

1. **Definition Clarity** - What constitutes NO_DEMAND?
2. **Hidden Demand Handling** - Exclusion logic?
3. **Scoring Purpose** - Why weight 0.00 in production?
4. **Qualification Impact** - Does it affect actionability?
5. **False Positive Reduction** - Validation tests?

Without semantic clarity, NO_DEMAND cannot graduate to formal scoring.

---

**Status:** PRODUCTION-ACTIVE, SEMANTIC AUDIT REQUIRED (August 2026)  
**Confidence Level:** MODERATE (implementation active, semantics unclear)  
**Production Ready:** Needs semantic clarification  
**Weight:** 0.00 (contextual, non-scoring)  
**Critical Issue:** Semantic definition requires audit refinement  
**Next Step:** Semantic quality audit to resolve ambiguities
