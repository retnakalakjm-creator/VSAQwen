# Specification: NO_SUPPLY

**Version:** 1.0  
**Status:** Production-Connected, Contextual / Non-Scoring (August 24, 2026)  
**Audit Status:** Complete - All 8 stages passed  
**Production Events:** 23 (across 8 symbols)  
**Win Rate:** 60.87% (matches market baseline 60.80%)  
**Scoring Weight:** 0.00 (contextual only, non-scoring)  
**Runtime Weight Range:** 0.90-1.50 (observed, but not applied to scoring)

---

## Purpose

Detect bearish environmental conditions where supply evidence is absent or minimal during price action.

NO_SUPPLY represents the absence of significant selling pressure in a bearish environment, which is contextual but not actionable as independent evidence.

**Contextual observation** for understanding market participation and structural context.

---

## Classical Definition (Tom Williams)

NO_SUPPLY occurs when:
- Bearish environment exists (price under pressure or consolidating down)
- No aggressive selling appears
- Low volume activity
- Narrow spreads
- Price holds despite bearish context
- Absence of supply aggression

Market waiting for supply or consolidating before next move.

---

## Wyckoff Interpretation

NO_SUPPLY = Absence of Distribution Pressure

Indicates:
- Distribution phase not active
- Smart money not currently exiting
- Equilibrium or consolidation phase
- Waiting for supply or demand to emerge
- Not yet ready for significant directional move

Contextual marker, not directional evidence.

---

## Professional Interpretation

There is no active selling visible in this bearish context.

Professional distribution is not underway.

Market is waiting or consolidating.

Neutral context flag, not bullish or bearish signal alone.

---

## Detection Conditions (Frozen)

### Condition 1: Bearish Environment
- `ctx.is_bearish_environment()` = TRUE
- Price under bearish pressure or consolidating
- Overall market structure bearish

### Condition 2: Bearish Bar
- Close lower than open OR neutral close in bearish context
- Downward or flat price action
- Not rising sharply

### Condition 3: Low Volume
- Volume below normal levels
- Percentile-based threshold
- Shows fading participation
- Not active trading

### Condition 4: Narrow Spread
- Intrabar range is narrow
- Spread Percentile below threshold
- Minimal effort shown
- Quiet market action

### Confirmation Factors (Not Mandatory)
- Volume decreasing vs prior bar (16/23 events)
- Weak close near lows (12/23 events)

---

## Output

**Event Type:** ContextualObservation (not SmartMoneyEvidence)

**Properties:**
- Code: NO_SUPPLY
- Category: CONTEXTUAL (environmental flag)
- Direction: NEUTRAL (bearish context, not directional)
- Role: Context marker, not evidence
- Strength: WEAK (absence, not presence)

**Interpretation:**
No selling aggression detected despite bearish environment.
Market consolidating, waiting for next move.
Contextual information only, not actionable alone.

---

## Weight System

**Scoring Weight:** 0.00 (non-scoring)

**Status:** Contextual only, does not contribute to scoring

**Rationale:**
- Absence patterns don't score in VSA
- Presence patterns (supply evidence) do score
- NO_SUPPLY is complement to supply evidence
- Used for environmental context, not direct evidence

**Registry/Reference Weight:** 1.00 (documentation only)

**Runtime Weight:** 0.90-1.50 (observed but not applied)
- WeightCalculator processes all patterns
- Weight calculated even for non-scoring patterns
- Not used in final scoring (multiplied by 0.00)

---

## Frozen Detector Semantics (Production Definition)

**Requirements (all mandatory):**
1. Bearish environment (`ctx.is_bearish_environment()` = TRUE)
2. Bearish bar (close lower/neutral)
3. Low volume (below threshold)
4. Narrow spread (below threshold)

**Point-in-time:** YES (evaluated on each bar)

**Target-bar only:** YES (detection bar only, not lookback)

**Semantic Quality:** 100% (23/23 events met all requirements)

**Philosophy:** Production definition locked, no future changes

---

## Complete Audit Results (August 24, 2026)

**Audit Completion Status:** ✅ ALL STAGES PASSED

### Candidate Audit
- **Status:** ✅ PASS
- **Production events:** 23 (across 8 symbols)
- **Coverage:** 8/8 symbols (comprehensive)
- **Cheap candidates:** 225
- **Expected emissions:** 23 (perfect match)
- **Normal rejections:** 202

### Semantic Quality Audit
- **Status:** ✅ PASS (100%)
- **Bearish environment:** 23/23 ✓
- **Bearish bar:** 23/23 ✓
- **Low volume:** 23/23 ✓
- **Narrow spread:** 23/23 ✓
- **Semantic failures:** 0

