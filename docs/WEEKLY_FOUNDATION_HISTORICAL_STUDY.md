# Weekly Foundation Historical Study — WF6R / Pre-WF7 Gate

**Status:** READY FOR MANUAL VALIDATION  
**Purpose:** execute the already-built WF1-WF6 shadow/audit stack on real historical weekly data before any WF7 production qualification change.

---

## Why this step exists

WF1 through WF6 created the instrumentation needed to answer the weekly-foundation questions, but those modules alone do not justify a production change.

WF7 is intentionally conditional. Before changing `PatternQualification`, the named-VSA confirmation gate, contradiction policy, or `WeeklySetup`, ProVSA needs a repeatable way to materialize the shadow framework on real multi-symbol historical data and export the results for review.

This runner is that execution gate.

```text
real completed weekly history
        ↓
legacy scanner replay
        ↓
WF1 decision-gate records
        ↓
WF2 behavior state
        ↓
WF3 evolution / contradiction
        ↓
WF4 shadow weekly thesis
        ↓
WF5 legacy-vs-shadow replay
        ↓
WF6 evidence-promotion cohorts
        ↓
CSV / JSON review artifacts
        ↓
manual evidence review
        ↓
WF7 only if justified
```

No production behavior is changed by this step.

---

## New runner

Module:

```text
audit.weekly_foundation_runner
```

Primary programmatic entry point:

```python
run_weekly_foundation_historical_study(...)
```

The default data path is the same completed-week historical path already used by ProVSA:

```text
download_data
→ daily_to_weekly
→ completed_weekly_only
→ MetricsEngine
→ HistoricalScannerRunner
```

For every replay bar the runner then:

1. obtains the causal scanner candidate for that exact completed weekly bar;
2. derives structural support/resistance zones only from swings confirmed by that bar;
3. creates the WF1 `WeeklyDecisionGateAuditRecord`;
4. freezes the matching weekly OHLC price bar;
5. builds WF5 legacy-vs-shadow replay output;
6. feeds the full symbol dataset into the WF6 evidence-promotion audit.

The scanner is requested through the suffix-reuse `scan_to_indices` path when available, so the study does not repeatedly restart a full replay for each historical week.

---

## Command-line usage

Example:

```powershell
python -m audit.weekly_foundation_runner `
  --symbols LT.NS,RELIANCE.NS,TCS.NS,INFY.NS `
  --horizons 5,10,15 `
  --out-of-sample-start-week 2025-01-01 `
  --location-thresholds-pct 0.5,1.0,2.0 `
  --output-dir reports/weekly-foundation/study-01
```

The symbols and split date above are examples only. The runner deliberately does not invent a universal symbol universe, train/test split, or location threshold.

If location sensitivity is not being tested yet, omit the threshold argument:

```powershell
python -m audit.weekly_foundation_runner `
  --symbols LT.NS,RELIANCE.NS,TCS.NS,INFY.NS `
  --horizons 5,10,15 `
  --out-of-sample-start-week 2025-01-01 `
  --output-dir reports/weekly-foundation/study-01
