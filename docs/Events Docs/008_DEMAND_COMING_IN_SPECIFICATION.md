# Specification: DEMAND_COMING_IN

**Version:** 1.0  
**Status:** Audit-Only (August 20, 2026)  
**Audit Events:** 281 (multi-symbol validation complete)  
**Win Rate:** 66.19% (above market baseline 60.68%)  
**Decision-Value Lift:** +5.52 percentage points  
**Weight:** 0.38 (provisional, not promoted to production)

---

## Purpose

Detect market demand entering at higher price levels during upward price action.

Demand Coming In represents buyers actively entering the market at resistance levels or during rallies.

**Observation of demand activity** without automatic reversal confirmation.

---

## Classical Definition (Tom Williams)

Demand Coming In occurs when:
- Price rising or stable at elevated levels
- Increased volume on up bars
- Buyers absorbing selling pressure
- Spread widening
- Professional entry visible

NOT climactic buying, but active steady accumulation.

---

## Wyckoff Interpretation

Demand Coming In = Accumulation Phase Active Buying

Indicates:
- Smart money entering at higher levels
- Professional buying on strength
- Absorption of supply
- Preparation for markup phase

Part of accumulation phase characterized by professional entry.

---

## Professional Interpretation

Buyers entering the market at higher prices.

Professional money committing to accumulation.

Demand presence despite higher prices.

Support for continuation or breakout.

---

## Detection Conditions

### Condition 1: Up Bar or Strength Context
- Close higher or equal to open
- Bullish price action
- Shows initial demand

### Condition 2: Above-Average or Increasing Volume
- Volume Percentile >= DEMAND_COMING_IN_MIN_VOLUME_PERCENTILE
- Shows professional scale
- Indicates active participation, not quiet buying

### Condition 3: Above-Average Spread
- Spread Percentile >= DEMAND_COMING_IN_MIN_SPREAD_PERCENTILE
- Shows effort in buying
- Indicates competition/resistance

### Condition 4: Non-Climactic
- NOT extreme volume (volume < climax threshold)
- NOT panic buying (volume controlled)
- NOT buying climax signal (different pattern)
- Steady buying, not exhaustion

### Confirmation Factors (Not Mandatory)
- Higher close
- Volume sustained from prior bar
- Narrow close (buyers in control)
- Increasing volume trend

---

## Output

**Event Type:** SmartMoneyEvidence

**Properties:**
- Code: DEMAND_COMING_IN
- Category: DEMAND (bullish context)
- Direction: BULLISH
- Role: Supporting demand evidence
- Strength: MODERATE

**Interpretation:**
Demand entering at higher levels, buyers committing.
Active accumulation at resistance levels.
Support for uptrend or breakout.

---

## Confidence Calculation

Composite of:
- Volume Percentile (45% weight) - shows participation scale
- Spread Percentile (35% weight) - indicates effort against resistance
- Price level (20% weight) - shows buyers' conviction at higher levels

Higher volume + wider spread + higher price level = higher confidence in demand entry

---

## Weight

**Provisional Weight:** 0.38

**Status:** Audit-only (NOT promoted to production weight)

**Rationale for Non-Promotion:**
- Temporal instability (Window 1 = -7.97 pp)
- Inconsistent performance across market conditions
- Modest decision-value lift (+5.52 pp)
- Symbol-specific validation pending

---

## Audit Finding: Temporal Instability

### Temporal Window Analysis (4 quarters of audit period)

| Window | Win Rate | Performance | Notes |
|--------|----------|-------------|-------|
| Window 1 | -7.97 pp | NEGATIVE | Below baseline, concerning |
| Window 2 | +7.07 pp | POSITIVE | Above baseline, improvement |
| Window 3 | +11.20 pp | STRONG | Significantly above baseline |
| Window 4 | +20.12 pp | VERY STRONG | Latest data shows strong performance |

### Key Observation

**Temporal instability is primary concern preventing promotion:**
- Window 1 negative signals (was pattern not working?)
- Improving trend in recent windows (+20.12 pp latest)
- Suggests environment-dependent performance
- May require market-regime gating

**Positive Signal:**
- Recent performance (Window 4) very strong
- Trend is improving, not degrading
- Suggests future promotion likely if current conditions persist

---

## Why Audit-Only Status?

**Criteria for Production Promotion:**
- ✗ Consistent temporal performance (Window 1 fails this test)
- ✗ Validated across all symbols (pending leave-one-out audit)
- ✓ Positive decision-value (+5.52 pp achieved)
- ✓ Above market baseline (66.19% vs 60.68%)
- ✓ Reasonable semantic quality (85.41%)

