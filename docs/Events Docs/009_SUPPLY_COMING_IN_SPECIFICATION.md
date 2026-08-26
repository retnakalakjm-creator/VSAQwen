# Specification: SUPPLY_COMING_IN

**Version:** 1.0  
**Status:** Production-Active (August 22, 2026)  
**Audit Status:** Complete - All stages passed  
**Production Events:** 189 (across 8 symbols)  
**Win Rate:** 62.96% (above market baseline 60.68%)  
**Registry Weight:** 1.00  
**Runtime Weight:** Dynamic (0.70-1.70, mean 1.0243)

---

## Purpose

Detect supply entering the market while price is declining with increased volume.

Supply Coming In represents active selling pressure entering during downtrend or weakness.

**Key bearish signal** for identifying supply accumulation at key levels.

---

## Classical Definition (Tom Williams)

Supply Coming In occurs when:
- Price declining or testing support
- Volume increasing significantly
- Sellers are visibly active
- Spread widening (aggressive selling)
- Close near lows (sellers in control)

Professional money actively selling at levels.

---

## Wyckoff Interpretation

Supply Coming In = Distribution Phase Active Selling

Indicates:
- Smart money selling at key levels
- Professional distribution underway
- Supply accumulation for collapse/reversal
- Preparation for markup phase completion and reversal

Part of distribution phase characterized by professional exit.

---

## Professional Interpretation

Sellers entering the market aggressively.

Professional money committing to distribution/exit.

Supply pressure evident at lower prices.

Foundation for continuation or reversal downward.

---

## Detection Conditions (From Candidate Audit)

### Condition 1: Down Bar or Weakness Context
- Close lower or equal to open
- Bearish price action
- Shows initial supply/selling

### Condition 2: Above-Average or Increasing Volume
- Volume Percentile >= SUPPLY_COMING_IN_MIN_VOLUME_PERCENTILE
- Shows professional-scale activity
- Indicates active participation, not quiet selling

### Condition 3: Above-Average Spread
- Spread Percentile >= SUPPLY_COMING_IN_MIN_SPREAD_PERCENTILE
- Shows effort in selling (pressure)
- Indicates competition/resistance

### Condition 4: Non-Climactic
- NOT extreme volume (volume < climax threshold)
- NOT selling climax signal (different pattern)
- Steady selling, not exhaustion

### Confirmation Factors (Not Mandatory)
- Lower close (sellers in control)
- Volume sustained from prior bar
- Wide close (sellers establishing position)
- Decreasing momentum (selling continues)

---

## Output

**Event Type:** SmartMoneyEvidence

**Properties:**
- Code: SUPPLY_COMING_IN
- Category: SUPPLY (bearish context)
- Direction: BEARISH
- Role: Supporting supply evidence
- Strength: MODERATE to STRONG (depending on confirmation presence)

**Interpretation:**
Supply entering at lower levels while sellers remain active.
Active accumulation for distribution or reversal.
Support for downtrend or breakdown.

---

## Confidence Calculation

Composite of:
- Volume Percentile (45% weight) - shows participation scale
- Spread Percentile (35% weight) - indicates effort against support
- Price level (20% weight) - shows sellers' conviction at lower levels

Higher volume + wider spread + lower price level = higher confidence in supply entry

---

## Weight (TBD)

**Provisional Weight:** TBD (Audit in progress)

**Status:** Under audit, not yet assigned production weight

**Rationale:** 
- Candidate audit just completed
- Semantic quality audit pending
- Interaction analysis required
- Decision-value audit needed

---

## Opposite Pattern Relationship

SUPPLY_COMING_IN is the bearish counterpart to DEMAND_COMING_IN (bullish):
- DEMAND_COMING_IN: Buyers entering at higher prices (bullish)
- SUPPLY_COMING_IN: Sellers entering at lower prices (bearish)

Should have similar audit frameworks and weight ranges.