### Interaction Audit
- **Status:** ✅ PASS (confirming, not contradictory)
- **Interaction rate:** 100% (all events have interaction)
- **Supply interaction:** SUPPLY_DRYING_UP (23/23 events, 100%)
- **Demand interaction:** TEST (4/23 events)
- **Self-conflict:** Excluded (correct)
- **Contradiction penalty:** Not justified

### Interaction Outcome Audit

**Performance by Event Type:**

| Group | Events | Positive Rate | Mean Return |
|-------|--------|---------------|-------------|
| NO_SUPPLY + SUPPLY_DRYING_UP | 19 | 63.16% | +0.45% |
| NO_SUPPLY + SUPPLY_DRYING_UP + TEST | 4 | 50.00% | +3.73% |

**Finding:** Small population, no reliable penalty justification

### Outcome Audit
- **Status:** ✅ PASS
- **Positive outcomes:** 14 (60.87%)
- **Negative outcomes:** 9 (39.13%)
- **Flat outcomes:** 0
- **Mean 8-bar return:** +1.02%
- **vs Market baseline:** +0.07 pp directional lift
- **Return vs baseline:** -2.81 pp (below market)

**Interpretation:** Performance matches market baseline; no incremental decision value

### Decision-Value Audit
- **Status:** ✅ PASS (clear decision: non-scoring)
- **Candidate positive rate:** 60.87%
- **Market baseline:** 60.80%
- **Lift:** +0.07 pp (negligible)
- **Candidate share:** 0.20% of eligible events (very rare)
- **Decision:** No incremental decision value demonstrated

**Justification:** Pattern does not add value over baseline; remains contextual

### Production-Path Readiness Audit
- **Status:** ✅ PASS
- **Registry:** YES (documented)
- **Supply-map scoring entry:** NO (not scoring)
- **Demand-map scoring entry:** NO (not scoring)
- **Weight Calculator:** Dynamic (but multiplied by 0.00)
- **Runtime weights:** 0.90-1.50 (valid range)
- **Duplicate emissions:** 0
- **Semantic failures:** 0
- **Production score mutation:** FALSE

### Frozen Decision
- **Status:** Production-connected, contextual/non-scoring
- **Weight:** 0.00 (non-scoring)
- **Interaction penalty:** NONE (no contradiction)
- **Rejection rule:** NONE (contextual allowed)
- **Detector changes:** NONE (definition frozen)

---

## What NO_SUPPLY Must NOT Claim

NO_SUPPLY alone must NOT imply:
- Supply is absent (absence from detection, not market fact)
- Bullish continuation (context only, not directional)
- Support will hold (no evidence)
- Safe entry point (no actionable signal)
- Demand will enter (speculation)

Those require:
- Positive demand evidence (separate patterns)
- Structural support confirmation
- Extended testing validation
- Qualification engine assessment

---

## Relationship to Other Patterns

### With SUPPLY_DRYING_UP (100% overlap in audit)
- 100% of NO_SUPPLY events coincide with SUPPLY_DRYING_UP
- Both indicate absence of aggressive selling
- Complementary observations, not contradictory
- Supply drying (supply leaving) vs NO_SUPPLY (supply not visible)

### With SUPPLY_COMING_IN (Opposite)
- SUPPLY_COMING_IN: Supply entering aggressively
- NO_SUPPLY: Supply not entering
- Mutually exclusive in typical bars

### With TEST (Minor overlap)
- TEST pattern in 4/23 events (17.4%)
- TEST is contextual pattern
- Interaction not contradictory

### With Demand Patterns
- NO_SUPPLY is supply-context pattern
- Interacts with demand patterns orthogonally
- Does not favor or oppose demand evidence

---

## Interaction with Other Patterns

### With SUPPLY_DRYING_UP (100% documented overlap)
- Sequence: Supply drying → NO_SUPPLY = Supply exhaustion confirmed
- Same bar: Both occur simultaneously (100% overlap)
- Status: Confirming, no penalty applied

### With SELLING_CLIMAX
- Opposite concept: Climax = high volume; NO_SUPPLY = low volume
- Unlikely same bar
- Different supply phases

### With BUYING_CLIMAX
- Opposite context: Climax = supply pressure; NO_SUPPLY = no supply
- Different signals
- Not concurrent typically

---

## Context Rules

### In Downtrend
- NO_SUPPLY = Trend nearing end or consolidating
- Rally possible but not guaranteed
- Waiting phase

### At Support Levels
- NO_SUPPLY = Support may hold (no selling pressure)
- But also no buying pressure (ambiguous)
- Context only

### After Selling Climax
- NO_SUPPLY = Climax fade
- Supply exhaustion after intense selling
- Consolidation likely

### During Equilibrium
- NO_SUPPLY = Balanced context
- Neither supply nor demand active
- Waiting for breakout direction

---

## Real-Market Examples

