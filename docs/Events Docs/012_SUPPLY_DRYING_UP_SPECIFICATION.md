# Specification: SUPPLY_DRYING_UP

**Version:** 1.0  
**Status:** Production-Active (August 25, 2026)  
**Audit Status:** Complete - All 8 stages passed  
**Production Events:** 225 (across 8 symbols)  
**Win Rate:** 61.78% (above baseline 60.79%)  
**Mean Return:** +3.56% (below baseline +3.83%)  
**Registry Weight:** 1.00  
**Supply-Map Weight:** 0.60  
**Runtime Weight:** 1.00 (static)  
**Production Role:** Contextual supply-exhaustion signal  
**Opposite Pattern:** DEMAND_DRYING_UP

---

## Purpose

Detect the weakening or exhaustion of selling supply as volume declines while price remains stable or falls slightly.

Supply Drying Up represents the end of selling enthusiasm and potential setup for reversal or consolidation.

**Important observation** of supply exhaustion without aggressive buying pressure.

---

## Classical Definition (Tom Williams)

Supply Drying Up occurs when selling activity diminishes even as price holds or falls slightly.

Typical characteristics:
- Price stable or slightly lower
- Volume declining
- Narrow spreads
- Weak close or neutral close
- No follow-through selling energy

Professional distribution ending, not yet buyers' turn.

---

## Wyckoff Interpretation

Supply Drying Up = End of Distribution Phase

Indicates:
- Selling pressure exhausted
- Equilibrium approaching
- Preparation for accumulation or reversal
- Transition point in market cycle

Separates aggressive supply from consolidation/accumulation.

---

## Professional Interpretation

Sellers have completed distribution or took profits.

Supply energy is fading.

Waiting period before next directional move.

Reversal risk building, but not yet confirmed.

---

## Detection Conditions (Projected)

### Condition 1: Down or Stable Price
- Close lower or equal to previous close
- Downtrend context or consolidation
- No aggressive buying pressure

### Condition 2: Declining Volume
- Volume Percentile < threshold (declining)
- Volume decreasing from prior bars
- Shows selling interest fading
- NOT climactic volume

### Condition 3: Narrow Spread
- Spread Percentile < threshold (narrow)
- Small intrabar range
- Indicates reduced conflict/effort
- Quiet market action

### Confirmation Factors (Not Mandatory)
- Close above open (slight strength)
- Higher close than prior bar
- Very low volume (extremely quiet)
- Narrow range with small body

---

## Output

**Event Type:** SmartMoneyEvidence

**Properties:**
- Code: SUPPLY_DRYING_UP
- Category: DEMAND (bullish context from supply perspective)
- Direction: BULLISH (exhaustion signal)
- Role: Supporting contextual observation
- Strength: MODERATE

**Interpretation:**
Selling supply fading, energy depleting.
Transition phase, waiting for next move.
Reversal setup building (not yet confirmed).

---

## Confidence Calculation (Projected)

Composite of:
- Volume Percentile decline (40% weight) - shows fading supply
- Spread Percentile (30% weight) - indicates reduced effort
- Price stability (30% weight) - shows demand holding without strength

Lower volume + narrower spread + stable price = higher confidence in supply exhaustion

---

## Weight (TBD)

**Provisional Weight:** To be determined through audit

**Status:** Production-active, awaiting formal audit

---

## Relationship to DEMAND_DRYING_UP

SUPPLY_DRYING_UP is the bearish counterpart to DEMAND_DRYING_UP (bullish):
- DEMAND_DRYING_UP: Buyers leaving, volume declining (bearish)
- SUPPLY_DRYING_UP: Sellers leaving, volume declining (bullish)

Should have similar audit frameworks and likely comparable weight ranges.

---

## False Positives to Avoid

### DO NOT Detect:

1. **Down Bar + Climactic Volume**
   - This is SELLING_CLIMAX, not supply drying up
   - Climax = exhaustion with power; drying = weakness
   - Different patterns with different implications

2. **Down Bar + Average Volume**
   - Insufficient decline to confirm drying
   - Supply may still be present
   - Not yet exhausted

3. **Down Bar + High Volume + Wide Spread**
   - Contradictory (wide spread = effort, low volume = no effort)
   - Unlikely real-market combination
   - Skip detection

4. **Up Bar with Declining Volume**
   - Demand drying, not supply drying
   - Different pattern (demand exhaustion)
   - Not supply drying up

---

## Detection Semantics

**Core Rule:** Selling supply is present but fading.

This is observed as:
- Price holding (sellers still present but weak)
- Volume declining (fewer sellers)
- Narrow spread (less effort needed)

Not demand entering (no buying pressure).
Just fading supply (sellers leaving).

---

## What SUPPLY_DRYING_UP Must NOT Claim

SUPPLY_DRYING_UP alone must NOT imply:
- Confirmed reversal
- Demand dominance
- Trade entry signal
- Automatic strength ahead
- End of downtrend

Those require:
- Subsequent demand entry patterns
- Qualification validation
- Supporting evidence
- Price structure context

---

## Interaction with Other Patterns

### With DEMAND_COMING_IN
- Sequence: SUPPLY_DRYING_UP (sellers weak) → DEMAND_COMING_IN (buyers enter) = Bullish transition (high probability reversal)
- Same bar: Unlikely (opposite signals)

### With DEMAND_DRYING_UP
- Same bar: Impossible (opposite signals)
- Sequence: SUPPLY_DRYING_UP (sellers weak) → DEMAND_DRYING_UP (buyers weak) = Equilibrium consolidation

### With HIDDEN_DEMAND
- Sequence: SUPPLY_DRYING_UP → HIDDEN_DEMAND (buyers entering as sellers exit) = Accumulation beginning
- Same bar: Possible but less likely

