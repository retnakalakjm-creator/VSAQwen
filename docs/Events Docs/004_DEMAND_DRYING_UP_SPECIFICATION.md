# Specification: DEMAND_DRYING_UP

**Version:** 1.0  
**Status:** Audit-Complete (August 20, 2026)  
**Audit Commits:** 3 (candidate, semantic quality, interaction audits)  
**Audit Events:** Multi-stage validation complete

---

## Purpose

Detect the weakening or exhaustion of buying demand as volume declines while price remains stable or rises.

Demand Drying Up represents the end of buying enthusiasm and potential setup for reversal or consolidation.

**Important observation** of demand exhaustion without aggressive supply pressure.

---

## Classical Definition (Tom Williams)

Demand Drying Up occurs when buying activity diminishes even as price holds or rises slightly.

Typical characteristics:
- Price stable or slightly higher
- Volume declining
- Narrow spreads
- Weak close or neutral close
- No follow-through demand energy

Professional accumulation ending, not yet sellers' turn.

---

## Wyckoff Interpretation

Demand Drying Up = End of Accumulation Phase

Indicates:
- Buying pressure exhausted
- Equilibrium approaching
- Preparation for distribution or reversal
- Transition point in market cycle

Separates strong accumulation from consolidation/distribution.

---

## Professional Interpretation

Buyers have completed accumulation or taking profits.

Demand energy is fading.

Waiting period before next directional move.

Reversal risk building, but not yet confirmed.

---

## Detection Conditions

### Condition 1: Rising or Stable Price
- Close higher or equal to previous close
- Uptrend context or consolidation
- No aggressive selling pressure

### Condition 2: Declining Volume
- Volume Percentile < DEMAND_DRYING_UP_MAX_VOLUME_PERCENTILE
- Volume decreasing from prior bars
- Shows buying interest fading
- NOT climactic volume

### Condition 3: Narrow Spread
- Spread Percentile < DEMAND_DRYING_UP_MAX_SPREAD_PERCENTILE
- Small intrabar range
- Indicates reduced conflict/effort
- Quiet market action

### Confirmation Factors (Not Mandatory)
- Close below open (slight weakness)
- Lower close than prior bar
- Very low volume (extremely quiet)
- Narrow range with small body

---

## Output

**Event Type:** SmartMoneyEvidence

**Properties:**
- Code: DEMAND_DRYING_UP
- Category: DEMAND (bullish context)
- Direction: BEARISH (exhaustion signal)
- Role: Supporting contextual observation
- Strength: MODERATE

**Interpretation:**
Buying demand fading, energy depleting.
Transition phase, waiting for next move.
Reversal setup building (not yet confirmed).

---

## Confidence Calculation

Composite of:
- Volume Percentile decline (40% weight) - shows fading demand
- Spread Percentile (30% weight) - indicates reduced effort
- Price stability (30% weight) - shows support holding without strength

Lower volume + narrower spread + stable price = higher confidence in demand exhaustion

---

## Weight

**Production Weight:** Provisional (Recently determined through audit)

**Status:** Production-active, audit-complete (August 20, 2026)

---

## Why This Matters

Demand Drying Up is:
- Early warning of demand exhaustion
- Not aggressive reversal signal (yet)
- Preparation for potential supply entry
- Context setting for downstream patterns

Observes fade without destruction, suggesting market topping gradually not violently.

---

## False Positives to Avoid

### DO NOT Detect:

1. **Stable Price + Very High Volume**
   - Likely absorption or hidden supply
   - High volume = active demand not drying up
   - This is opposite of demand drying

2. **Rising Price + Average Volume**
   - Insufficient decline to confirm drying
   - Demand may still be present
   - Not yet exhausted

3. **Rising Price + Wide Spread + Low Volume**
   - Contradictory (wide spread = effort, low volume = no effort)
   - Unlikely real-market combination
   - Skip detection

4. **Down Bar with Declining Volume**
   - Supply entering, not demand drying
   - Different pattern (supply confirmation)
   - Not demand drying up

---

## Detection Semantics

**Core Rule:** Buying demand is present but fading.

This is observed as:
- Price holding (buyers still here)
- Volume declining (fewer buyers)
- Narrow spread (less effort needed)

Not aggressive supply (no selling pressure).
Just fading demand (buyers leaving).

---

## What DEMAND_DRYING_UP Must NOT Claim

DEMAND_DRYING_UP alone must NOT imply:
- Confirmed reversal
- Supply dominance
- Trade entry signal
- Automatic weakness ahead
- End of uptrend

Those require:
- Subsequent supply entry patterns
- Qualification validation
- Supporting evidence
- Price structure context

---

## Interaction with Other Patterns

### With SUPPLY_COMING_IN
- Sequence: DEMAND_DRYING_UP → SUPPLY_COMING_IN = Bearish transition (high probability reversal)
- Same bar: Unlikely (opposite signals)