---

## False Positives to Avoid

### DO NOT Detect:

1. **Down Bar + Climactic Volume**
   - This is SELLING_CLIMAX, not supply coming in
   - Climax = exhaustion; coming in = steady entry
   - Different patterns with different implications

2. **Down Bar + Average Volume**
   - Insufficient volume for professional participation
   - Likely retail or normal selling, not smart money
   - Not significant enough to call "supply coming in"

3. **Down Bar + High Volume + Narrow Spread**
   - Volume present but no effort shown (spread)
   - Likely absorption, not supply entry
   - Professional supply would show spread (competition)

4. **In Strong Downtrend + Very Low Volume**
   - Low volume doesn't show "supply coming in"
   - May be continuation but not "coming in"
   - Requires volume showing active participation

---

## Detection Semantics

**Core Rule:** Professional sellers entering at lower prices during downward action.

This is observed as:
- Down bar (direction)
- Above-average volume (scale of participation)
- Above-average spread (effort against support)
- Non-climactic (controlled selling, not panic)

**Real-market constraint:**
- Do NOT require textbook-perfect progression
- Steady entry without extremes is the signal
- Volume and spread confirmation matters
- Climax patterns are different (excluding condition)

---

## What SUPPLY_COMING_IN Must NOT Claim

SUPPLY_COMING_IN alone must NOT imply:
- Automatic continuation downward
- Confirmed downtrend
- Trade entry signal (requires confirmation)
- Support for sustained decline
- Sellers in control

Those require:
- Subsequent price progression
- Volume maintenance
- Structural support
- Qualification validation
- Multiple supporting patterns

---

## Interaction with Other Patterns

### With HIDDEN_SUPPLY
- Opposite perspective of same phenomenon
- HIDDEN_SUPPLY: Supply at higher prices during up bar
- SUPPLY_COMING_IN: Supply at lower prices during down bar
- Sequence: SUPPLY_COMING_IN (active) → HIDDEN_SUPPLY (at higher prices) = Distribution continuation

### With INCREASING_SUPPLY
- Sequence: SUPPLY_COMING_IN (steady) → INCREASING_SUPPLY (intense) = Supply escalation (very bearish)
- Same bar: Possible (both show supply but different characteristics)

### With SELLING_CLIMAX
- Sequence: SUPPLY_COMING_IN (steady) → SELLING_CLIMAX (intense) = Supply peak (climactic)
- Same bar: Contradictory (coming in = controlled; climax = exhaustion)

### With DEMAND_COMING_IN
- Sequence: SUPPLY_COMING_IN (sellers) → DEMAND_COMING_IN (buyers) = Support forming
- Indicates sellers met significant opposition at lower levels

---

## Context Rules

### In Downtrend
- Supply Coming In = Trend continuation support
- Sellers defending downtrend
- Breakdown likely

### At Support Levels
- Supply Coming In = Aggressive support rejection
- Sellers attacking support
- Breakdown probability elevated

### After Consolidation
- Supply Coming In = Resolution bearish
- Breakdown from consolidation
- Continuation likely downward

### In Early Downtrend
- Supply Coming In = Trend foundation
- Initial distribution
- Breakdown to lower levels likely

---

## Validation Framework

### Post-Detection Validation (1-8 bars forward)

1. **Volume Continuation**
   - Sustained high volume: Supply continuing
   - Fading volume: Supply weakening
   - Volume spike: Potential climax (watch)

2. **Price Progression**
   - Lower closes: Supply dominance
   - Consolidation: Supply present but opposed
   - Reversal: Supply overcome by demand

3. **Demand Response**
   - No demand: Supply uncontested
   - Hidden demand: Support building
   - Demand coming in: Trend resistance

4. **Spread Trend**
   - Widening: Continued selling effort
   - Narrowing: Consolidation (normal)
   - Extreme: Climax risk (watch)

---

## Real-Market Examples

