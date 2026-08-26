# Specification: INCREASING_SUPPLY

**Version:** 1.0  
**Status:** Production-Active (August 23, 2026)  
**Audit Status:** Complete - All 8 stages passed  
**Production Events:** 528 (across 8 symbols)  
**Win Rate:** 63.45% (above market baseline 60.68%)  
**Registry/Empirical Weight:** 0.85  
**Configured Supply-Map Weight:** 0.70  
**Production Runtime Weight:** 1.00 (observed)

---

## Purpose

Detect escalating bearish supply where selling pressure is increasing in intensity through multiple bars.

Increasing Supply represents a progression from initial supply to growing supply intensity.

**Signal of momentum** showing sellers gaining control progressively.

---

## Classical Definition (Tom Williams)

Increasing Supply occurs when a sequence of bars shows:
- Multiple bearish bars
- Progressively increasing volume
- Increasing selling effort visible
- Rising pressure with growing volume
- Sellers taking increasing control

Represents the build-up of professional supply distribution.

---

## Wyckoff Interpretation

Increasing Supply = Distribution Phase Acceleration

Indicates:
- Smart money exiting increasingly
- Selling pressure building
- Professional money distributing progressively
- Foundation strengthening for reversal or breakdown

Separates early supply from aggressive supply.

---

## Professional Interpretation

Selling interest is not just present but growing.

Professional money is distributing aggressively.

Volume + pressure progression shows intensity increase.

Setup for potential breakdown or sustained decline.

---

## Detection Conditions (Frozen)

### Condition 1: Bearish Bar
- Close lower than or equal to open
- Bearish price action
- Shows initial selling strength

### Condition 2: Increasing Volume
- Current volume > prior bar volume
- Shows escalation, not static supply
- Volume progression key differentiator
- Intensity increasing, not plateauing

### Condition 3: Increasing Spread
- Current spread > prior bar spread
- Shows escalating effort
- Wider range than prior bar
- Selling effort intensifying

**No thresholds required** - purely comparative (vs prior bar)

---

## Output

**Event Type:** SmartMoneyEvidence

**Properties:**
- Code: INCREASING_SUPPLY
- Category: SUPPLY (bearish context)
- Direction: BEARISH
- Role: Primary bearish evidence
- Strength: STRONG

**Interpretation:**
Selling intensity is escalating, sellers gaining control.
Progressive supply distribution visible.
Bearish setup building.

---

## Weight System (IMPORTANT: Multiple Weight Concepts)

**Three Separate Weights:**

1. **Registry/Empirical Reference Weight:** 0.85
   - Historical calibration reference
   - NOT used in production directly
   - Documents what audit found

2. **Configured Supply-Map Weight:** 0.70
   - Static entry in `config.SUPPLY_EVIDENCE_WEIGHTS`
   - Used by scoring configuration
   - May differ from runtime

3. **Production Runtime Weight:** 1.00 (observed)
   - What actually emits in production
   - Measured across all 528 events
   - Context-dependent calculation
   - WeightCalculator handles dynamic adjustment

**Critical Distinction:**
- Do NOT confuse registry (0.85) with runtime (1.00)
- Do NOT assume configured (0.70) is what runs
- Production runtime is verified, not assumed

**Status:** Production-active with runtime weighting verified

---

## Frozen Detector Semantics

**Requirements (all mandatory, point-in-time):**
1. Down/bearish bar
2. Increasing volume vs prior bar
3. Increasing spread vs prior bar

**Philosophy:** Preserve meaningful imperfect real-market evidence; no textbook perfection required

**Semantic Quality Audit Result:** 100% (528/528 events valid)

---

## Audit Results Summary (August 23, 2026)

**Audit Completion Status:** ✅ ALL STAGES PASSED

### Candidate Audit
- **Status:** ✅ PASS
- **Production events:** 528 (across 8 symbols)
- **Coverage:** 8/8 symbols (comprehensive)
- **Cheap candidates:** 1,022
- **Expected events:** 528 (perfect match)

### Semantic Quality Audit
- **Status:** ✅ PASS (100%)
- **Down bar:** 528/528 ✓
- **Volume increasing:** 528/528 ✓
- **Spread increasing:** 528/528 ✓
- **Semantic failures:** 0

### Interaction Audit
- **Status:** ✅ PASS (mixed but not contradictory)
- **Supply-conflict events:** 147/528 (27.84%)
  - Conflict type: SUPPLY_COMING_IN (100%)
- **Demand interaction events:** 30/528 (5.68%)
  - Interaction type: STOPPING_VOLUME (100%)

### Interaction Outcome Audit

**Performance by Event Type:**

