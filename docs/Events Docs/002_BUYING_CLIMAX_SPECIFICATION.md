# Specification: BUYING_CLIMAX

**Version:** 1.0  
**Status:** Audit-Complete (August 20, 2026)  
**Audit Commits:** 4 (candidate, campaign-qualified, semantic quality audits)  
**Audit Events:** Comprehensive validation across all production paths

---

## Purpose

Detect the climactic conclusion of a bullish campaign where professional buying has reached exhaustion or a turning point.

Buying Climax represents a potential reversal opportunity or supply exhaustion test.

**NOT an automatic sell signal** - just an observation of campaign exhaustion.

---

## Classical Definition (Tom Williams)

Buying Climax occurs when professional buyers conclude their accumulation phase.

Typical characteristics:
- Very high volume
- Wide spread
- Strong close
- Weak continuation follow-through
- Often at market highs

Professional money cannot hide large accumulation.

---

## Wyckoff Interpretation

Buying Climax represents exhaustion of a bullish campaign.

May lead to:
- Selling Climax (reversal)
- Markup Continuation (higher)
- Secondary Test (consolidation)
- Distribution Phase (top formation)

**NOT confirmation of reversal** - it is an observation of campaign intensity.

---

## Professional Interpretation

Professional accumulation has reached peak intensity.

Buying pressure exhausted or switching direction.

Possible reversal or consolidation ahead.

**Further validation required.**

---

## Detection Conditions

### Condition 1: Bullish Campaign Context
- Must be in uptrend or accumulation phase
- Preceded by meaningful rising price action
- Campaign should show progression (HH/HL pattern or equivalent)

### Condition 2: Climactic Volume
- Volume Percentile >= BUYING_CLIMAX_MIN_VOLUME_PERCENTILE
- Must be exceptionally high (not just above average)
- Suggests professional activity at scale

### Condition 3: Wide Spread
- Spread Percentile >= BUYING_CLIMAX_MIN_SPREAD_PERCENTILE
- Large intrabar range indicates effort
- Shows buying competition against resistance

### Condition 4: Strong Close Position
- Close Ratio >= BUYING_CLIMAX_MIN_CLOSE_RATIO
- Close well above midpoint (bullish close)
- Demonstrates buying strength through day
- But: WEAK close would indicate climax + distribution

### Confirmation Factors (Not Mandatory)
- Higher volume on close
- Strong close ratio (0.70+)
- Wide spread
- Higher high established
- No follow-through volume next bar

---

## Output

**Event Type:** SmartMoneyEvidence

**Properties:**
- Code: BUYING_CLIMAX
- Category: SUPPLY (bearish context)
- Direction: BEARISH (from supply perspective, bullish exhaustion)
- Role: Primary weakness / supply pressure
- Strength: STRONG

**Interpretation:**
From a bearish perspective, buying exhaustion = future supply opportunity.
From a bullish perspective, campaign intensity = near-term weakness before continuation or reversal.

---

## Confidence Calculation

Composite of:
- Volume Percentile (50% weight)
- Spread Percentile (30% weight)
- Close Ratio (20% weight)

Normalized mean = Confidence score

Higher volume + wider spread + stronger close = higher confidence

---

## Weight System (IMPORTANT: Dynamic Runtime Weights)

**Registry Weight:** 1.00 (Static metadata)

**Runtime Weight:** DYNAMIC (calculated per bar)
- Minimum observed: 0.90
- Maximum observed: 2.00  
- Mean observed: ~1.4464
- Calculated by: `WeightCalculator._buying_climax_weight(ctx)`
- Factors: Market environment, trend state, structural progression, climactic evaluation

**Empirical Reference Weight:** 0.38 (Used only in analysis/testing, NOT production runtime)

**Critical Distinction:**
- Do NOT confuse registry weight (1.00) with runtime weight (dynamic 0.90-2.00)
- Do NOT use empirical reference weight (0.38) as current production weight
- Runtime weight is dynamically calculated, not static

**Status:** Production-active, dynamically weighted

---

## False Positives to Avoid

### DO NOT Detect:

1. **High Volume + Weak Close**
   - Likely Selling Climax, not buying exhaustion
   - Indicates supply entry, not demand exit

2. **High Volume + Narrow Spread**
   - Likely Hidden Supply (hidden weakness)
   - Not true climactic buying

3. **Average Volume + Wide Spread**
   - Normal volatility, not professional climax
   - Insufficient volume for professional activity