### With INCREASING_SUPPLY
- Sequence: INCREASING_SUPPLY (escalation) → SUPPLY_DRYING_UP (exhaustion) = Supply peak followed by fade
- Same bar: Contradictory (escalation vs drying)

---

## Context Rules

### In Downtrend
- Supply Drying Up = Trend nearing conclusion
- Rally likely
- Reversal risk building

### Near Support Levels
- Supply Drying Up = Support solidifying
- Supply wavering at key level
- Test upward probable

### After Large Volume Selloff
- Supply Drying Up = Normal profit-taking ending
- Sellers taking off table
- Continuation may restart

### After Selling Climax
- Supply Drying Up = Climax fade
- Supply exhaustion confirmed
- Reversal likely

---

## Validation Framework

### Post-Detection Validation (1-8 bars forward)

1. **Demand Response**
   - Demand entering: Bullish confirmation
   - No demand: Supply may resume
   - Hidden demand: Accumulation phase

2. **Volume Trend**
   - Stays low: Consolidation continues
   - Increases (demand): Rally may resume
   - Spikes down: Supply resuming

3. **Price Action**
   - Holds support: Consolidation
   - Breaks higher: Reversal confirmed
   - Continues lower: Supply not yet exhausted

4. **Close Position**
   - Strong closes: Buyers entering
   - Weak closes: Sellers still present
   - Neutral closes: Equilibrium holding

---

## Real-Market Examples (Conceptual)

### Example 1: Supply Drying in Downtrend
```
Bar: Down bar after large selloff
Price: Lower close
Volume: 30 percentile (very low)
Spread: Narrow (10)
Result: SUPPLY_DRYING_UP detected
Follow-up: Demand enters next 2 bars
Outcome: Reversal to upside
```

### Example 2: Consolidation Phase
```
Bar: Down bar in sideways range
Price: Stable close
Volume: 25 percentile (minimal)
Spread: Very narrow (8)
Result: SUPPLY_DRYING_UP detected
Follow-up: 3-bar consolidation, then down break
Outcome: Supply resumes after quiet period
```

### Example 3: Support Holding
```
Bar: Down bar at support
Price: Hold support level
Volume: 20 percentile (exhausted)
Spread: Narrow
Result: SUPPLY_DRYING_UP detected
Follow-up: Demand enters with volume
Outcome: Breakout higher from support
```

---

## Production Status (Frozen - Audit Complete Aug 25)

**Detection:** ✅ ACTIVE (production-path collector runs every bar)

**Scoring Weight:**
- Registry: 1.00 (static metadata)
- Supply-map: 0.60 (professional configuration)
- Runtime: 1.00 (dynamic emission, static observed)

**Production Events:** 225 across 8 symbols

**Performance:**
- Positive rate: 61.78% (vs market 60.79%, +0.99 pp)
- Mean return: +3.56% (vs market +3.83%, -0.26 pp)
- Clean subset (159 events): 59.75% positive, +4.21% return
- With TEST (43 events): 69.77% positive (+10.02 pp), +2.55% return

**Qualification:** Integrated and active (contextual role)

**Production Role:** Contextual supply-exhaustion signal (no scoring promotion)

**Contextual Use:** YES (identifies supply exhaustion points, TEST interaction useful)

**Actionability:** YES (with supporting evidence - contextual only)

**Interaction Policy:**
- TEST: Improves hit rate (+10.02 pp) but reduces return (-1.66 pp), no penalty applied
- NO_SUPPLY: Reduces return materially (-3.76 pp), no penalty applied

**Status:** PRODUCTION-ACTIVE / AUDIT-COMPLETE (August 25, 2026)

---

## Implementation Notes

**Current Detector:** `evidence/demand.py::_collect_supply_drying_up()` (presumed, awaiting verification)

**Called In:** `EvidenceEngine.collect()` → `collect_demand()` (presumed)

**Semantics:** DRAFT (awaiting audit finalization)

---

## Expected Audit Path

### Short-term
- [ ] Candidate audit (validation in scanner)
- [ ] Semantic quality audit (definition validation)
- [ ] Interaction audit (conflict identification)

### Medium-term
- [ ] Decision-value audit (weight determination)
- [ ] Production-path audit (integration check)
- [ ] Weight sensitivity testing

### Timeline
- **Audit duration:** ~3-5 days
- **Weight determination:** Concurrent with audits
- **Status decision:** Upon audit completion

---

## Related Patterns

- **DEMAND_DRYING_UP** - Opposite (demand exhaustion)
- **SUPPLY_COMING_IN** - Opposite (supply entering)
- **SELLING_CLIMAX** - Opposite phase (supply intensity)
- **INCREASING_SUPPLY** - Opposite (supply escalation)
- **HIDDEN_DEMAND** - Often sequence after (buyers entering)

---

## Key Principle

Supply Drying Up = Sellers leaving, not yet buyers entering.

Represents market transition point.

Requires demand patterns to confirm bullish turn.

Early warning system for supply exhaustion.

---

**Status:** PRODUCTION-ACTIVE (August 25, 2026)  
**Audit Status:** ✅ COMPLETE (All 8 stages passed)  
**Confidence Level:** VERY HIGH (comprehensive audit, 225 events validated)  
**Production Ready:** YES (actively deployed)  
**Production Role:** Contextual supply-exhaustion signal  
**Weight:** Registry 1.00, Supply-map 0.60, Runtime 1.00  
**Key Finding:** 225 events, 61.78% positive (+0.99 pp vs market). Clean subset: 59.75%, +4.21% return. TEST interaction: 69.77% positive (+10.02 pp) but weaker return. No scoring promotion; remains contextual.  
**Status:** Frozen (no further changes)
