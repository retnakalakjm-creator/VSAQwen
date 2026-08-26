# Specification: HIDDEN_DEMAND

**Version:** 1.0  
**Status:** Implementation-Ready, Audit-Diagnostics Prepared (August 20, 2026)  
**Implementation:** 6 diagnostic audit scripts (933 lines) ready for execution  
**Audit Status:** Awaiting diagnostics run

---

## Purpose

Detect demand that is not evident from price action alone but is revealed through volume and close analysis.

Hidden Demand occurs when buyers enter quietly at lower prices while price is falling, without showing obvious buying pressure signals.

**Key observation** for understanding true accumulation hidden beneath bearish surface action.

---

## Classical Definition (Tom Williams)

Hidden Demand represents professional buying that does not appear as aggressive upward pressure.

Typical characteristics:
- Price falling or stable
- Volume increasing
- Close above midpoint despite down bar
- Strong close (buyers' effort halting selling)
- No obvious support bars

Professional accumulation is not always obvious.

---

## Wyckoff Interpretation

Hidden Demand = Demand Entering During Supply Phase

Indicates:
- Smart money accumulation beginning
- Supply being absorbed quietly
- Foundation building for reversal
- Setup for aggressive breakout when buyers emerge

Represents conflict between sellers and hidden buyers.

---

## Professional Interpretation

Demand is present in market even though price falling.

Buyers entering on weakness (professional accumulation strategy).

Selling interest exists but faces hidden absorption.

Price may appear weak but reversal risk building.

---

## Detection Conditions

### Condition 1: Down Bar or Neutral Bar
- Close lower than or equal to open
- Bearish price action on bar
- Suggests initial supply/weakness

### Condition 2: High Volume
- Volume Percentile >= HIDDEN_DEMAND_MIN_VOLUME_PERCENTILE
- Indicates professional-scale activity
- Rules out quiet absorption

### Condition 3: Strong Close Position
- Close Ratio > HIDDEN_DEMAND_MIN_CLOSE_RATIO (strong close)
- Close in upper half of bar despite down bar
- Shows buyers' effort halting selling
- Buyers' defense preventing weakness

### Confirmation Factors (Not Mandatory)
- High volume on close
- Open < Close (buyers winning despite down bar)
- Close above previous close (strength)
- Higher close than opening (reversal)
- Wide spread showing conflict

---

## Output

**Event Type:** SmartMoneyEvidence

**Properties:**
- Code: HIDDEN_DEMAND
- Category: DEMAND (bullish context)
- Direction: BULLISH
- Role: Supporting demand evidence
- Strength: MODERATE to STRONG (depending on confirmation presence)

**Interpretation:**
Demand entering at lower prices while sellers remain active.
Creates imbalance favoring potential accumulation and reversal on buy-side activation.

---

## Confidence Calculation

Composite of:
- Volume Percentile (40% weight) - proves professional activity
- Close Ratio (40% weight) - indicates buyer strength
- Spread Percentile (20% weight) - shows market conflict

Higher volume + stronger close + wide spread = higher confidence in hidden demand

---

## Weight

**Production Weight:** TBD (To be determined through audit diagnostics)

**Status:** Implementation-ready, audit diagnostics prepared

---

## Why "Hidden"?

Demand is hidden because:
1. Price falling = normally reads as bearish
2. Volume high = could be selling
3. But close strong = reveals buyer defense
4. Buyers invisible on surface, visible through analysis

Classic smart money behavior - accumulating on weakness without showing hand.

---

## False Positives to Avoid

### DO NOT Detect:

1. **Down Bar + High Volume + Weak Close**
   - Likely Selling Climax, not hidden demand
   - Close weakness means sellers won
   - No demand opposition evident

2. **Down Bar + Average Volume + Strong Close**
   - Insufficient volume for professional demand
   - Likely normal support bounce, not smart money
   - Not significant enough to call "hidden demand"

3. **Down Bar + High Volume + Average Spread**
   - Possible absorption, not hidden demand
   - Narrow spread = less conflict
   - Professional demand would show effort (spread)

4. **Up Bar with High Volume**
   - Obvious demand, not hidden
   - If buyers already showing hand, not "hidden"
   - This is BUYING_CLIMAX, not hidden demand

---

## Detection Semantics

**Core Rule:** Professional buyers are entering at lower prices while sellers push price down.

This is observed as:
- Volume spike (professional scale)
- Down bar (price moving lower)
- Strong close (buyers defend, sellers can't hold selling)

**Real-market constraint:**
- Do NOT require textbook-perfect strong close
- Strong relative to volume and open/low is sufficient
- Confirmation factors help but not mandatory
- Context of prior price action matters

---

## What HIDDEN_DEMAND Must NOT Claim

HIDDEN_DEMAND alone must NOT imply:
- Automatic upward reversal
- Confirmed bottom formation
- Buying pressure equivalent to obvious climax
- Trade entry signal
- End of downtrend

Those require:
- Subsequent price action response
- Qualification engine validation
- Supporting evidence from other patterns
- Structural/campaign context

---

## Interaction with Other Patterns

### With SELLING_CLIMAX
- Same bar: May occur (climax with hidden demand = strong accumulation setup)
- Sequence: SELLING_CLIMAX → HIDDEN_DEMAND = Extended accumulation (very bullish)

### With INCREASING_DEMAND
- Same bar: Possible (both indicate demand, different evidence)
- Both active = very strong demand confluence

### With SUPPLY_COMING_IN
- Same bar: May occur (supply exiting while demand entering)
- Suggests professional absorption of supply

### With SUPPLY_DRYING_UP
- Same bar: May occur (supply waning while buyers enter)
- Indicates supply exhaustion coinciding with demand entry

### With SPRING
- Sequence: SPRING (reverse) → HIDDEN_DEMAND (accumulation) = Textbook accumulation continuation
- Indicates reversal from lows followed by quiet buying

---

## Context Rules

### In Downtrend
- Hidden Demand = Trend base forming
- Accumulation phase likely beginning
- Reversal risk building

### Near Support Levels
- Hidden Demand = Professional support at key level
- Demand awaiting breakout for aggressive buying
- Technical level breakdown gets tested

### After Large Volume Selloff
- Hidden Demand = Buyers entering on weakness
- Professional accumulation behavior
- Usually arrests decline, builds reversal

### In Late Downtrend
- Hidden Demand = Market bottoming dynamics
- Base formation in progress
- Reversal setup active

---

## Validation Framework

### Post-Detection Validation (1-8 bars forward)

1. **Price Action Response**
   - Immediate reversal: Demand very strong
   - Consolidation: Demand holding selling
   - Continued decline: Sellers still active but opposed

2. **Volume Trend**
   - Declining next bars: Sellers in control but weakening
   - Sustained high: Demand ongoing
   - Volume spike up: Demand activation/breakout

3. **Strong Close Persistence**
   - Repeats on next bars: Consistent demand
   - Reverses to weakness: Demand diminishing
   - Continues strong: Accumulation phase active

4. **Price Structure**
   - Higher low formed: Demand very aggressive
   - Equal low: Demand present but not dominant
   - Breakdown: Sellers still have control but challenged

---

## Real-Market Examples

### Example 1: Hidden Demand at Support
```
Bar: Down bar at support level
Volume: Very high (90 percentile)
Close: Strong (0.70), well above open
Result: HIDDEN_DEMAND detected
Follow-up: Price consolidates, slowly rallies
Outcome: Demand was real, buyers waiting
```

### Example 2: Hidden Demand in Downtrend
```
Bar: Down bar in strong downtrend
Volume: High (75 percentile)
Close: Strong (0.65)
Result: HIDDEN_DEMAND detected
Follow-up: Price continues lower next 3 bars
Outcome: Sellers eventually overcome, demand absorbed
Lesson: Hidden demand doesn't always reverse immediately
```

### Example 3: Hidden Demand + Climax
```
Bar: Down bar with exceptional volume
Volume: 98 percentile (climactic selling)
Close: Strong (0.75)
Result: HIDDEN_DEMAND + SELLING_CLIMAX both detected
Follow-up: Immediate reversal next bar
Outcome: Double confirmation = powerful signal
```

---

## Audit Preparation (August 20, 2026)

**6 Diagnostic Audit Scripts Ready:**

1. **Candidate Audit** - Verification in scanner output
2. **Semantic Quality Audit** - Pattern definition validation
3. **Interaction Audit** - Conflict detection with other patterns
4. **Decision-Value Audit** - Net benefit calculation
5. **Conflict Outcome Audit** - Performance of conflicting events
6. **Penalty Sensitivity Audit** - Weight optimization testing

**Status:** All diagnostic infrastructure prepared, awaiting execution

**Timeline:** Audit execution pending codebase integration completion

---

## Production Status (Anticipated)

**Detection:** READY (awaiting integration)

**Scoring Weight:** TBD (to be determined from audit)

**Qualification:** Standalone not required (awaiting qualification audit)

**Contextual Use:** YES (will identify hidden demand entering market)

**Actionability:** NOT standalone (requires confirmation from other demand patterns)

---

## Implementation Notes

**Current Detector:** `evidence/demand.py::_collect_hidden_demand()` (implementation complete)

**Called In:** `EvidenceEngine.collect()` → `collect_demand()` (ready)

**Diagnostic Scripts:** 933 lines prepared (6 comprehensive audit scripts)

**Semantics:** DRAFT (awaiting audit finalization)

---

## Audit Diagnostics Ready

**Script 1: Candidate Audit (131 lines)**
- Validates hidden demand detection in scanner
- Verifies representation across all symbols
- Confirms production path integration

**Script 2: Semantic Quality Audit (158 lines)**
- Tests pattern definition against real-market data
- Validates detection conditions
- Confirms threshold appropriateness

**Script 3: Interaction Audit (155 lines)**
- Identifies same-bar conflicts with other patterns
- Measures conflict frequency
- Analyzes conflict impact on scoring

**Script 4: Decision-Value Audit (154 lines)**
- Measures net benefit to scoring system
- Calculates outcome correlation
- Determines appropriate weight range

**Script 5: Conflict Outcome Audit (225 lines)**
- Compares clean events vs conflicted events
- Measures performance gap
- Justifies conflict penalty if needed

**Script 6: Penalty Sensitivity Audit (110 lines)**
- Tests weight range 0.25 → 1.4
- Identifies optimal weight
- Confirms confidence improvement

---

## Expected Audit Timeline

**Phase 1: Execution** (1-2 days)
- Run all 6 diagnostic scripts
- Collect audit data across 8 symbols
- Aggregate results

**Phase 2: Analysis** (1-2 days)
- Evaluate audit findings
- Determine production readiness
- Identify weight and gates

**Phase 3: Documentation** (1 day)
- Freeze specification
- Update PRIMARY_VSA_EVENT_MATRIX.md
- Publish audit conclusion

**Total Timeline:** 3-5 days to production decision

---

## Future Enhancements

### Version 2.0
- Close ratio threshold refinement
- Volume spike detection specificity
- Integration with trend context
- Demand accumulation profiling

### Version 3.0
- Smart Money accumulation tracking
- Hidden demand persistence detection
- Layered demand identification
- Multi-bar hidden demand sequences

### Version 4.0
- Machine learning confidence adjustment
- Real-time supply/demand imbalance scoring
- Hidden demand magnitude estimation
- Reversal probability weighting

---

## Related Patterns

- **SUPPLY_COMING_IN** - Opposite (supply exiting)
- **SELLING_CLIMAX** - Opposite side (supply intensity)
- **INCREASING_DEMAND** - Opposite of supply patterns
- **SPRING** - Reverse move (downstream pattern)
- **SHAKEOUT** - Aggressive selling (different pattern)

---

## Key Principle

Hidden Demand = Demand present but not obvious.

Requires analysis to detect.

Price falling + Volume high + Close strong = Buyers entering on weakness.

Professional move to accumulate without signaling intentions.

---

**Status:** IMPLEMENTATION READY (August 20, 2026)  
**Audit Readiness:** COMPLETE (6 diagnostic scripts prepared)  
**Confidence Level:** TBD (pending audit execution)  
**Production Timeline:** 3-5 days to decision  
**Recent Preparation:** August 20, 2026 (933 lines diagnostic code)