4. **Narrow Spread on Buying Climax**
   - Not true climax (climax requires effort = wide spread)
   - May be absorption or quiet buying

---

## Detection Semantics

**Core Rule:** Professional buying has reached a peak intensity point.

This is observed as:
- Exceptional volume (top percentile)
- Large price range (wide spread)
- Buying strength evidenced by close position

**Real-market constraint:** Do NOT require textbook-perfect checklist.

A useful buying climax:
- May not have all confirmations present
- Is identified from volume + spread + close combination
- Gets validated by subsequent price action
- Becomes meaningful in context of campaign phase

---

## What BUYING_CLIMAX Must NOT Claim

BUYING_CLIMAX alone must NOT imply:
- Automatic reversal
- Confirmed top formation
- Distribution phase beginning
- Sell signal
- Supply dominance

Those conclusions belong to:
- Subsequent price action response
- Qualification engine validation
- Supporting supply evidence
- Structural context analysis

---

## Interaction with Other Patterns

### With UPTHRUST (SIGNIFICANT OVERLAP)

**Critical Finding from Audit:**
- Overlap rate: 181/181 (100% of campaign-qualified BUYING_CLIMAX events)
- ALL BUYING_CLIMAX events coincide with UPTHRUST

**Performance Breakdown:**
- UPTHRUST alone (53 events): 66.04% positive, +4.75% mean return (STRONG)
- UPTHRUST + INCREASING_DEMAND (119 events): 51.69% positive, +2.20% mean return (WEAK)
- Remaining combinations (9 events): Varied performance

**Interaction Penalty Analysis:**
- Provisional penalty tested: 0.20 (for INCREASING_DEMAND + UPTHRUST combination only)
- Effect: Improves aggregate rate from 56.35% → 57.12% positive
- Status: PROVISIONAL/ANALYSIS-ONLY, NOT in production yet
- Justification: Pure UPTHRUST subset is strong (66.04%), doesn't warrant suppression

**Real-Market Interpretation:**
UPTHRUST + BUYING_CLIMAX often form campaign completion patterns. The weaker INCREASING_DEMAND + UPTHRUST subset suggests different market dynamics. Not all UPTHRUST + BUYING_CLIMAX combinations are bearish.

### With SELLING_CLIMAX
- Same bar: Rare (conflicting directions)
- Sequence: Buying Climax → Selling Climax = Double Climax (strong reversal signal)

### With SUPPLY_COMING_IN
- Same bar: May occur (high volume, supply entering)
- Sequence: Buying Climax → Supply Coming In = Natural progression

### With SUPPLY_DRYING_UP
- Same bar: Possible (climax + no follow-up supply)
- Interpretation: Climax without supply follow-up = more bearish

### With INCREASING_DEMAND
- Sequence: INCREASING_DEMAND (escalation) → BUYING_CLIMAX (exhaustion) = Campaign peak
- Together: Represents demand intensity reaching limit

---

## Context Rules

### In Uptrend
- Buying Climax = Campaign near completion
- High probability of consolidation or pullback
- Reversal risk elevated

### In Early Accumulation
- Buying Climax = False start
- Likely followed by shakeout/test
- Not yet a reversal signal

### After Breaking Resistance
- Buying Climax = Acceptance test of new level
- May establish support on pullback
- Continuation likely after consolidation

### At Market Highs
- Buying Climax = Potential top formation
- Risk of reversal elevated
- Requires confirmation from supply patterns

---

## Validation Framework

### Post-Detection Validation (1-8 bars forward)

1. **Area Holding** (nearest support)
   - Immediate pullback: 0-2 bars
   - Consolidation: 2-4 bars
   - Continuation: 4-8 bars

2. **Supply Response**
   - Strong supply entering: Bearish confirmation
   - No supply: Buying may resume
   - Hidden supply: Absorption (watch closely)

3. **Volume Trend**
   - Declining volume: Normal after climax
   - Sustained high volume: Possible distribution
   - Volume spike: Supply entering

4. **Spread Trend**
   - Narrowing spreads: Consolidation normal
   - Wide spreads: Renewed conflict (data)

---

## Unit Tests

### Positive: BUYING_CLIMAX Detected

```
Volume Percentile:  92 (very high)
Spread Percentile:  85 (wide)
Close Ratio:        0.82 (strong close)
Campaign:           Up trend active
Result:             ✅ DETECTED
```

### Negative: High Volume But Weak Close

