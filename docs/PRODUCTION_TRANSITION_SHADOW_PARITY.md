# Production Transition Shadow Parity

## Purpose

This document records the Phase 4 scanner-architecture guardrail added before the first production wiring step.

The goal was to compare production scanner output against transition-runner output before changing production routing. The guardrail remains useful after production wiring because it keeps comparing the current production result with an independently computed transition-runner result.

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
- shadow-helper isolation from production routing

## Production boundary at creation

When this guardrail was introduced, `production_scanner.py` remained untouched and continued to use the existing incremental/full-replay production path.

The next approved production-wiring slice may use this guardrail to route a narrow full-replay path through `HistoricalScannerRunner`, while keeping valid checkpoint resume behavior on `IncrementalScannerEngine`.

## Why this comes before production wiring

The transition runner already has historical and audit parity coverage. Production adds more risk because it owns durable scanner state, checkpoint validation, fallback diagnostics, and latest-actionable output. Shadow comparison gives CI a way to detect production-vs-transition divergence before and after runtime paths are switched.

## Next safe step

The first production wiring PR should be narrow, should preserve fallback diagnostics, and should not alter detector logic or scoring/actionability policy.

Do not route valid checkpoint resume through the transition runner until the full-replay production slice is stable.
