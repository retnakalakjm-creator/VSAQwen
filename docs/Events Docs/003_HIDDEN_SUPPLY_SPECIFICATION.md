# Specification: HIDDEN_SUPPLY

**Version:** 1.0  
**Status:** Audit-Complete (August 20, 2026)  
**Audit Commits:** 6 (candidate, semantic quality, interaction, decision-value, conclusion)  
**Audit Events:** Comprehensive multi-stage validation  
**Audit Conclusion:** Pattern valid, semantics frozen

---

## Purpose

Detect supply that is not evident from price action alone but is revealed through volume analysis.

Hidden Supply occurs when sellers enter quietly at higher prices while price is rising, without showing obvious selling pressure signals.

**Important observation** for understanding true supply/demand dynamics beneath surface price action.

---

## Classical Definition (Tom Williams)

Hidden Supply represents professional selling that does not appear as aggressive downward pressure.

Typical characteristics:
- Price rising or stable
- Volume increasing
- Close near or below midpoint despite up bar
- Weak close (buyers' effort met resistance)
- No obvious pressure bars

Professional selling is not always obvious.

---

## Wyckoff Interpretation

Hidden Supply = Supply Entering During Demand Phase

Indicates:
- Smart money selling resistance
- Supply awaiting pullback
- Potential for aggressive drop when buyers fail
- Setup for testing lower levels

Represents conflict between buyers and hidden sellers.

---

## Professional Interpretation

Supply is present in market even though price rising.

Sellers entering on strength (professional move).

Buying interest exists but faces hidden opposition.

Price may hold temporarily but reversal risk elevated.

---

## Detection Conditions

### Condition 1: Up Bar or Neutral Bar
- Close higher than or equal to open
- Bullish price action on bar
- Suggests initial demand/strength

### Condition 2: High Volume
- Volume Percentile >= HIDDEN_SUPPLY_MIN_VOLUME_PERCENTILE
- Indicates professional-scale activity
- Not passive/quiet accumulation

### Condition 3: Weak Close Position
- Close Ratio < HIDDEN_SUPPLY_MAX_CLOSE_RATIO (weak close)
- Close in lower half of bar despite up bar
- Shows buyers' effort meeting resistance
- Sellers' defense preventing strong close

### Confirmation Factors (Not Mandatory)
- Low volume on close
- Open > Close (despite up bar)
- Close below previous close
- Lower close than opening (rejection)
- Wide spread showing conflict

---

## Output

**Event Type:** SmartMoneyEvidence

**Properties:**
- Code: HIDDEN_SUPPLY
- Category: SUPPLY (bearish context)
- Direction: BEARISH
- Role: Supporting supply evidence
- Strength: MODERATE to STRONG (depending on confirmation presence)

**Interpretation:**
Supply entering at higher prices while buyers remain active.
Creates imbalance favoring potential reversal on profit-taking.

---

## Confidence Calculation

Composite of:
- Volume Percentile (40% weight) - proves professional activity
- Close Ratio (40% weight) - indicates seller strength
- Spread Percentile (20% weight) - shows market conflict

Higher volume + weaker close + wide spread = higher confidence in hidden supply

---

## Weight

**Production Weight:** Provisional (Recently determined through audit)

**Status:** Production-active, audit-complete (August 20, 2026)

---

## Why "Hidden"?

Supply is hidden because:
1. Price rising = normally reads as bullish
2. Volume high = could be buying
3. But close weak = reveals seller defense
4. Sellers invisible on surface, visible through analysis

Classic smart money behavior - entering on strength without showing hand.

---

## False Positives to Avoid

### DO NOT Detect:

1. **Up Bar + High Volume + Strong Close**
   - Likely Buying Climax, not hidden supply
   - Close strength means buyers won
   - No supply opposition evident

2. **Up Bar + Average Volume + Weak Close**
   - Insufficient volume for professional supply
   - Likely normal profit-taking, not smart money
   - Not significant enough to call "hidden supply"

3. **Up Bar + High Volume + Average Spread**
   - Possible absorption, not hidden supply
   - Narrow spread = less conflict
   - Professional supply would show effort (spread)

4. **Down Bar with High Volume**
   - Obvious supply, not hidden
   - If sellers already showing hand, not "hidden"
   - This is SELLING_CLIMAX, not hidden supply

---

## Detection Semantics

**Core Rule:** Professional sellers are entering at higher prices while buyers push price up.

This is observed as:
- Volume spike (professional scale)
- Up bar (price moving higher)
- Weak close (sellers defend, buyers can't hold gains)

**Real-market constraint:**
- Do NOT require textbook-perfect weak close
- Weak relative to volume and open/high is sufficient
- Confirmation factors help but not mandatory
- Context of prior price action matters

---

## What HIDDEN_SUPPLY Must NOT Claim

HIDDEN_SUPPLY alone must NOT imply:
- Automatic downward reversal
- Confirmed top formation
- Selling pressure equivalent to visible climax
- Trade entry signal
- End of uptrend

Those require:
- Subsequent price action response
- Qualification engine validation
- Supporting evidence from other patterns
- Structural/campaign context

---

## Interaction with Other Patterns

### With BUYING_CLIMAX
- Same bar: May occur (climax with hidden supply = strong distribution risk)
- Sequence: BUYING_CLIMAX → HIDDEN_SUPPLY = Extended distribution (very bearish)

### With INCREASING_SUPPLY
- Same bar: Possible (both indicate supply, different evidence)
- Both active = very strong supply confluence

### With SUPPLY_COMING_IN
- Same bar: May occur (supply entering visibly and hidden simultaneously)
- Suggests aggressive supply entry

### With SUPPLY_DRYING_UP
- Same bar: Unlikely (supply drying contradicts hidden supply)
- If occurs: Supply present but waning = transition signal

### With TEST
- Sequence: TEST → HIDDEN_SUPPLY = Test rejection (bearish)
- Indicates buyers' failure met with supply

---

## Context Rules

### In Uptrend
- Hidden Supply = Trend resistance forming
- Distribution phase likely beginning
- Pullback risk elevated

### Near Resistance Levels
- Hidden Supply = Professional defense at key level
- Supply awaiting breakdown for aggressive selling
- Technical level breakout gets tested

### After Large Volume Rally
- Hidden Supply = Profit-taking on strength
- Normal market behavior
- Usually contains rally, doesn't reverse it

### In Early Uptrend
- Hidden Supply = Market testing resistance
- Buyers absorbing supply, likely to continue
- Not automatic reversal signal

---

## Validation Framework

### Post-Detection Validation (1-8 bars forward)

1. **Price Action Response**
   - Immediate reversal: Supply very strong
   - Consolidation: Supply slowing buyers
   - Continuation higher: Buyers overcome supply

2. **Volume Trend**
   - Declining next bars: Buyers in control
   - Sustained high: Supply ongoing
   - Volume spike down: Supply/profit-taking

3. **Weak Close Persistence**
   - Repeats on next bars: Consistent supply
   - Reverses to strength: Supply diminishing
   - Continues weak: Distribution phase

4. **Price Structure**
   - Lower low formed: Supply very aggressive
   - Higher low: Supply present but contained
   - Breakout: Buyers eventually overcome supply

---

## Real-Market Examples

### Example 1: Hidden Supply at Resistance
```
Bar: Up bar at resistance level
Volume: Very high (90 percentile)
Close: Weak (0.30), well below open
Result: HIDDEN_SUPPLY detected
Follow-up: Price consolidates, slowly rolls over
Outcome: Supply was real, sellers waiting
```

### Example 2: Hidden Supply in Uptrend
```
Bar: Up bar in strong uptrend
Volume: High (75 percentile)
Close: Weak (0.35)
Result: HIDDEN_SUPPLY detected
Follow-up: Price continues higher next 3 bars
Outcome: Buyers eventually overcome, supply absorbed
Lesson: Hidden supply doesn't always cause reversal
```

### Example 3: Hidden Supply + Climax
```
Bar: Up bar with exceptional volume
Volume: 98 percentile (climactic)
Close: Weak (0.25)
Result: HIDDEN_SUPPLY + BUYING_CLIMAX both detected
Follow-up: Immediate reversal next bar
Outcome: Double confirmation = powerful signal
```

---

## Audit Results Summary (August 20, 2026)

**Audit Scope:**
- Candidate audit: Verification in production scanner output
- Semantic quality audit: Pattern definition validation
- Interaction audit: Conflict detection with other patterns
- Decision-value audit: Net benefit calculation
- Conclusion: Pattern validated, semantics frozen

**Key Findings:**
- Pattern correctly identifies supply entering at higher prices
- Semantic quality high (definition matches real-market observations)
- Interactions manageable, no major conflicts
- Decision-value positive (benefits pattern scoring)

**Status:** Production-active CONFIRMED, frozen for this audit cycle

---

## Production Status

**Detection:** ACTIVE (production-path collector runs every bar)

**Scoring Weight:** Provisional (weight determined through audit, applied in scoring engine)

**Qualification:** Standalone not required, contributes to supply context

**Contextual Use:** YES (identifies hidden supply entering market)

**Actionability:** NOT standalone (requires confirmation from other supply patterns)

---

## Implementation Notes

**Current Detector:** `evidence/supply.py::_collect_hidden_supply()`

**Called In:** `EvidenceEngine.collect()` → `collect_supply()`

**Recent Audit:** August 20, 2026 (6 commits, audit-complete)

**Semantics:** FROZEN (no changes until new evidence emerges)

---

## Future Enhancements

### Version 2.0
- Close ratio threshold refinement
- Volume spike detection specificity
- Integration with trend context
- Supply accumulation profiling

### Version 3.0
- Smart Money supply tracking
- Hidden supply persistence detection
- Layered supply identification
- Multi-bar hidden supply sequences

### Version 4.0
- Machine learning confidence adjustment
- Real-time supply/demand imbalance scoring
- Hidden supply magnitude estimation
- Reversal probability weighting

---

## Related Patterns

- **SUPPLY_COMING_IN** - Visible supply (more obvious)
- **BUYING_CLIMAX** - Demand exhaustion (opposite side)
- **INCREASING_SUPPLY** - Supply ramping up (more aggressive)
- **UPTHRUST** - False breakout attempt (different pattern)
- **SUPPLY_DRYING_UP** - Supply exhaustion (opposite condition)

---

## Key Principle

Hidden Supply = Supply present but not obvious.

Requires analysis to detect.

Price rising + Volume high + Close weak = Sellers entering on strength.

Professional move to avoid tipping hand while entering substantial supply.

---

**Status:** FROZEN (August 20, 2026)  
**Confidence Level:** HIGH (multi-stage audit complete)  
**Production Ready:** YES  
**Recent Validation:** August 20, 2026 (6-commit audit cycle)