### Example 1: Supply Coming In During Decline
```
Context: Strong downtrend established
Bar: Down bar at new low
Volume: 70 percentile (above average)
Spread: 65 percentile (wide)
Close: Weak (0.25, near low)
Non-climactic: YES (not extreme)
Result: ✅ SUPPLY_COMING_IN detected
Follow-up: Volume continues, price holds lower
Outcome: Supply supports continued decline
```

### Example 2: Failed Supply Coming In
```
Context: Downtrend at support level
Bar: Down bar at support
Volume: 72 percentile (above average)
Spread: 70 percentile (wide)
Non-climactic: YES
Result: ✅ SUPPLY_COMING_IN detected
But: Demand comes in heavily next bar
Outcome: Support held, sellers failed
Lesson: Supply present but insufficient to break support
```

### Example 3: Supply Climax
```
Historical: Down bar at low
Detection: SUPPLY_COMING_IN confirmed
Same Pattern: Next bar shows SELLING_CLIMAX
Conclusion: Supply intensity reaching exhaustion
Interpretation: Climax often marks reversal
```

---

## Complete Audit Results (August 22, 2026)

**Audit Completion Status:** ✅ ALL STAGES PASSED

### Candidate Audit
- **Status:** ✅ PASS
- **Production events:** 189 (across 8 symbols)
- **Coverage:** 8/8 symbols (comprehensive)
- **Cheap candidates:** 1,022
- **Campaign-qualified:** 370 bars
- **Normal rejections:** 181 (expected)

### Semantic Quality Audit
- **Status:** ✅ PASS (100%)
- **Down bar:** 189/189 ✓
- **High volume:** 189/189 ✓
- **Above-average spread:** 189/189 ✓
- **Weak close:** 189/189 ✓
- **Increasing volume:** 189/189 ✓
- **Semantic failures:** 0

### Interaction Audit
- **Status:** ✅ PASS (confirming, not contradictory)
- **Supply-conflict events:** 147/189 (77.78%)
- **Conflict type:** INCREASING_SUPPLY (100%)
- **Clean events:** 42/189 (22.22%)

**Critical Finding: Interaction is CONFIRMING (not contradictory)**
```
Clean SUPPLY_COMING_IN:
  - Positive rate: 54.76%
  - Mean return: +3.61%

SUPPLY_COMING_IN + INCREASING_SUPPLY:
  - Positive rate: 65.31% (+10.54 pp IMPROVEMENT)
  - Mean return: +3.81% (+0.20 pp improvement)
```

**Decision:** No penalty applied; interaction strengthens the signal

### Outcome Audit
- **Status:** ✅ PASS
- **Positive outcomes:** 119 (62.96%)
- **Negative outcomes:** 70 (37.04%)
- **Mean 8-bar return:** +3.76%
- **vs Market baseline:** +2.17 pp lift
- **Directional lift:** Positive

### Weight Sensitivity Audit
- **Status:** ✅ PASS
- **Tested weights:** 0.25, 0.30, 0.38, 0.45, 0.50
- **Result:** Runtime weighting does not change with fixed weights
- **Qualified events:** 189 at all weights
- **Actionable events:** 56 at all weights (29.63%)
- **Decision:** Dynamic weighting preserved, not static

### Production-Path Readiness Audit
- **Status:** ✅ PASS
- **Collection path:** YES (evidence/supply.py)
- **Engine collection:** YES (via collect_supply)
- **Registry:** YES
- **Duplicate emissions:** 0
- **Campaign mismatches:** 0
- **Weight out-of-bounds:** 0
- **Production score mutation:** NO

### Runtime Weight Analysis
- **Base weight:** 1.00 (registry)
- **Runtime range:** 0.70 - 1.70
- **Runtime mean:** 1.0243
- **Empirical reference:** 0.38 (historical only, not used)
- **Weight calculator:** WeightCalculator._supply_coming_in_weight(ctx)
- **Adjustments:** Trend and structural context-dependent

