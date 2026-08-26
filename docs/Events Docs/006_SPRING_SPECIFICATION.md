# Specification: SPRING

**Version:** 1.0  
**Status:** Provisional-Production (August 20, 2026)  
**Audit Events:** 37 (complete audit, gated system)  
**Win Rate:** 61-67% (with gates), 43% (raw, ungated)  
**Weight:** 0.75 (with gates active)

---

## Purpose

Detect a sharp downward probe (spring/shakeout) that fails to continue downward, forming a potential reversal signal in downtrends or market bottoms.

Spring represents professional shake-out of weak holders followed by reversal attempt.

**Key reversal signal** when combined with subsequent demand evidence.

---

## Classical Definition (Tom Williams)

Spring occurs in weak markets or at support levels where:
- Price makes a sharp downward move
- Volume spike on the selling
- Price then immediately recovers
- Close recovers significant portion of drop
- Leaves trapped sellers at the low

Professional buyers testing lower levels and creating panic before aggressive buying begins.

---

## Wyckoff Interpretation

Spring = Smart Money Testing Supply at Lower Levels

Part of Accumulation Phase:
- Initial selling drive
- Spring (test/reversal)
- Secondary test (lower)
- Final stage (accumulation completion)

Represents the "shaking" of weak hands before accumulation.

---

## Professional Interpretation

Professional money is testing market supply at lower levels.

Initial panic selling trapped weak holders.

Buyers absorbing selling aggressively.

Setup for reversal once foundation confirmed.

---

## Detection Conditions

### Condition 1: Downtrend or Weakness Context
- Price in downtrend or support area
- Prior bearish action establishes "weakness" foundation
- Sellers have been active

### Condition 2: Sharp Down Move (Effort)
- Down bar with significant decline
- Volume spike on the move down
- Clear aggressive selling attempt
- Testing lower levels

### Condition 3: Reversal/Recovery (Result Contradiction)
- Price recovers sharply from lows
- Close well above the low (strong recovery)
- Shows buying overcoming selling
- Often closes near or above open

### Condition 4: Low Volume on Recovery (Professional Absorption)
- Recovery volume LOW (not panic bid)
- Shows quiet absorption, not climactic buying
- Professional accumulation characteristic
- Weak holders shaken, professionals absorbing

### Confirmation Factors (Important for Gates)
- **Confirmation Gate 1: CONFIRMED**
  - Must be confirmed by subsequent demand pattern
  - HIDDEN_DEMAND, BUYING_CLIMAX, or equivalent
  - Spring alone = not actionable

- **Confirmation Gate 2: LOW_VOLUME**
  - Recovery volume must be low
  - Shows professional absorption
  - Validates quiet accumulation

- **Confirmation Gate 3: SHALLOW**
  - Spring doesn't break prior structural lows
  - Recovery significant from absolute low
  - Shows support holding

---

## Output

**Event Type:** SmartMoneyEvidence

**Properties:**
- Code: SPRING
- Category: DEMAND (bullish context)
- Direction: BULLISH
- Role: Reversal signal (gated)
- Strength: MODERATE (ungated), STRONG (when all gates pass)

**Interpretation:**
Professional testing and absorption of selling pressure.
Setup for reversal once foundations confirmed.

---

## Confidence Calculation

Composite of:
- Downmove magnitude (30% weight) - degree of testing
- Recovery strength (35% weight) - buyers' dominance
- Recovery volume lowness (35% weight) - professional characteristic

Higher downmove + stronger recovery + lower volume = higher confidence

---

## Weight System

**Base Weight:** 0.75

**Gate Application:**
- CONFIRMED: Requires downstream demand pattern
- LOW_VOLUME: Recovery volume below average
- SHALLOW: Spring doesn't exceed prior support break

**Weight Reduction:**
- Without CONFIRMED gate: Weight effectively 0 (standalone not actionable)
- Without LOW_VOLUME: Weight 0.50 (less professional)
- Without SHALLOW: Weight 0.30 (structural support violated)
- All gates active: Weight 0.75 (full production)

---

## Why Gating Is Essential

Spring signals alone are NOT actionable because:
1. Spring can occur in false reversals (dead-cat bounces)
2. Reversal requires confirmation from demand patterns
3. Low volume is KEY to professional distinction
4. Shallow move shows support legitimacy

