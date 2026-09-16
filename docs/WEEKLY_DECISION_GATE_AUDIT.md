# ProVSA Weekly Decision-Gate Audit

**Milestone:** WF1 — Weekly Decision-Gate Audit  
**Status:** READY FOR MANUAL VALIDATION  
**Baseline:** WF0 frozen legacy weekly semantics on `main` via PR #264  
**Scope:** Read-only instrumentation only; no production qualification/actionability changes.

---

## 1. Purpose

WF1 makes the existing weekly decision boundary observable before ProVSA introduces a broader weekly behavior model.

The audit does **not** decide whether the current gate is good or bad. It records what the legacy scanner actually saw and why a weekly candidate was or was not actionable.

Primary question:

```text
Where does the existing weekly gate delay or reject otherwise useful evidence,
and where is that conservatism actually protecting the system?
```

The WF0 contract remains the source of truth for the legacy behavior being measured.

---

## 2. Read-Only API

WF1 adds:

```python
WeeklyDecisionGateAuditor.audit(
    *,
    symbol: str,
    candidate: ScannerCandidate,
    support_zone: WeeklyPriceZone | None = None,
    resistance_zone: WeeklyPriceZone | None = None,
) -> WeeklyDecisionGateAuditRecord
```

The auditor consumes an already-produced `ScannerCandidate`. It does not run an alternate scanner, mutate qualification, create a `WeeklySetup`, change ranking, or create execution authority.

The legacy scanner therefore remains causal and authoritative; WF1 only exposes the decision boundary in a structured form.

---

## 3. Audit Record

`WeeklyDecisionGateAuditRecord` captures the point-in-time weekly state needed for later WF2–WF6 comparison work:

```text
symbol / week / bar index
trend direction / trend state
structural pattern
structural swing lineage
structural progression events
legacy qualification
legacy qualification reason
legacy candidate reason
legacy qualification actionable-evidence flag
legacy candidate actionable state
whether structural qualification is current
qualifying evidence
scoring evidence
scoring-evidence age
current-bar evidence
bounded recent evidence
campaign evidence
Effort/Result evidence
Absorption evidence
bullish named VSA evidence
bearish named VSA evidence
aligned named VSA present
opposing named VSA present
professional pressure conflict
professional strength / weakness
professional net strength / pressure
professional confidence
optional weekly support/resistance zones
explicit legacy gate blockers
```

The record intentionally keeps raw evidence/provenance instead of collapsing the audit into a new synthetic score.

---

## 4. Explicit Legacy Gate Blockers

WF1 exposes the following audit-only blocker taxonomy:

```text
QUALIFICATION_MISSING
STRUCTURAL_QUALIFICATION_STALE_NO_VSA
NAMED_VSA_CONFIRMATION_MISSING
NAMED_VSA_CONFIRMATION_STALE
OPPOSING_NAMED_VSA_PRESENT
PROFESSIONAL_PRESSURE_CONFLICT
PROFESSIONAL_CONFIDENCE_ZERO
SIGNAL_BAR_ANOMALY
```

These values describe existing legacy behavior. They are **not** new production rejection rules.

The auditor deliberately mirrors the scanner's current constants and named directional VSA sets. That coupling is intentional: WF1 must measure the frozen baseline rather than silently reinterpret it.

---

## 5. Causality and Bounded Evidence

WF1 preserves point-in-time semantics.

For bounded recent evidence:

```text
earliest = current_bar - ScannerEngine.SCORING_LOOKBACK_BARS
```

Only campaign evidence satisfying:

```text
earliest <= evidence.bar_index <= current_bar
```

is admitted to `recent_evidence`.

Evidence from a future bar is excluded even if a replay/audit caller accidentally supplies it in the candidate's campaign evidence.

The audit also records the legacy `scoring_evidence_age` and mirrors `MAX_ACTIONABLE_VSA_AGE` so later replay work can distinguish:

```text
missing confirmation
vs
present but stale confirmation
```

---

## 6. Read-Only Evidence Remains Read-Only

WF1 exposes existing production-visible:

```text
EFFORT_GT_RESULT
RESULT_GT_EFFORT
ABSORPTION
```

through the candidate's current read-only evidence properties.

WF1 does **not** promote them into:

```text
named VSA confirmation
qualification
professional scoring
ranking
actionability
alerts
orders
```

This is important because WF6 must measure incremental value before any promotion decision is made.

---

## 7. What the Tests Pin

`tests/test_weekly_decision_audit.py` currently verifies:

1. An actionable legacy bullish candidate is mirrored without mutation.
2. Symbol normalization and weekly structural zone passthrough remain deterministic.
3. Recent evidence is bounded and future evidence is excluded.
4. Effort/Result and Absorption are exposed without being promoted.
5. Opposing named VSA is reported as the legacy blocker.
6. Fresh named VSA can support legacy continuation after the structural event week.
7. Stale named VSA is distinguished from missing directional confirmation.
8. Unqualified state, zero confidence, and signal-bar anomaly remain observable.
9. Empty symbols are rejected.

The tests intentionally use legacy scanner semantics rather than proposed WF2 behavior semantics.

---

## 8. Production Safety Boundary

WF1 introduces no production behavior change.

```text
No detector change
No evidence weight change
No qualification change
No VSA confirmation change
No scanner scoring change
No ranking change
No actionability change
No WeeklySetup change
No Weekly→Daily coordinator change
No daily-entry change
No execution change
```

The new module is a read-only diagnostic seam for replay/audit work.

---

## 9. Manual Validation

Run from branch `feat/wf1-weekly-decision-audit`:

```powershell
git fetch origin
git checkout feat/wf1-weekly-decision-audit
git pull origin feat/wf1-weekly-decision-audit
python -m pytest tests/test_weekly_decision_audit.py tests/test_weekly_legacy_decision_baseline.py tests/test_scanner_full_resume_equivalence.py tests/test_production_scanner.py -v
python -m pytest tests -q
```

Do not mark WF1 complete from GitHub metadata alone. The milestone is ready to merge only after the targeted tests and full backend suite pass in the user's local environment.

---

## 10. Next Step After WF1

After WF1 is merged and manually validated, proceed to:

```text
WF2 — WeeklyBehaviorState Shadow Model
```

WF2 should consume existing causal evidence and describe market behavior without requiring a perfect textbook sequence and without assigning an arbitrary synthetic confidence score.