**Decision Logic:**
```
Pattern shows promise (+5.52 pp lift)
BUT temporal window 1 is negative (-7.97 pp)
Cannot promote pattern with negative performance window
Better to keep audit-only until all windows consistently positive
Recent improvement suggests future promotion likely
```

---

## False Positives to Avoid

### DO NOT Detect:

1. **Up Bar + Climactic Volume**
   - This is BUYING_CLIMAX, not demand coming in
   - Climax = exhaustion; coming in = steady entry
   - Different patterns with different implications

2. **Up Bar + Average Volume**
   - Insufficient volume for professional participation
   - Likely retail or normal buying, not smart money
   - Not significant enough to call "demand coming in"

3. **Up Bar + High Volume + Narrow Spread**
   - Volume present but no effort shown (spread)
   - Likely absorption, not demand entry
   - Professional demand would show spread (competition)

4. **In Strong Uptrend + Very Low Volume**
   - Low volume doesn't show "demand coming in"
   - May be continuation but not "coming in"
   - Requires volume showing active participation

---

## Detection Semantics

**Core Rule:** Professional buyers entering at higher prices during upward action.

This is observed as:
- Up bar (direction)
- Above-average volume (scale of participation)
- Above-average spread (effort against resistance)
- Non-climactic (controlled entry, not panic)

**Real-market constraint:**
- Do NOT require textbook-perfect progression
- Steady entry without extremes is the signal
- Volume and spread confirmation matters
- Climax patterns are different (excluding condition)

---

## What DEMAND_COMING_IN Must NOT Claim

DEMAND_COMING_IN alone must NOT imply:
- Automatic continuation
- Confirmed uptrend
- Trade entry signal (requires confirmation)
- Support for sustained rally
- Buyers in control

Those require:
- Subsequent price progression
- Volume maintenance
- Structural support
- Qualification validation
- Multiple supporting patterns

---

## Interaction with Other Patterns

### With HIDDEN_SUPPLY
- Sequence: DEMAND_COMING_IN (buyers entering) → HIDDEN_SUPPLY (sellers entering) = Conflict setup
- Same bar: Possible (both up bar, high volume combinations)

### With INCREASING_DEMAND
- Sequence: DEMAND_COMING_IN → INCREASING_DEMAND = Demand escalation (very bullish)
- Same bar: Possible (both show demand but different characteristics)

### With BUYING_CLIMAX
- Sequence: DEMAND_COMING_IN (steady) → BUYING_CLIMAX (intense) = Demand peak (setup for reversal)
- Same bar: Contradictory (coming in = controlled; climax = exhaustion)

### With SUPPLY_COMING_IN
- Sequence: DEMAND_COMING_IN (buyers) → SUPPLY_COMING_IN (sellers) = Resistance forming
- Indicates buyers met significant opposition

---

## Context Rules

### In Uptrend
- Demand Coming In = Trend continuation support
- Buyers defending uptrend
- Breakout setup likely

### At Resistance Levels
- Demand Coming In = Aggressive resistance test
- Buyers attacking resistance
- Breakout probability elevated

### After Consolidation
- Demand Coming In = Resolution bullish
- Breakout from consolidation
- Continuation likely

### In Early Uptrend
- Demand Coming In = Trend foundation
- Initial accumulation
- Breakout to higher levels likely

---

## Temporal Window Interpretation

### Window 1 Performance: -7.97 pp

**What This Means:**
- Pattern showed negative performance in first quarter
- Win rate below market baseline
- Suggests pattern wasn't working in that market environment
- Possible causes: Bear market, specific market regime, data anomaly

**Why It Matters:**
- Promotion requires CONSISTENT performance
- Single negative window justifies holding audit-only
- Can't recommend weight when historical period was negative

### Windows 2-4 Performance: Strong Improvement

**What This Means:**
- After poor Window 1, pattern improved significantly
- Window 4 shows +20.12 pp (VERY strong)
- Recent conditions favor this pattern
- Trend is positive, not negative

**Implication:**
- If current market conditions persist → promotion likely soon
- If negative conditions return → pattern may revert
- Requires market-regime classification for robust application

---

## Validation Framework

### Post-Detection Validation (1-8 bars forward)

1. **Volume Continuation**
   - Sustained high volume: Demand continuing
   - Fading volume: Demand weakening
   - Volume spike: Potential climax (watch)

2. **Price Progression**
   - Higher closes: Demand dominance
   - Consolidation: Demand present but opposed
   - Breakdown: Demand overcome

3. **Supply Response**
   - No supply: Demand uncontested
   - Hidden supply: Resistance building
   - Supply coming in: Trend resistance

4. **Spread Trend**
   - Widening: Continued competition
   - Narrowing: Consolidation (normal)
   - Extreme: Climax risk (watch)