Gate system ensures:
- Only professional springs scored
- Confirmation from other patterns required
- Low-quality springs filtered
- Integration with broader demand picture

---

## False Positives to Avoid

### DO NOT Detect:

1. **Down Move + Strong Recovery Volume**
   - Likely panic bid, not professional absorption
   - High volume = weak holders buying back, not professionals
   - Confidence low, actionability zero

2. **Down Move + Recovery + Subsequent Breakdown**
   - Spring failed (price breaks lower after recovery)
   - Not a true spring (no support holding)
   - Reversal not confirmed

3. **Down Move at Market Bottoms + Small Recovery**
   - May be capitulation, not spring
   - Requires confirmation from structural analysis
   - Spring framework alone insufficient

4. **In Strong Downtrend + No Support Level**
   - Spring without foundation
   - No structural support to hold on
   - High failure risk

---

## Detection Semantics

**Core Rule:** Professional testing of lower levels with quiet absorption.

This is observed as:
- Sharp downmove (testing/shaking)
- Strong recovery (absorption power)
- Low recovery volume (professional characteristic)

**Real-market constraint:**
- Do NOT trigger on every down-recover sequence
- Must show professional absorption characteristics (low volume)
- Must have structural support or confirmation

---

## What SPRING Must NOT Claim

SPRING alone must NOT imply:
- Automatic reversal continuation
- Confirmed bottom (requires structure)
- Trade entry point (needs confirmation)
- Bullish continuation guaranteed

Those require:
- CONFIRMED gate (other demand patterns active)
- LOW_VOLUME gate (professional absorption)
- SHALLOW gate (support holding)
- Structural context validation

---

## Gate Requirements Detailed

### Gate 1: CONFIRMED

**Definition:** Subsequent bar(s) must show demand pattern evidence

**Acceptable Confirmations:**
- HIDDEN_DEMAND (buyers entering on weakness)
- BUYING_CLIMAX (demand intensity)
- INCREASING_DEMAND (demand rising)
- Other bullish patterns in next 1-3 bars

**Rationale:** Spring alone is ambiguous; confirmation removes ambiguity

**Timing:** Within 1-3 bars of spring for tight integration

### Gate 2: LOW_VOLUME

**Definition:** Recovery volume below average/prior bars

**Percentile:** Volume Percentile <= SPRING_MAX_RECOVERY_VOLUME_PERCENTILE

**Rationale:** Professional accumulation is quiet; high volume = panic buyers

**Example:**
```
Down bar volume: 85 percentile (spike down)
Recovery bar volume: 20 percentile (quiet)
GATE PASSES: Professional characteristic confirmed
```

### Gate 3: SHALLOW

**Definition:** Spring doesn't violate structural support

**Structure Validation:**
- Prior swing low NOT broken by spring
- OR recent support level respected
- OR structural invalidation doesn't occur

**Rationale:** Structural support holding validates consolidation foundation

---

## Interaction with Other Patterns

### With HIDDEN_DEMAND
- Sequence: SPRING → HIDDEN_DEMAND = Ideal accumulation setup (very bullish)
- CONFIRMED gate passes when HIDDEN_DEMAND follows

### With BUYING_CLIMAX
- Same bar: Unlikely (opposite volume profiles)
- Sequence: SPRING (test) → BUYING_CLIMAX (demand entry) = Setup completion

### With SUPPLY_COMING_IN
- Sequence: SPRING (test) → SUPPLY_COMING_IN (rejection) = False reversal (watch closely)
- Indicates spring was trap, not true reversal

### With SHAKEOUT
- Related but different: Both test lows
- SHAKEOUT more aggressive; SPRING more subtle
- Both part of professional shake-out methodology

---

## Context Rules

### In Strong Downtrend
- SPRING = Professional accumulation beginning
- High probability of reversal
- Test succeeds, bounce follows

### At Major Support Levels
- SPRING = Professional defending key level
- Support holding on test
- Reversal likely

### After Large Volume Decline
- SPRING = Absorption of panic selling
- Professional buying on weakness
- Reversal risk building

### Before Market Bottoms
- SPRING = Marker of bottom formation
- Often appears 1-2 bars before actual bottom
- Structural confirmation needed

---

## Validation Framework

### Post-Detection Validation (1-8 bars forward)