```
Volume Percentile:  95 (very high)
Spread Percentile:  85 (wide)
Close Ratio:        0.25 (weak close)
Campaign:           Up trend active
Result:             ❌ NOT DETECTED (likely Selling Climax)
```

### Negative: Average Volume

```
Volume Percentile:  60 (average)
Spread Percentile:  85 (wide)
Close Ratio:        0.82 (strong close)
Campaign:           Up trend active
Result:             ❌ NOT DETECTED (insufficient volume for professional activity)
```

### Negative: Narrow Spread

```
Volume Percentile:  95 (very high)
Spread Percentile:  45 (narrow)
Close Ratio:        0.82 (strong close)
Campaign:           Up trend active
Result:             ❌ NOT DETECTED (narrow spread ≠ climactic effort)
```

### Boundary: All Thresholds

```
Volume Percentile:  = THRESHOLD
Spread Percentile:  = THRESHOLD
Close Ratio:        = THRESHOLD
Campaign:           Up trend active
Result:             ✅ DETECTED (boundary inclusive)
```

---

## Production Status

**Detection:** ACTIVE (production-path collector runs every bar)

**Scoring Weight:** 1.00 (primary supply/bearish evidence)

**Qualification:** Standalone not required, but contributes to supply context

**Contextual Use:** YES (identifies campaign exhaustion points)

**Actionability:** NOT standalone (requires confirmation from supply patterns)

---

## Comprehensive Audit Summary (August 20-21, 2026)

**Audit Scope (13 Commits):**
1. ✅ Candidate audit: Representation validated (432 candidates, 181 qualified)
2. ✅ Campaign-qualified audit: Qualification layer verified
3. ✅ Semantic quality audit: Pattern definition confirmed
4. ✅ Interaction/Contradiction audit: UPTHRUST overlap identified (100%)
5. ✅ Interaction outcome audit: Performance by interaction type analyzed
6. ✅ Combination audit: UPTHRUST + INCREASING_DEMAND analysis
7. ✅ Production-path readiness: Runtime weight architecture validated
8. ✅ Runtime weight provenance: Dynamic weighting confirmed (0.90-2.00)

**Campaign-Qualified Events:** 181 (100% have UPTHRUST overlap)

**Production-Path Verification:**
- Production emissions: 181 (no duplicates)
- Campaign mismatches: 0
- Runtime weights out of bounds: 0
- Runtime bounds: 0.50 .. 2.00
- Interaction penalty in production: NO
- Production score mutation: NO

**Decision-Value Findings:**
- Candidate positive decisive rate: 56.35%
- Market baseline: 60.79%
- Gap: -4.44 percentage points (below baseline)
- Mean 8-bar return: +3.03% (market: +3.83%)
- With provisional 0.20 penalty (INCREASING_DEMAND + UPTHRUST only): 57.12% positive

**Status:** Production-active CONFIRMED, audit-complete
- Registry weight: 1.00 (static)
- Runtime weight: Dynamic (0.90-2.00)
- Interaction penalty: Provisional 0.20 (ANALYSIS-ONLY, not in production)

---

## Future Enhancements

### Version 2.0
- Volume spike detection (specific threshold)
- Higher-timeframe context (weekly confluence)
- Weak close variant detection
- Distribution phase classification

### Version 3.0
- Smart Money accumulation profile matching
- Campaign phase lifecycle progression
- Composite Operator activity correlation
- Nearby supply/demand confluence scoring

### Version 4.0
- Machine learning confidence adjustment
- Real-time market regime adaptation
- Cross-symbol correlation analysis
- Seasonal pattern overlay

---

## Implementation Notes

**Current Detector:** `evidence/supply.py::_collect_buying_climax()`

**Called In:** `EvidenceEngine.collect()` → `collect_supply()`

**Updates Required:**
- None (recently audited, semantics frozen)

**Related Patterns:**
- SELLING_CLIMAX (opposite direction)
- SUPPLY_COMING_IN (supply response)
- UPTHRUST (campaign start)
- NO_DEMAND (absence of support)

---

## References

**Wyckoff Analysis:**
- Accumulation Phase completion
- Campaign exhaustion
- Reversal preparation phase

**Smart Money Concept:**
- Professional money exhaustion
- Effort reaching limit
- Potential supply entry point

**Technical Analysis:**
- Top formation signals
- Volume climax patterns
- Distribution phase identification

---

**Status:** FROZEN (August 20, 2026)  
**Confidence Level:** HIGH (recent audit complete)  
**Production Ready:** YES  
**Next Review:** When new market evidence emerges