---

## Frozen Semantics (Production Definition)

**Requirements (all mandatory):**
1. Down/bearish bar
2. High volume (Volume Percentile >= threshold)
3. Above-average spread (Spread Percentile >= threshold)
4. Weak close (Close Ratio < threshold)
5. Increasing volume vs prior bar (volume progression)

**Philosophy:** Preserve meaningful imperfect real-market evidence rather than require textbook-perfect formations

---

## Production Status (ACTIVE)

**Detection:** ✅ ACTIVE (production-path collector runs every bar)

**Scoring Weight:** 
- **Registry:** 1.00 (static)
- **Runtime:** Dynamic (0.70-1.70, context-dependent)
- **Empirical reference:** 0.38 (historical calibration only, NOT used in production)

**Qualification:** Integrated and active

**Contextual Use:** YES (identifies supply entering at lower levels)

**Actionability:** YES (full production deployment)

**Status:** PRODUCTION-ACTIVE / AUDIT-COMPLETE

---

## Implementation Notes

**Current Detector:** `evidence/supply.py::_collect_supply_coming_in()` (production active)

**Called In:** `EvidenceEngine.collect()` → `collect_supply()` (production path)

**Registry Weight:** 1.00 (static metadata)

**Runtime Weight:** Calculated by `WeightCalculator._supply_coming_in_weight(ctx)` (dynamic, context-dependent)

**Recent Audit:** Complete (August 22, 2026) - All 8 stages passed

**Semantics:** FROZEN (production definition locked in)

---

## Production Deployment Summary

**Promotion Status:** ✅ PROMOTED TO PRODUCTION (August 22, 2026)

**Key Decision Points:**
1. **All audit stages passed:** Candidate ✓, Semantic ✓, Interaction ✓, Outcome ✓, Weight sensitivity ✓, Production-path ✓
2. **Positive directional lift:** +2.17 pp above market baseline
3. **No penalty applied:** INCREASING_SUPPLY overlap is CONFIRMING (+10.54 pp improvement), not contradictory
4. **Production-ready:** Perfect ranking, no mutations, weights in bounds
5. **Dynamic weighting confirmed:** Runtime adapts to context (0.70-1.70 range)

**Deployment Status:** ACTIVE in production scanner

---

## Comparison: SUPPLY_COMING_IN vs Related Patterns

| Aspect | Supply Coming In | Hidden Supply | Selling Climax |
|--------|-----------------|---------------|-----------------|
| Bar Type | Down | Up | Down |
| Volume | High | High | Very High |
| Close | Weak | Weak | Weak |
| Effort | Visible | Hidden | Climactic |
| Purpose | Active entry | Quiet entry | Exhaustion |
| Severity | Moderate | Moderate | Extreme |

---

## Key Principle

Supply Coming In = Sellers entering at lower prices actively.

Opposite of DEMAND_COMING_IN (buyers at higher prices).

Should follow similar audit framework and produce comparable insights.

Base observation with solid candidate audit (68 events, 64.71% positive).

---

## Related Patterns

- **DEMAND_COMING_IN** - Opposite (bullish)
- **INCREASING_SUPPLY** - Opposite of INCREASING_DEMAND (bearish escalation)
- **SELLING_CLIMAX** - Opposite side climax version
- **SUPPLY_DRYING_UP** - Supply exhaustion (opposite condition)
- **HIDDEN_SUPPLY** - Hidden selling (similar but up bar)

---

**Status:** PRODUCTION-ACTIVE (August 22, 2026)  
**Confidence Level:** VERY HIGH (all 8 audit stages passed)  
**Production Ready:** YES (actively deployed)  
**Weight:** 1.00 registry, dynamic runtime (0.70-1.70)  
**Recent Validation:** August 22, 2026 (comprehensive 8-stage audit complete)
