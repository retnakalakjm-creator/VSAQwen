# WF7A — Legacy Actionability Contradiction Counterfactual

## Purpose

WF5/WF6 historical study results showed that the next safe question is narrower than replacing legacy weekly qualification.

The observed study contained a material population where the legacy path was actionable while the shadow weekly behavior/thesis path was not supportive.  WF7A therefore asks:

> If legacy qualification remained unchanged, would withholding legacy-actionable weeks when the shadow weekly behavior layer materially contradicted them have separated stronger from weaker forward outcomes?

WF7A is **audit-only**.  It does not change production actionability.

## What stays unchanged

WF7A does not modify:

- `PatternQualification`
- the three-event structural qualification requirement
- named-VSA confirmation
- evidence weights
- `ProfessionalScoringEngine`
- scanner score/rank/actionability
- `WeeklySetup`
- weekly-to-daily coordination
- daily behavior/entry
- execution
- alerts or orders

## Counterfactual policies

WF7A evaluates several transparent policies in parallel.  None is automatically selected for production.

### `STRUCTURAL_INVALIDATION_ONLY`

Suppress a legacy-actionable observation only when the shadow thesis for the same legacy direction contains structural invalidation evidence.

### `MATERIAL_CONTRADICTION`

Suppress when the same-direction shadow thesis is challenged by either meaningful/campaign contradiction or structural invalidation.

### `MATERIAL_CONTRADICTION_OR_OPPOSITE_SUPPORT`

Apply the material-contradiction rule and also suppress when a supported shadow thesis points in the opposite direction from the legacy actionable qualification.

### `REQUIRE_SAME_DIRECTION_SHADOW_SUPPORT`

Exploratory strict policy.  Retain a legacy-actionable observation only when the shadow thesis is `SUPPORTED` in the same direction.

This strict policy is intentionally included as a counterfactual boundary case.  It is **not** a production recommendation.

## Observation contract

Only weeks that were already `legacy_actionable=True` are included.

For each such completed weekly bar, WF7A records:

```text
symbol
week
bar index
legacy direction
shadow state
shadow direction
policy
retain/suppress disposition
transparent suppression reasons
5/10/15-week legacy-direction forward outcome
in-sample / out-of-sample partition
```

The decision state is frozen before future outcomes are attached.

## Suppression reasons

WF7A exposes reasons separately from policies:

```text
STRUCTURAL_INVALIDATION
CAMPAIGN_CHALLENGED
OPPOSITE_SUPPORTED_THESIS
SHADOW_SUPPORT_MISSING
```

A policy consumes these observable reasons; it does not create an opaque score.

## Outcome comparison

For every policy/horizon/partition, the report keeps three cohorts separate:

```text
BASELINE   = all legacy-actionable observations
RETAINED   = legacy-actionable observations the counterfactual would keep
SUPPRESSED = legacy-actionable observations the counterfactual would withhold
```

Metrics include:

```text
observation count
complete-outcome count
mean close return
median close return
mean MFE
mean MAE
positive / non-positive close-return counts
retained minus baseline mean return
retained minus suppressed mean return
retained minus suppressed MFE/MAE
```

All returns remain direction-adjusted to the original legacy qualification.

## Robustness views

The caller-defined out-of-sample boundary from the weekly-foundation study is preserved.

WF7A also emits leave-one-symbol-out comparisons for every policy and horizon.  This makes it possible to see whether a separation seen in the aggregate persists when each symbol is isolated rather than being driven by a small set of names.

WF7A does not turn those robustness views into an automatic pass/fail rule.

## Historical runner

Example:

```powershell
python -m audit.weekly_actionability_counterfactual_runner --symbols "RELIANCE.NS,HDFCBANK.NS,ICICIBANK.NS,SBIN.NS,INFY.NS,TCS.NS,LT.NS,BHARTIARTL.NS,ITC.NS,HINDUNILVR.NS,MARUTI.NS,M&M.NS,SUNPHARMA.NS,DRREDDY.NS,NTPC.NS,POWERGRID.NS,ONGC.NS,COALINDIA.NS,ULTRACEMCO.NS,ASIANPAINT.NS" --horizons "5,10,15" --out-of-sample-start-week "2024-01-01" --output-dir "reports/weekly-foundation/wf7a-study-01"
```

The runner first replays the existing weekly-foundation historical stack and then applies the counterfactual policies.  It writes:

```text
wf7a_counterfactual_summary.json
wf7a_counterfactual_observations.csv
wf7a_counterfactual_summaries.csv
wf7a_counterfactual_leave_one_symbol_out.csv
```

## Promotion gate after WF7A

WF7A itself cannot authorize a production change.

A later production PR should be considered only if a narrowly defined suppression semantic shows useful separation between retained and suppressed legacy setups and that separation is reasonably stable across:

```text
multiple forward horizons
out-of-sample observations
leave-one-symbol-out views
bullish and bearish legacy directions
```

If the result is unstable, contradictory, or concentrated in a few symbols, the correct result is to leave production weekly actionability unchanged.