1. **Confirmation Pattern Appearance**
   - HIDDEN_DEMAND within 1-3 bars: Very bullish
   - Other demand patterns: Moderate bullish
   - No confirmation: Reversal risk zero, spring fails

2. **Volume Trend**
   - Stays low: Accumulation continues
   - Spikes up: Demand activation (breakout)
   - Spike down: Supply entering (false spring)

3. **Price Structure**
   - Higher low formed: Accumulation confirmed
   - Equals low: Testing continues (hold)
   - Breaks lower: Spring fails, trend continues down

4. **Spread Trend**
   - Narrow: Consolidation normal
   - Wide: Increased conflict (demand competition)

---

## Real-Market Examples

### Example 1: Classic Spring Setup
```
Condition: Downtrend, approaching support
Spring bar: Down bar, spike volume, strong recovery, low recovery volume
Next bar: HIDDEN_DEMAND detected (CONFIRMED gate passes)
Result: ✅ SPRING scored (0.75 weight, all gates active)
Follow-up: 3-bar consolidation, then breakout higher
Outcome: Textbook accumulation pattern
```

### Example 2: Failed Spring
```
Condition: Downtrend
Spring bar: Down bar, volume, recovery, LOW recovery volume (gates pass)
But: No confirmation pattern within 3 bars
Next bars: Price continues down, breaks support
Result: Spring was trap, not reversal
Lesson: Gates require confirmation, not just price action
```

### Example 3: Spring Without Low Volume
```
Down bar: Volume spike down
Recovery: Strong recovery BUT high volume
Gates: LOW_VOLUME gate FAILS (panic bid, not professional)
Result: ❌ SPRING NOT scored (weight 0.75 → 0 without gate)
Interpretation: Panic buyers, not accumulation
```

---

## Audit Results Summary (Complete)

**Audit Scope:**
- 37 events across 8 symbols
- Historical validation (complete audit)
- Win rate with all gates: 61-67%
- Win rate without gates: 43% (ungated = too much noise)

**Key Finding:**
- Gates are ESSENTIAL for professional performance
- Ungated spring triggers too many false signals
- LOW_VOLUME gate critical to professional distinction
- CONFIRMED gate required for actionability

**Status:** Provisional-Production CONFIRMED, gates frozen

---

## Production Status

**Detection:** ACTIVE (production-path collector runs every bar)

**Scoring Weight:** 0.75 (with gates active)

**Gate Requirements:** All 3 gates REQUIRED for scoring
- CONFIRMED (downstream demand)
- LOW_VOLUME (professional absorption)
- SHALLOW (structural support holding)

**Qualification:** Gated system integrated into qualification engine

**Contextual Use:** YES (identifies accumulation setups)

**Actionability:** GATED (actionable only when all gates pass)

---

## Implementation Notes

**Current Detector:** `evidence/demand.py::_collect_spring()`

**Called In:** `EvidenceEngine.collect()` → `collect_demand()`

**Gate Implementation:** Qualification + professional scoring integration

**Recent Audit:** Complete (37 events, gates validated)

**Semantics:** FROZEN (gate structure locked in)

---

## Future Enhancements

### Version 2.0
- Gate threshold refinement
- Multi-timeframe correlation
- Structural level integration
- Volatility adjustment

### Version 3.0
- Smart Money spring identification
- Spring magnitude classification
- Professional vs panic spring discrimination
- Reversal probability enhancement

### Version 4.0
- Machine learning gate optimization
- Real-time market condition adaptation
- Cross-symbol spring correlation
- Ensemble gate methodology

---

## Key Principle

SPRING = Professional testing with quiet accumulation.

GATES = Professional filter ensuring quality signals.

BASE (0.75) = Production weight with all gates.

NO GATES = Ungated score (effectively 0, integration with confirmation patterns).

---

## Comparison: Ungated vs Gated

| Aspect | Ungated | Gated |
|--------|---------|-------|
| Win Rate | 43% | 61-67% |
| False Positives | High | Low |
| Actionability | Low | High |
| Weight | Effectively 0 | 0.75 |
| Confidence | Moderate | Very High |

---

**Status:** FROZEN (August 20, 2026)  
**Confidence Level:** VERY HIGH (37-event audit complete, gates validated)  
**Production Ready:** YES (with gates active)  
**Weight:** 0.75 (all gates required)  
**Gate Implementation:** Locked in, no changes without new evidence