### With SUPPLY_DRYING_UP
- Same bar: Impossible (opposite signals)
- Sequence: DEMAND_DRYING_UP (buyers weak) → SUPPLY_DRYING_UP (sellers weak) = Equilibrium consolidation

### With HIDDEN_SUPPLY
- Sequence: DEMAND_DRYING_UP → HIDDEN_SUPPLY = Supply entering as demand exits (bearish)
- Same bar: Possible but less likely

### With BUYING_CLIMAX
- Sequence: BUYING_CLIMAX (intense) → DEMAND_DRYING_UP (fade) = Natural exhaustion progression
- Same bar: Contradictory (climax = high energy, drying = low energy)

---

## Context Rules

### In Strong Uptrend
- Demand Drying Up = Trend nearing conclusion
- Pullback likely
- Reversal risk building

### Near Major Resistance
- Demand Drying Up = Failed breakout attempt
- Supply should enter soon
- Test downward probable

### In Early Uptrend
- Demand Drying Up = Consolidation phase
- Buyers absorbing supply
- Continuation likely after quiet period

### After Large Volume Move
- Demand Drying Up = Normal profit-taking
- Buyers taking off table
- Continuation requires fresh demand

---

## Validation Framework

### Post-Detection Validation (1-8 bars forward)

1. **Supply Response**
   - Supply entering: Bearish confirmation
   - No supply: Demand may resume
   - Hidden supply: Distribution phase

2. **Volume Trend**
   - Stays low: Consolidation continues
   - Increases (demand): Rally may resume
   - Spikes down: Supply entering aggressively

3. **Price Action**
   - Holds support: Consolidation
   - Breaks lower: Reversal confirmed
   - Continues higher: Demand not yet exhausted

4. **Close Position**
   - Weak closes: Sellers entering
   - Strong closes: Demand resuming
   - Neutral closes: Equilibrium holding

---

## Real-Market Examples

### Example 1: Demand Drying in Uptrend
```
Bar: Up bar after strong rally
Price: Higher close
Volume: 30 percentile (very low)
Spread: Narrow (15)
Result: DEMAND_DRYING_UP detected
Follow-up: Supply enters next 2 bars
Outcome: Reversal to downside
```

### Example 2: Consolidation Phase
```
Bar: Up bar in sideways range
Price: Stable close
Volume: 25 percentile (minimal)
Spread: Very narrow (10)
Result: DEMAND_DRYING_UP detected
Follow-up: 3-bar consolidation, then up break
Outcome: Demand resumes after quiet period
```

### Example 3: Failed Breakout
```
Bar: Up bar at resistance
Price: Slightly above resistance
Volume: 20 percentile (exhausted)
Spread: Narrow
Result: DEMAND_DRYING_UP detected
Follow-up: Supply enters with high volume
Outcome: Rejection of resistance, pullback
```

---

## Audit Results Summary (August 20, 2026)

**Audit Scope:**
- Candidate audit: Verification in scanner output
- Semantic quality audit: Pattern definition validation
- Interaction audit: Conflict detection with other patterns

**Key Findings:**
- Pattern correctly identifies fading demand
- Semantic quality validated (definition matches observations)
- Interactions clean (no major conflicts)
- Contextual value confirmed

**Status:** Production-active CONFIRMED, frozen for this audit cycle

---

## Production Status

**Detection:** ACTIVE (production-path collector runs every bar)

**Scoring Weight:** Provisional (weight determined through audit)

**Qualification:** Standalone not required, contextual evidence

**Contextual Use:** YES (identifies demand exhaustion points)

**Actionability:** NOT standalone (requires supply confirmation)

---

## Implementation Notes

**Current Detector:** `evidence/demand.py::_collect_demand_drying_up()`

**Called In:** `EvidenceEngine.collect()` → `collect_demand()`

**Recent Audit:** August 20, 2026 (3 commits, audit-complete)

**Semantics:** FROZEN (no changes until new evidence)

---

## Future Enhancements

### Version 2.0
- Volume decline rate specificity
- Trend confirmation requirements
- Consolidation pattern matching
- Support level proximity detection

### Version 3.0
- Smart Money withdrawal detection
- Demand profile analysis
- Multi-bar weakening sequences
- Exhaustion probability scoring

---

## Related Patterns

- **SUPPLY_COMING_IN** - Opposite (supply entering)
- **SUPPLY_DRYING_UP** - Opposite side (supply fading)
- **BUYING_CLIMAX** - Intensity exhaustion (different observation)
- **SHAKEOUT** - Aggressive selling (different pattern)
- **TEST** - Probe after weakness (downstream pattern)

---

## Key Principle

Demand Drying Up = Buyers leaving, not yet sellers entering.

Represents market transition point.

Requires supply patterns to confirm bearish turn.

Early warning system for demand exhaustion.

---

**Status:** FROZEN (August 20, 2026)  
**Confidence Level:** HIGH (3-stage audit complete)  
**Production Ready:** YES  
**Recent Validation:** August 20, 2026 (3-commit audit cycle)
