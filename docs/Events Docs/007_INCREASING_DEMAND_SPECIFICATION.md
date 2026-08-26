# Specification: INCREASING_DEMAND

**Version:** 1.0  
**Status:** Provisional (August 20, 2026)  
**Audit Events:** 902 (comprehensive multi-symbol validation)  
**Win Rate:** ~60% (all events), 60% (clean), 51% (conflicted)  
**Base Weight:** 0.85  
**Conflict Penalty:** 0.10 (effective weight 0.765 for conflicted events)

---

## Purpose

Detect escalating bullish demand where buying pressure is increasing in intensity through multiple bars.

Increasing Demand represents a progression from initial demand to growing demand intensity.

**Signal of momentum** showing buyers gaining control progressively.

---

## Classical Definition (Tom Williams)

Increasing Demand occurs when a sequence of bars shows:
- Multiple bullish bars
- Progressively higher volume
- Increasing buying effort visible
- Rising prices with growing volume
- Buyers taking increasing control

Represents the build-up of professional demand accumulation.

---

## Wyckoff Interpretation

Increasing Demand = Accumulation Phase Acceleration

Indicates:
- Smart money entering increasingly
- Buying pressure building
- Professional money accumulating progressively
- Foundation strengthening for reversal or breakout

Separates early demand from aggressive demand.

---

## Professional Interpretation

Buying interest is not just present but growing.

Professional money is accumulating aggressively.

Volume + price progression shows intensity increase.

Setup for potential breakout or sustained rally.

---

## Detection Conditions

### Condition 1: Bullish Bar
- Close higher than or equal to open
- Bullish price action
- Shows initial buying strength

### Condition 2: High Volume
- Volume Percentile >= INCREASING_DEMAND_MIN_VOLUME_PERCENTILE
- Must be above average, indicating professional scale
- Volume spike suggests demand intensity

### Condition 3: Above-Average Spread
- Spread Percentile >= INCREASING_DEMAND_MIN_SPREAD_PERCENTILE
- Shows effort in buying
- Wide spread = professional competition

### Condition 4: Increasing Volume Progression
- Current volume > prior bar volume
- Shows escalation, not just static demand
- Intensity increasing, not plateauing

### Confirmation Factors (Not Mandatory)
- Higher close than prior bar
- Wider spread than prior bar
- Momentum bars in sequence (multiple bullish)
- Close near highs (buying dominance)

---

## Output

**Event Type:** SmartMoneyEvidence

**Properties:**
- Code: INCREASING_DEMAND
- Category: DEMAND (bullish context)
- Direction: BULLISH
- Role: Primary bullish evidence
- Strength: STRONG

**Interpretation:**
Buying intensity is escalating, buyers gaining control.
Progressive demand accumulation visible.
Bullish setup building.

---

## Confidence Calculation

Composite of:
- Volume Percentile (40% weight) - proves professional scale
- Spread Percentile (30% weight) - indicates effort
- Volume progression (30% weight) - shows increasing intensity

Higher volume + wider spread + increasing volume progression = higher confidence

---

## Weight System

**Base Weight:** 0.85 (primary bullish evidence)

**Conflict Adjustment:**
- Clean events (no conflicts): Weight 0.85
- Conflicted events (4.55% of sample): Weight 0.85 × 0.90 = 0.765
- Conflict penalty: 0.10 (provisional, subject to validation)

**Effective Weight Range:** 0.765 - 0.85

---

## Conflict Analysis (Key Audit Finding)

### Conflict Rate: 4.55% (41 events out of 902)

**Conflict Composition:**
| Type | Count | Percentage | Meaning |
|------|-------|-----------|---------|
| HIDDEN_SUPPLY-LIKE | 41 | 100% | Supply hiding, price up on volume |
| BUYING_CLIMAX-LIKE | 16 | 39% | Buying pressure + climax volume |
| UPTHRUST-LIKE | 1 | 2.4% | Bullish trap move |

**Interpretation:**
- Conflicts are minimal (4.55%)
- Conflicts are manageable (not invalidating)
- Supply presence doesn't negate demand bullishness
- Conflicted events still positive (51% win rate vs 59% clean)

### Performance Gap: Conflict vs Clean

**8-Bar Forward Return:**
- Clean events (858): +3.83% mean return
- Conflicted events (41): +0.72% mean return
- Gap: -3.11 pp (weaker performance)

**Win Rate (POSITIVE_8_BAR):**
- Clean events: 59.44%
- Conflicted events: 51.22%
- Gap: -8.22 pp (weaker outcomes)

