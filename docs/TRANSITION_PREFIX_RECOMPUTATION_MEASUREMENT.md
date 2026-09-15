# Transition Prefix Recomposition Measurement

## Purpose

This note captures the optimization target after the production transition migration was closed.

Production now reaches the transition path for:

- full replay/bootstrap/fallback candidates;
- valid checkpoint resume candidates;
- scanner snapshot creation and refresh.

Before changing runtime behavior, this guardrail documents and tests the current repeated-prefix recomputation shape so later optimization PRs can prove they only reduce duplicate work, not scanner semantics.

## Current measured behavior

`ScannerTransitionEngine.scan_to_index(metrics, target_index)` currently starts from an empty `ScanState` and calls `run_to_index(...)` through every bar from `ScannerEngine.MIN_REPLAY_BARS` to `target_index`.

Each step calls `features_for(metrics, index)`, and `features_for(...)` currently builds a copied point-in-time metrics prefix with:

```python
metrics.iloc[: index + 1].copy()
```

Therefore repeated independent `scan_to_index(...)` calls for increasing target bars rebuild earlier prefixes again. This is the intentional behavior captured by `tests/test_transition_prefix_recomputation_measurement.py` before optimization begins.

## Existing safe reuse seam

`ScannerTransitionEngine.run_to_index(metrics, target_index, state=existing_state)` already supports continuing from a prior `ScanState`.

When a caller supplies a state whose `last_bar_index` is behind the target, the runner starts at `last_bar_index + 1` and evaluates only the new suffix. The measurement test locks this seam because it is the safest future optimization boundary.

## Optimization contract for later PRs

A later optimization may reuse transition state or cached per-prefix work only if it preserves:

- candidate output parity for every target bar;
- strict sequential step ordering;
- point-in-time metrics visibility;
- engine/config/data fingerprint behavior at production state boundaries;
- fallback diagnostics and checkpoint validation behavior.

## Non-goals for this PR

This PR does not change:

- detector rules or VSA evidence semantics;
- scoring, ranking, qualification, or actionability;
- production scanner runtime behavior;
- API or frontend behavior;
- replay/manual-review behavior;
- HVR, stopping-volume, or climactic-action logic;
- trade plans, alerts, or orders.
