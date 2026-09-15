# Production Transition Shadow Parity

## Purpose

This document records the next Phase 4 scanner-architecture guardrail after the audit caller was routed through `HistoricalScannerRunner`.

The goal is to compare the current production scanner output against the transition-runner output before any production wiring changes are made. This is a shadow comparison only. It does not change production routing, detector behavior, scoring, ranking, qualification, actionability, trade plans, alerts, orders, frontend behavior, or replay behavior.

## Added guardrail

`production_transition_shadow.py` provides explicit comparison helpers:

```python
compare_latest_candidate_with_transition(metrics, symbol="...")
compare_actionable_with_transition(metrics, symbol="...")
```

Each helper runs the current production path first, computes an independent transition-runner result, and returns a comparison object with:

- `matched`
- production signature
- transition signature
- fallback diagnostics
- production candidate(s)
- transition candidate(s)

The helpers are intentionally passive. They never replace production output with transition output.

## Covered cases

The tests verify production-vs-transition parity for:

- first-run production bootstrap
- resume from persisted checkpoint without fallback
- latest actionable production output
- fallback after stale data fingerprint diagnostics
- empty behavior before the minimum replay window
- production scanner isolation from the transition runner

## Production boundary

`production_scanner.py` remains untouched by this slice. It still uses the existing incremental/full-replay production path.

Do not route production scanner calls through `HistoricalScannerRunner` or `ScannerTransitionEngine` until the next explicitly approved production-wiring PR.

## Why this comes before production wiring

The transition runner already has historical and audit parity coverage. Production adds more risk because it owns durable scanner state, checkpoint validation, fallback diagnostics, and latest-actionable output. Shadow comparison gives CI a way to detect production-vs-transition divergence before the runtime path is switched.

## Next safe step

After this PR passes, the next safe slice is a first production wiring PR guarded by this shadow parity suite. That PR should still be narrow, should preserve fallback diagnostics, and should not alter detector logic or scoring/actionability policy.