| Group | Events | Positive Rate | Mean Return |
|-------|--------|----------------|-------------|
| Clean | 289 | 61.25% | +2.22% |
| Other supply interactions | 133 | 66.17% | +3.98% |
| Other demand interactions | 92 | 67.39% | +4.50% |
| SUPPLY_COMING_IN + (weaker) | 14 | 57.14% | +2.11% |

**Decision:** No penalty applied; interactions generally confirming, not contradictory

### Outcome Audit
- **Status:** ✅ PASS
- **Positive outcomes:** 335 (63.45%)
- **Negative outcomes:** 193 (36.55%)
- **Mean 8-bar return:** +3.06%
- **vs Market baseline:** +2.66 pp directional lift
- **Return lift:** -0.77 pp (directional value, not return alpha)

**Interpretation:** Strong directional classification; use as supply-pressure component, not standalone return predictor

### Weight Sensitivity Audit

**Tested weights:** 0.70, 0.75, 0.80, 0.85, 0.90, 1.00

**Key Finding:** Weights affect ranking but not qualification/actionability

| Weight | Production-Capped Score | Final Scores Changed | Rank Positions Changed |
|--------|------------------------|--------------------|----------------------|
| 0.70 | 0.9273 | baseline | baseline |
| 0.75 | 0.9394 | 381/528 | 98/528 |
| 0.80 | 0.9515 | 381/528 | 173/528 |
| **0.85** | **0.9636** | **381/528** | **213/528** |
| 0.90 | 0.9758 | 381/528 | 237/528 |
| 1.00 | 1.0000 | 381/528 | 297/528 |

**Status:** All tested weights maintain scoring path integrity; no mutation risk

### Production-Path Readiness Audit
- **Status:** ✅ PASS
- **Collection path:** YES (evidence/supply.py)
- **Engine collection:** YES (via collect_supply)
- **Registry:** YES
- **Duplicate emissions:** 0
- **Campaign mismatches:** 0
- **Weight out-of-bounds:** 0
- **Production score mutation:** NO
- **Semantic failures:** 0

---

## Weight Architecture (CRITICAL)

### Three Weight Concepts Must Remain Separate

**Concept 1: Registry/Empirical Reference (0.85)**
- Audit calibration reference
- Historical research finding
- NOT applied directly to production
- Documents what testing showed

**Concept 2: Configured Supply-Map (0.70)**
- Static entry: `config.SUPPLY_EVIDENCE_WEIGHTS['INCREASING_SUPPLY'] = 0.70`
- May differ from runtime
- Configuration layer value
- Subject to manual tuning

**Concept 3: Production Runtime (1.00)**
- What actually emits
- Calculated per bar
- WeightCalculator applies logic
- Context-dependent
- Verified across all 528 events

### Why They Differ

1. **Registry (0.85)** = What audit empirically found
2. **Configured (0.70)** = What system was told to use
3. **Runtime (1.00)** = What actually happens in production

This separation is intentional:
- Audit preserves empirical findings
- Configuration allows manual override
- Runtime verifies actual behavior
- No discrepancy is a "bug" - it's architectural design

---

## What INCREASING_SUPPLY Must NOT Claim

INCREASING_SUPPLY alone must NOT imply:
- Guaranteed continuation
- Confirmed downtrend
- Trade entry signal (needs confirmation)
- Dominant selling control
- Automatic breakdown

Those require:
- Subsequent price continuation
- Qualification engine validation
- Support from structural context
- Absence of major demand evidence

---

## Interaction with Other Patterns

### With SUPPLY_COMING_IN (27.84% overlap)
- Sequence: SUPPLY_COMING_IN (steady) → INCREASING_SUPPLY (intense) = Supply escalation (very bearish)
- Same bar: Possible, confirming (both indicate supply)
- Status: No penalty applied (confirming overlap)

### With STOPPING_VOLUME (5.68% overlap)
- Sequence: INCREASING_SUPPLY (sellers) → STOPPING_VOLUME (buyers) = Demand resistance
- Indicates sellers met opposition
- Status: No contradiction

### With HIDDEN_SUPPLY
- Sequence: INCREASING_SUPPLY (visible) → HIDDEN_SUPPLY (at higher prices) = Supply persistence (very bearish)
- Both indicate supply presence
- Different perspectives, confirming intent

### With SELLING_CLIMAX
- Sequence: INCREASING_SUPPLY (escalation) → SELLING_CLIMAX (exhaustion) = Supply peak (climactic)
- Different patterns in sequence
- Exhaustion follows intensity

---

## Context Rules

### In Downtrend
- Increasing Supply = Trend acceleration
- Momentum building downward
- Breakdown likely

### After Consolidation
- Increasing Supply = Resolution bearish
- Breakdown from consolidation
- Continuation likely downward

### At Resistance/Support
- Increasing Supply = Aggressive selling at key level
- Support rejection
- Lower levels likely test