**Implication:**
Conflicts reduce quality but don't invalidate; penalty justified to separate high-quality from average events.

---

## False Positives to Avoid

### DO NOT Detect:

1. **High Volume But Declining Volume**
   - Not increasing demand (volume plateau/decline)
   - May be climax or absorption
   - Intensity not escalating

2. **Bullish Bar + High Volume But Narrow Spread**
   - Effort not shown (wide spread missing)
   - Likely absorption, not demand intensity
   - Professional accumulation would show spread

3. **Bullish Bar + High Volume + Weak Close**
   - Buyers' effort met resistance
   - Not true demand intensity (climax instead)
   - Spread wide but close weak = distribution risk

4. **Average Volume Despite Bullish Bar**
   - Insufficient volume for professional activity
   - Retail or normal buying, not smart money
   - Not significant enough to call "increasing demand"

---

## Detection Semantics

**Core Rule:** Professional buyers entering progressively with increasing intensity.

This is observed as:
- Bullish bar (direction)
- High volume (scale)
- Wide spread (effort)
- Increasing volume (progression)

**Real-market constraint:**
- Do NOT require textbook-perfect momentum sequence
- Multi-bar progression helpful but single bar valid
- Increasing volume is KEY differentiator
- Confirmation from other patterns adds value

---

## What INCREASING_DEMAND Must NOT Claim

INCREASING_DEMAND alone must NOT imply:
- Guaranteed continuation
- Confirmed uptrend
- Trade entry signal
- No supply opposition
- Automatic bullish breakout

Those require:
- Subsequent price continuation
- Qualification engine validation
- Support from structural context
- Absence of major supply evidence

---

## Interaction with Other Patterns

### With HIDDEN_SUPPLY
- Same bar: May occur (4.55% conflict rate) - quality reduced but not invalid
- Sequence: INCREASING_DEMAND (buyers) → HIDDEN_SUPPLY (sellers entering) = Conflict setup

### With BUYING_CLIMAX
- Sequence: Early INCREASING_DEMAND → BUYING_CLIMAX = Campaign escalation (bullish progression)
- Same bar: Possible but contradictory (increasing vs climax)

### With SUPPLY_COMING_IN
- Sequence: INCREASING_DEMAND (buyers) → SUPPLY_COMING_IN (sellers) = Trend resistance
- Indicates buyers met opposition

### With SPRING
- Sequence: SPRING (test) → INCREASING_DEMAND (follow-through) = Accumulation continuation
- Indicates spring reversal validated by demand

### With TEST
- Sequence: TEST (probe) → INCREASING_DEMAND (validation) = Test success
- Shows buyers entered after probe

---

## Context Rules

### In Uptrend
- Increasing Demand = Trend continuation
- Momentum building
- Breakout setup likely

### After Consolidation
- Increasing Demand = Resolution bullish
- Buyers breaking out
- Accumulation completing

### At Resistance Levels
- Increasing Demand = Breakout attempt
- Volume through resistance
- Success depends on supply response

### After Shakeout/Spring
- Increasing Demand = Reversal validation
- Buyers absorbing selling pressure
- Accumulation in progress

---

## Conflict Penalty Framework

### Why Penalties?

Conflicted events (HIDDEN_SUPPLY, BUYING_CLIMAX same-bar) show:
- Mixed signal (supply + demand)
- Reduced confidence (outcome weaker)
- Lower win rates (buyers met opposition)
- Quality degradation (not pure demand)

### Penalty Calculation

**Base Weight:** 0.85
**Conflict Penalty:** 0.10
**Effective Weight:** 0.85 × (1.0 - 0.10) = 0.765

**Applied When:** Conflict pattern detected same bar

**NOT Applied:** Clean events get full 0.85 weight

### Penalty Sensitivity (Tested)

| Penalty | Effective Weight | Rationale |
|---------|------------------|-----------|
| 0.00 | 0.85 | No adjustment (not validated) |
| 0.05 | 0.8075 | Slight quality reduction (not enough) |
| 0.10 | 0.765 | **OPTIMAL** (balances reduction with retention) |
| 0.15 | 0.7225 | Moderate reduction (too aggressive) |
| 0.20 | 0.68 | Heavy reduction (loses signal value) |

**Selection:** 0.10 penalty balances:
- Acknowledging conflict = lower confidence
- Preserving evidence = doesn't invalidate
- Practical scoring = slight weight reduction
- Outcome alignment = reflects 8.22 pp win-rate gap

---

## Validation Framework

### Post-Detection Validation (1-8 bars forward)

1. **Continuation Volume**
   - Volume persists: Demand continuing
   - Volume fades: Demand weakening
   - Volume spikes: Breakout attempt