### Example 1: NO_SUPPLY in Bearish Context
```
Context: Downtrend for 5 bars
Bar: Bearish bar, low volume, narrow spread
Bearish environment: YES
Result: NO_SUPPLY detected (23 total in audit)
Meaning: No active selling, consolidating
Outcome: Waiting phase, next move TBD
Interpretation: Contextual only, not actionable signal
```

### Example 2: NO_SUPPLY Before Supply Drying
```
Context: Downtrend ending
Bar: Bearish environment, quiet action
Volume: Very low
Spread: Narrow
Result: NO_SUPPLY + SUPPLY_DRYING_UP both detected (100% overlap)
Outcome: Supply and selling both exhausted
Interpretation: Capitulation phase, reversal risk building
```

### Example 3: NO_SUPPLY with TEST
```
Context: Consolidation area
Bar: Bearish environment maintained
Action: Quiet, testing lows
Result: NO_SUPPLY + TEST detected (4 events)
Outcome: Mixed performance (50% positive in this subset)
Interpretation: Ambiguous, requires demand confirmation
```

---

## Production Status (Frozen)

**Detection:** ✅ ACTIVE (production-path collector runs every bar)

**Scoring Weight:** 0.00 (contextual only)

**Production Role:** Context flag (environmental information)

**Qualification Impact:** Indirect (context for other decisions)

**Actionability:** None alone (requires supporting evidence)

**Status:** PRODUCTION-CONNECTED, CONTEXTUAL / NON-SCORING

---

## Implementation Notes

**Current Detector:** `evidence/supply.py::_collect_no_supply()` (production active)

**Called In:** `EvidenceEngine.collect()` → `collect_supply()` (production path)

**Weight Application:** 0.00 (not applied to scoring)

**Semantic Definition:** FROZEN (production locked)

**Recent Audit:** Complete (August 24, 2026) - All 8 stages passed

---

## Why NO_SUPPLY Is Non-Scoring

**Decision Rationale:**

1. **No Incremental Value**
   - Positive rate (60.87%) matches baseline (60.80%) exactly
   - Return (-2.81 pp below baseline) worse than market
   - 0.20% share of eligible events (extremely rare)

2. **Absence Pattern Philosophy**
   - Absence of evidence is not evidence of bullish movement
   - Supply not present ≠ demand will enter
   - Contextual information, not actionable signal

3. **Ambiguity Problem**
   - Could indicate consolidation (neutral)
   - Could indicate supply about to resume (bearish)
   - Could indicate demand hidden (bullish)
   - Can't distinguish without other patterns

4. **Interaction Finding**
   - 100% overlap with SUPPLY_DRYING_UP
   - Smaller sample in interaction subsets
   - No reliable penalty or adjustment justified

---

## Possible Future Enhancement

If NO_SUPPLY were to be scored (future versions):

1. **Require strong bullish confluence**
   - Multiple demand patterns present
   - NOT just absence of supply
   - Active buyer evidence needed

2. **Combine with demand patterns**
   - NO_SUPPLY + DEMAND_COMING_IN = Strong bullish setup
   - NO_SUPPLY alone = insufficient

3. **Support structure requirements**
   - Test of support level
   - Quantified structural context
   - Price-based confirmation needed

4. **Extended duration**
   - Multiple bars of NO_SUPPLY
   - Not single-bar observation
   - Trend of supply absence

---

## Related Patterns

- **SUPPLY_DRYING_UP** - Supply fading (100% overlap documented)
- **SUPPLY_COMING_IN** - Supply entering (opposite)
- **SELLING_CLIMAX** - Supply intensity (opposite extreme)
- **TEST** - Minor interaction pattern (4/23 events)
- **NO_DEMAND** - Parallel contextual pattern

---

## Key Principle

NO_SUPPLY = Absence of visible selling in bearish environment.

Not bullish signal; just contextual marker.

Requires supporting evidence (demand patterns) for actionability.

Remains production-connected for environmental context.

---

## Audit Principles Preserved

- Absence patterns don't score in VSA (weight 0.00 preserved)
- Presence patterns score (supply evidence)
- Interaction overlap 100% with SUPPLY_DRYING_UP (documented)
- No decision value over baseline = no scoring weight
- Contextual role preserved, actionability minimal
- Production path exists but scoring path does not

---

**Status:** PRODUCTION-CONNECTED, CONTEXTUAL / NON-SCORING (August 24, 2026)  
**Confidence Level:** VERY HIGH (all 8 audit stages passed)  
**Production Ready:** YES (actively deployed as context)  
**Scoring Weight:** 0.00 (contextual, non-scoring by design)  
**Recent Validation:** August 24, 2026 (comprehensive 8-stage audit complete)  
**Decision:** FROZEN (contextual/non-scoring, no changes)