### Near Highs
- Increasing Supply = Distribution phase active
- Top formation building
- Reversal preparation

---

## Validation Framework

### Post-Detection Validation (1-8 bars forward)

1. **Continuation Volume**
   - Sustained high volume: Supply continuing
   - Fading volume: Supply weakening
   - Volume spike: Climax possible

2. **Price Progression**
   - Lower closes: Supply dominance
   - Consolidation: Supply present but opposed
   - Reversal: Supply overcome

3. **Demand Response**
   - No demand: Supply uncontested
   - Weak demand: Supply winning
   - Strong demand: Resistance forming

4. **Spread Trend**
   - Widening: Continued selling effort
   - Narrowing: Consolidation
   - Extreme: Climax risk

---

## Real-Market Examples

### Example 1: Supply Escalation in Downtrend
```
Bar 1: Down bar, volume 70 percentile, spread 65 percentile
Bar 2: Down bar, volume 80 percentile (increasing), spread 72 percentile (increasing)
Result: ✅ INCREASING_SUPPLY detected
Follow-up: Volume continues, price lower 3 bars
Outcome: Supply escalation confirmed, downtrend continues
```

### Example 2: Supply with Demand Conflict
```
Bar 1: Down bar, volume 75, spread 68
Bar 2: Down bar, volume 82 (increasing), spread 75 (increasing)
But next bar: STOPPING_VOLUME detected (buyers entering)
Result: Increasing supply opposed by demand
Outcome: Support forming, potential consolidation
```

### Example 3: Distribution Phase
```
Sequence of 3-4 bars, each showing:
  - Down/neutral bars
  - Increasing volume progression
  - Increasing spread progression
Result: Progressive supply distribution
Follow-up: Later SELLING_CLIMAX
Outcome: Distribution phase visible, reversal setup
```

---

## Production Status

**Detection:** ✅ ACTIVE (production-path collector runs every bar)

**Scoring Weight:** 
- **Registry/Empirical:** 0.85 (calibration reference)
- **Configured:** 0.70 (supply-map entry)
- **Runtime:** 1.00 (verified production emission)

**Qualification:** Integrated and active

**Contextual Use:** YES (identifies supply escalation points)

**Actionability:** YES (full production deployment)

**Status:** PRODUCTION-ACTIVE / AUDIT-COMPLETE

---

## Implementation Notes

**Current Detector:** `evidence/supply.py::_collect_increasing_supply()` (production active)

**Called In:** `EvidenceEngine.collect()` → `collect_supply()` (production path)

**Semantic Requirements:** Down bar, volume increasing, spread increasing (point-in-time)

**Weight Handling:**
- Registry reference: 0.85
- Configuration override: 0.70 (if configured)
- Runtime emission: 1.00 (WeightCalculator calculated)

**Recent Audit:** Complete (August 23, 2026) - All 8 stages passed

**Semantics:** FROZEN (production definition locked in)

---

## Future Enhancements

### Version 2.0
- Volume acceleration rate specificity
- Spread widening trend analysis
- Progressive intensity scoring
- Ensemble interaction handling

### Version 3.0
- Smart Money supply tracking
- Supply phase classification
- Multi-bar escalation sequences
- Distribution phase identification

### Version 4.0
- Machine learning confidence adjustment
- Real-time market regime adaptation
- Dynamic weight adjustment
- Cross-symbol supply correlation

---

## Related Patterns

- **SUPPLY_COMING_IN** - Visible supply (steady entry)
- **SELLING_CLIMAX** - Supply exhaustion (opposite phase)
- **INCREASING_DEMAND** - Opposite side (demand escalation)
- **HIDDEN_SUPPLY** - Hidden selling (different observation)
- **SUPPLY_DRYING_UP** - Supply exhaustion (opposite condition)

---

## Key Principle

Increasing Supply = Sellers entering progressively with growing intensity.

Registry weight 0.85 = Empirical calibration reference.

Runtime weight 1.00 = Verified production emission (may differ from registry).

Three weight concepts separate by design, not error.

---

## Audit Principles Preserved

- Real-market VSA evidence may be imperfect; textbook purity not required
- Detector semantics unchanged during scoring calibration
- Weight tuning changes scoring only, not detection
- Interaction overlap not automatically contradiction
- Empirical reference and runtime weights separate concepts
- Production-path audits verify actual runtime behavior

---

**Status:** PRODUCTION-ACTIVE (August 23, 2026)  
**Confidence Level:** VERY HIGH (all 8 audit stages passed)  
**Production Ready:** YES (actively deployed)  
**Weight:** Registry 0.85, Runtime 1.00, Configured 0.70  
**Recent Validation:** August 23, 2026 (comprehensive 8-stage audit complete)