---

## Real-Market Examples

### Example 1: Demand Coming In During Rally
```
Context: Strong uptrend established
Bar: Up bar at new high
Volume: 70 percentile (above average)
Spread: 65 percentile (wide)
Close: Strong (0.75)
Non-climactic: YES (not extreme)
Result: ✅ DEMAND_COMING_IN detected
Follow-up: Volume continues, price holds higher
Outcome: Demand supports continued rally
```

### Example 2: Failed Demand Coming In
```
Context: Uptrend at resistance
Bar: Up bar at resistance level
Volume: 72 percentile (above average)
Spread: 70 percentile (wide)
Non-climactic: YES
Result: ✅ DEMAND_COMING_IN detected
But: Supply comes in heavily next bar
Outcome: Resistance held, buyers failed
Lesson: Demand present but insufficient to break resistance
```

### Example 3: Temporal Window Effect
```
Historical: Window 1 (early period) = Negative
Detection: DEMAND_COMING_IN in Window 1 = Below baseline
Same Pattern: DEMAND_COMING_IN in Window 4 (recent) = +20.12 pp
Conclusion: Pattern works in current market, didn't in past
```

---

## Audit Results Summary (Complete)

**Audit Scope:**
- 281 events across 8 symbols
- Temporal window analysis (4 quarters)
- Semantic quality assessment (85.41%)
- Multi-symbol consistency check

**Key Findings:**
- Pattern correctly identifies demand entering at higher levels
- Semantic quality high for detected events
- Temporal instability primary concern (Window 1 negative)
- Recent windows very strong (+20.12 pp Window 4)
- Decision-value lift solid (+5.52 pp overall)

**Status:** Audit-only CONFIRMED, promotion pending temporal validation

---

## Promotion Requirements

**To Promote from Audit-Only to Production:**

1. **Leave-One-Symbol-Out Validation**
   - Test excluding each symbol sequentially
   - All symbols must show positive performance
   - Any symbol-specific failure = hold audit-only

2. **Temporal Window Stability**
   - All windows must show positive lift
   - OR recent windows must strongly outweigh early weakness
   - Market-regime gating may be required

3. **Qualification Gate Testing**
   - Integration with qualification engine
   - Upstream signal validation
   - Downstream continuation validation

4. **Production Path Confirmation**
   - Scanner integration validated
   - No regressions in existing signals
   - Clean collection in full pipeline

---

## Production Status

**Detection:** ACTIVE (production-path collector runs every bar)

**Scoring Weight:** NOT APPLIED (audit-only, not in production scoring)

**Qualification:** Not integrated (awaiting promotion)

**Contextual Use:** YES (diagnostic and research)

**Actionability:** NO (audit-only, requires validation)

---

## Implementation Notes

**Current Detector:** `evidence/demand.py::_collect_demand_coming_in()`

**Called In:** `EvidenceEngine.collect()` → `collect_demand()`

**Recent Audit:** Complete (281 events, temporal analysis done)

**Semantics:** FROZEN (await promotion or new evidence)

---

## Future Path to Production

### Short-term (Next 1-2 weeks)
- [ ] Leave-one-symbol-out validation (all 8 symbols)
- [ ] Temporal window analysis confirmation
- [ ] Qualification gate testing

### Medium-term (2-3 weeks)
- [ ] Production path validation
- [ ] No-regression testing
- [ ] Integration finalization

### Long-term (3-4 weeks)
- [ ] Weight determination (current: 0.38 provisional)
- [ ] Production promotion decision
- [ ] Documentation update

---

## Key Principle

Demand Coming In = Buyers entering at higher prices actively.

Base observation with solid audit data (+5.52 pp lift).

Temporal instability (Window 1 = -7.97 pp) prevents promotion.

Recent strong performance (Window 4 = +20.12 pp) suggests future promotion likely if sustained.

---

## Comparison: Audit-Only vs Production

| Aspect | Audit-Only (Current) | Production (Target) |
|--------|---------------------|-------------------|
| Status | Validated but held | Ready to deploy |
| Weight | 0.38 (not applied) | 0.38 (or adjusted) |
| Scoring | Zero contribution | Active scoring |
| Requirements | Diagnostic/research | Live trading |
| Promotion | Pending validation | All gates passed |

---

**Status:** FROZEN (August 20, 2026)  
**Confidence Level:** MODERATE-HIGH (audit complete, temporal concern)  
**Production Ready:** NOT YET (awaiting promotion validation)  
**Weight:** 0.38 (provisional, not yet applied)  
**Recent Validation:** August 20, 2026 (temporal analysis complete, improvement trend noted)
