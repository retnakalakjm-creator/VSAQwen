# ProVSA Weekly Legacy Decision Baseline

**Milestone:** WF0 — Baseline Freeze and Safety Contract  
**Status:** IN PROGRESS  
**Baseline source:** `main` at `98cedd7bd1bf68ece3fb7a589394f7e1e371d798`  
**Purpose:** Freeze current weekly decision semantics before introducing read-only weekly behavior instrumentation.

---

## 1. Why This Baseline Exists

The Weekly Foundation roadmap will evaluate whether ProVSA's current weekly qualification/actionability boundary is too rigid for real-market behavior. Before any shadow instrumentation is added, the existing production semantics need a reproducible reference.

This document describes the **legacy behavior to preserve for comparison**. It is not an endorsement that every frozen rule should remain in the final weekly architecture.

Invariant:

```text
same weekly history
→ same legacy qualification/actionability output
before and after shadow-only weekly remediation work
```

WF0 must not change production qualification, scoring, ranking, actionability, alerts, orders, or `WeeklySetup` creation semantics.

---

## 2. Frozen Structural Qualification Contract

The current `PatternQualificationEngine` uses only structural progression events for persistent qualification:

```text
bullish: STRUCTURAL_PROGRESSION_IMPROVING
bearish: STRUCTURAL_PROGRESSION_WEAKENING
```

The current thresholds are:

```text
MIN_QUALIFYING_EVENTS = 3
MIN_EVENT_SPACING_BARS = 4
```

A later opposing structural progression event resets the active directional campaign. Events before that opposing boundary cannot qualify the current campaign again.

The current spacing-selection behavior is also legacy behavior. Existing tests already preserve the backward-selection quirk where events at bars `(1, 3, 5, 9)` can qualify as `(3, 5, 9)`.

WF0 does not correct or reinterpret that behavior; later weekly remediation must compare against it explicitly.

---

## 3. Frozen Scanner Freshness Contract

The current weekly scanner uses:

```text
SCORING_LOOKBACK_BARS = 10
MAX_ACTIONABLE_VSA_AGE = 3
```

A structurally qualified campaign therefore still depends on sufficiently recent directional VSA confirmation under the existing scanner rules.

These constants are frozen as comparison semantics for WF1–WF6. Changing them is outside WF0.

---

## 4. Frozen Named Directional VSA Contract

Current bullish named VSA confirmation codes:

```text
STOPPING_VOLUME
DEMAND_COMING_IN
INCREASING_DEMAND
HIDDEN_DEMAND
DEMAND_DRYING_UP
NO_SUPPLY
SPRING
TEST
SELLING_CLIMAX
SHAKEOUT
```

Current bearish named VSA confirmation codes:

```text
BUYING_CLIMAX
SUPPLY_COMING_IN
INCREASING_SUPPLY
HIDDEN_SUPPLY
SUPPLY_HIGH_VOLUME
SUPPLY_WIDE_SPREAD
SUPPLY_ABSORPTION
UPTHRUST
NO_DEMAND
```

For a persistent bullish qualification, the current legacy confirmation helper requires bullish named VSA evidence and no bearish named VSA evidence. The bearish path is symmetric.

This is one of the decision boundaries the Weekly Foundation roadmap intends to audit. WF0 only freezes it.

---

## 5. Frozen Read-Only Evidence Boundary

The following production-visible evidence remains excluded from the legacy named-VSA confirmation set:

```text
EFFORT_GT_RESULT
RESULT_GT_EFFORT
ABSORPTION
```

High Volume Reversal also remains governed by its existing read-only scanner boundary.

These observations may be visible for review/audit, but WF0 does not promote them into weekly scoring, ranking, qualification, or actionability.

The later Weekly Foundation audit will measure whether any of them add incremental decision value.

---

## 6. Frozen WeeklySetup Coupling

The current `WeeklySetup` model remains coupled to legacy persistent qualification:

```text
BULLISH WeeklySetup
→ PERSISTENT_BULLISH

BEARISH WeeklySetup
→ PERSISTENT_BEARISH
```

A direction/qualification mismatch is rejected by the domain model.

WF0 does not generalize this model. That decision belongs to WF8 and only if shadow/replay evidence shows that broader thesis semantics are needed.

---

## 7. What the WF0 Contract Test Pins

`tests/test_weekly_legacy_decision_baseline.py` freezes:

1. Three-event structural qualification threshold.
2. Four-bar minimum event spacing.
3. Opposing structural progression resets the active campaign.
4. Ten-bar scanner scoring lookback.
5. Three-bar maximum actionable VSA age.
6. Exact current bullish named-VSA confirmation set.
7. Exact current bearish named-VSA confirmation set.
8. Effort/Result and Absorption remain outside named-VSA confirmation.
9. Bullish persistent qualification requires aligned named VSA without named bearish opposition.
10. Bearish persistent qualification requires aligned named VSA without named bullish opposition.
11. `WeeklySetup` remains directionally coupled to persistent legacy qualification.

These assertions intentionally make later weekly semantic changes explicit. When WF7 eventually promotes validated behavior, the baseline tests should be retained as legacy comparison tests or deliberately superseded with documented evidence—not silently edited to make a refactor pass.

---

## 8. Safety Boundary

WF0 introduces no new market interpretation.

```text
No new detector
No new behavior score
No new thesis state
No new actionability
No ranking change
No production scanner change
No WeeklySetup change
No daily-entry change
```

The existing full-vs-resume equivalence contract remains authoritative.

---

## 9. Manual Validation

Targeted validation:

```powershell
python -m pytest tests/test_weekly_legacy_decision_baseline.py tests/test_qualification_state.py tests/test_scanner_full_resume_equivalence.py tests/test_production_scanner.py -v
```

Full backend validation:

```powershell
python -m pytest tests -q
```

WF0 is complete only after the new baseline contract and the full backend suite pass without production-semantic changes.

---

## 10. Next Step After WF0

After WF0 is merged and manually validated, proceed to:

```text
WF1 — Weekly Decision-Gate Audit
```

WF1 will add read-only diagnostics that explain where legacy weekly qualification/actionability delays or discards otherwise coherent real-market evidence. It must compare against this frozen baseline rather than changing it.