2. **Price Progression**
   - Higher closes: Demand dominance
   - Consolidation: Demand presence confirmed
   - Breakdown: Demand overcome by supply

3. **Spread Trend**
   - Narrowing: Consolidation natural
   - Widening: Increased conflict (competition)
   - Extreme: Potential climax (watch)

4. **Close Position**
   - Strong closes: Buyers winning
   - Weak closes: Sellers entering
   - Neutral closes: Equilibrium

---

## Real-Market Examples

### Example 1: Pure Increasing Demand (No Conflict)
```
Bar: Bullish bar
Volume: 80 percentile (high)
Spread: 75 percentile (wide)
Prior volume: 60 percentile (increasing)
Conflicts: None detected
Result: ✅ INCREASING_DEMAND scored (weight 0.85)
Follow-up: Volume continues, price higher
Outcome: Demand confirmed, bullish continuation
```

### Example 2: Conflicted Increasing Demand (HIDDEN_SUPPLY)
```
Bar: Bullish bar
Volume: 85 percentile (high)
Spread: 80 percentile (wide)
Prior volume: 70 percentile (increasing)
Close: Weak (0.30) - HIDDEN_SUPPLY detected
Result: ⚠️ INCREASING_DEMAND scored (weight 0.765 with penalty)
Follow-up: Supply evident, buying opposed
Outcome: Demand present but weaker than clean events
```

### Example 3: Increasing Demand in Breakout
```
Bar: Bullish bar at resistance
Volume: 88 percentile (climactic)
Spread: 85 percentile (wide)
Prior volume: 75 percentile (increasing)
Conflicts: Minimal
Result: ✅ INCREASING_DEMAND scored (weight 0.85)
Follow-up: Breakout higher, volume persists
Outcome: Resistance broken on strong demand
```

---

## Audit Results Summary (Complete)

**Audit Scope:**
- 902 events across 8 symbols
- Leave-one-symbol-out validation
- Conflict analysis (4.55% rate)
- Performance benchmarking

**Key Findings:**
- Pattern correctly identifies increasing demand
- Semantic quality high (definition matches observations)
- Conflict management justified (penalty 0.10 optimal)
- Multi-symbol consistency (all symbols positive)
- Win rate validated (60% consistent)

**Status:** Provisional CONFIRMED, conflict penalty locked in

---

## Production Status

**Detection:** ACTIVE (production-path collector runs every bar)

**Scoring Weight:** 0.85 (base), 0.765 (conflicted with penalty)

**Qualification:** Contributes to demand context, supports qualification

**Contextual Use:** YES (identifies demand escalation points)

**Actionability:** Not standalone, integrated with other demand patterns

---

## Implementation Notes

**Current Detector:** `evidence/demand.py::_collect_increasing_demand()`

**Called In:** `EvidenceEngine.collect()` → `collect_demand()`

**Conflict Handling:** Integrated in professional scoring engine

**Penalty Application:** Applied at scoring time, not detection time

**Recent Audit:** Complete (902 events, penalties validated)

**Semantics:** FROZEN (weight + penalty locked in)

---

## Future Enhancements

### Version 2.0
- Volume acceleration rate specificity
- Multi-bar momentum detection
- Spread widening trend analysis
- Conflict interaction refinement

### Version 3.0
- Smart Money accumulation profiling
- Demand phase classification
- Progressive intensity scoring
- Ensemble conflict handling

### Version 4.0
- Machine learning confidence adjustment
- Real-time market regime adaptation
- Dynamic conflict penalty adjustment
- Cross-symbol demand correlation

---

## Key Principle

Increasing Demand = Buyers entering progressively with growing intensity.

Base Weight 0.85 = Primary bullish evidence.

Conflict Penalty 0.10 = Acknowledges mixed signals when supply also present.

Effective Range 0.765-0.85 = Adjusts for event quality.

---

## Comparison: Base vs Conflict

| Aspect | Clean (0.85) | Conflicted (0.765) |
|--------|-------------|-------------------|
| Events | 858 (95.45%) | 41 (4.55%) |
| Mean Return | +3.83% | +0.72% |
| Win Rate | 59.44% | 51.22% |
| Quality | High | Moderate |
| Evidence | Strong | Present but opposed |

---

**Status:** FROZEN (August 20, 2026)  
**Confidence Level:** VERY HIGH (902-event audit complete)  
**Production Ready:** YES (provisional status)  
**Weight:** 0.85 base, 0.765 with conflict penalty  
**Recent Validation:** August 20, 2026 (conflict penalty finalized)