```

If no out-of-sample boundary is supplied, WF6 marks the observations as unsplit rather than silently choosing one.

---

## Output bundle

The runner writes:

```text
weekly_foundation_summary.json
weekly_replay_records.csv
weekly_promotion_observations.csv
weekly_promotion_summaries.csv
weekly_location_sensitivity.csv
weekly_leave_one_symbol_out.csv
```

### `weekly_foundation_summary.json`

Compact execution summary:

```text
symbols
symbol_count
horizons
audited bars
A/B/C/D replay bucket counts
WF6 observation count
WF6 summary count
location-sensitivity row count
leave-one-symbol-out row count
```

It contains no production recommendation.

### `weekly_replay_records.csv`

One row per audited completed week, including:

```text
legacy qualification/actionability/direction
legacy blockers
shadow thesis state/basis/direction
shadow supported flag
contradiction state
A/B/C/D bucket
direction agreement
legacy and shadow forward outcomes when applicable
```

This is the primary file for inspecting Bucket B and Bucket C cases.

### `weekly_promotion_observations.csv`

Point-in-time WF6 candidate observations including:

```text
evidence family
evidence code when applicable
present / absent
regime
partition
legacy state
shadow state
A/B/C/D bucket
contradiction state
location relation / distance
later structural outcome
forward return / MFE / MAE
```

### `weekly_promotion_summaries.csv`

Present-vs-absent cohort comparisons by:

```text
evidence candidate
named VSA code when applicable
direction
5/10/15-week horizon
in-sample / out-of-sample / all
regime
```

The file reports descriptive deltas only. A positive delta is not automatically a promotion decision.

### `weekly_location_sensitivity.csv`

Generated only when caller-supplied distance thresholds are provided. It compares supportive-near-zone observations with other eligible location observations at each supplied threshold.

### `weekly_leave_one_symbol_out.csv`

For multi-symbol studies, this compares each held-out symbol with the remaining symbols. It is designed to reveal whether an apparent effect is concentrated in one symbol rather than robust across the universe.

---

## What must be reviewed before WF7

The study exists to answer factual questions, not to force a predetermined redesign.

### Legacy-vs-shadow

Review at minimum:

```text
How large is Bucket C?
How large is Bucket B?
Are Bucket C outcomes meaningfully better than Bucket D?
Are Bucket B cases showing useful legacy conservatism?
Does shadow support systematically appear earlier than legacy actionability?
Does earlier shadow support increase adverse excursion materially?
```

### Legacy gate causes

For Bucket C, inspect whether misses are concentrated in:

```text
qualification missing
stale structural qualification with no VSA
named-VSA confirmation missing
named-VSA confirmation stale
opposing named VSA present
professional pressure conflict
```

This tells us whether WF7, if any, belongs in structural persistence, named-VSA confirmation, or contradiction policy.

### Evidence candidates

For each WF6 candidate inspect:

```text
sample count
out-of-sample direction of effect
leave-one-symbol-out stability
regime dependence
5/10/15-week consistency
MFE improvement
MAE deterioration or improvement
structural confirmation vs invalidation ordering
```

Candidates include:

```text
Effort / Result
Absorption
location
prior aligned campaign context
professional structural progression
rejection behavior
named VSA by regime
```

---

## What this runner does NOT decide

It does not emit:

```text
PROMOTE
REJECT
PASS
FAIL
BUY
SELL
ACTIONABLE
```

It also does not create or modify:

```text
PatternQualification
scanner evidence weights
named-VSA sets
professional scoring
ranking
WeeklySetup
Weekly→Daily coordinator
daily entry
execution
alerts
orders
```

The result object itself exposes `is_actionable == False`.

---

## WF7 readiness rule

WF7 remains blocked until a real historical study is run and reviewed.

Possible evidence-driven outcomes remain:

```text
1. Legacy gate is appropriately conservative
   → no qualification change.

2. Legacy structural persistence is useful but materially late
   → test a broader behavior-based qualification seam.

3. Named-VSA hard confirmation causes robust avoidable misses
   → test a behavior confirmation replacement in shadow first.

4. Opposing named-event rejection is too binary
   → test WF3 contradiction state as the policy seam.

5. Read-only evidence has no robust incremental value
   → keep it read-only.
```

There is no requirement that WF7 change production behavior. "No change" is a valid audit result.

---

## Manual validation for this PR

```powershell
git fetch origin
git checkout feat/wf6-historical-study-runner
git pull origin feat/wf6-historical-study-runner

python -m pytest tests/test_weekly_foundation_runner.py tests/test_weekly_evidence_promotion_audit.py tests/test_weekly_replay_comparison.py -v
python -m pytest tests/test_shadow_weekly_thesis.py tests/test_weekly_behavior_evolution.py tests/test_weekly_behavior_state.py tests/test_weekly_decision_audit.py -v
python -m pytest tests/test_weekly_legacy_decision_baseline.py tests/test_scanner_full_resume_equivalence.py tests/test_production_scanner.py -v
python -m pytest tests -q
```

After validation and merge, run the historical study against the chosen representative symbol universe. Review those outputs before opening any WF7 production-remediation PR.
