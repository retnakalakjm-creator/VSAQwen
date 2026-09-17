# WF7B — Contradiction Reason Decomposition Audit

## Purpose

WF7A showed that treating all shadow contradictions as one suppression rule is not robust enough for production promotion. Several policies improved full-sample or in-sample outcomes but weakened or reversed out of sample.

WF7B therefore asks a narrower question:

> Which specific shadow relationship is actually present on a legacy-actionable week, and does that relationship behave consistently when persistent multi-week episodes are counted once rather than once per bar?

WF7B is read-only. It does not change production qualification, actionability, ranking, WeeklySetup, daily entry, execution, alerts, or orders.

## Source

WF7B consumes the WF7A `WeeklyActionabilityCounterfactualReport`.

WF7A stores each legacy-actionable week once per counterfactual policy. The underlying reasons are policy-independent, so WF7B takes one canonical policy copy and deduplicates the four repeated rows before analysis.

## Exclusive reason classes

Each unique legacy-actionable week receives exactly one audit class:

```text
SAME_DIRECTION_SUPPORTED
CAMPAIGN_CHALLENGED
OPPOSITE_SUPPORTED_THESIS
STRUCTURAL_INVALIDATION
SHADOW_SUPPORT_MISSING
```

The classes use explicit precedence:

```text
STRUCTURAL_INVALIDATION
    > OPPOSITE_SUPPORTED_THESIS
    > CAMPAIGN_CHALLENGED
    > SAME_DIRECTION_SUPPORTED
    > SHADOW_SUPPORT_MISSING
```

This precedence is only a decomposition taxonomy. It is not a production score or severity weight.

### SAME_DIRECTION_SUPPORTED

The shadow thesis is in a supported state and points in the same direction as the legacy actionable qualification.

### CAMPAIGN_CHALLENGED

WF7A reports `CAMPAIGN_CHALLENGED` for the same legacy direction. Generic missing support may coexist in the source reasons, but the more specific challenged relationship is used as the exclusive WF7B class.

### OPPOSITE_SUPPORTED_THESIS

The shadow path has a supported directional thesis opposite the legacy actionable direction.

### STRUCTURAL_INVALIDATION

The same legacy direction has explicit structural invalidation evidence in the shadow thesis path.

### SHADOW_SUPPORT_MISSING

None of the stronger classes applies and the shadow path does not provide same-direction supported status.

## Episode-level audit

A persistent conflict can last several consecutive weekly bars. Counting every bar as an independent observation can make one long campaign dominate aggregate statistics.

WF7B therefore reports both:

```text
BAR
EPISODE_START
```

An episode continues only when all of the following are unchanged from the immediately prior completed weekly bar:

```text
symbol
legacy direction
exclusive WF7B reason class
bar_index is consecutive (+1)
```

Any gap, reason change, direction change, or symbol change starts a new episode.

`EPISODE_START` cohorts use only the first bar of each episode. Forward outcomes remain frozen from that first bar; no future information is used to classify the episode start.

## Historical outputs

The runner exports:

```text
wf7b_contradiction_reason_summary.json
wf7b_contradiction_reason_observations.csv
wf7b_contradiction_reason_summaries.csv
wf7b_contradiction_reason_leave_one_symbol_out.csv
```

Summary tables include 5/10/15-week direction-adjusted close return, MFE, MAE, positive/non-positive counts, in-sample/out-of-sample partitions, bar-level cohorts, episode-start cohorts, and leave-one-symbol-out views.

## Interpretation gate

WF7B must not automatically produce `PROMOTE`, `BLOCK`, or production threshold decisions.

A reason can only become a candidate for later production remediation if it shows useful separation across:

```text
full sample
out-of-sample
bar-level observations
episode starts
multiple symbols / leave-one-symbol-out views
```

A strong in-sample result with weak or reversed OOS behavior remains insufficient.

## Safety boundary

WF7B changes none of the following:

- VSA detectors
- evidence weights
- PatternQualification
- structural qualification thresholds
- named-VSA confirmation
- scanner actionability
- ranking
- WeeklySetup
- weekly-to-daily coordination
- daily behavior / entry
- execution
- alerts / orders

The report property `is_actionable` is always `False`.

## Manual validation

```powershell
git fetch origin
git checkout feat/wf7b-contradiction-reason-decomposition
git pull origin feat/wf7b-contradiction-reason-decomposition

python -m pytest tests/test_weekly_contradiction_reason_audit.py tests/test_weekly_actionability_counterfactual.py tests/test_weekly_replay_comparison.py -v
python -m pytest tests/test_shadow_weekly_thesis.py tests/test_weekly_behavior_evolution.py tests/test_weekly_behavior_state.py tests/test_weekly_decision_audit.py -v
python -m pytest tests/test_weekly_foundation_runner.py tests/test_weekly_legacy_decision_baseline.py tests/test_scanner_full_resume_equivalence.py tests/test_production_scanner.py -v
python -m pytest tests -q
```
