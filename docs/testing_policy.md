# Testing Policy

Milestone 3 separates fast regression tests from historical analysis scripts.

## Default pytest scope

The default test phase is for deterministic, regression-oriented tests that should
run on every local validation pass:

```cmd
pytest
```

Default collection intentionally excludes stale historical audit and analysis
scripts that live under `tests/` but are not part of the fast regression suite.
The exclusion is configured in `tests/conftest.py` through `collect_ignore_glob`.

Excluded patterns include:

- `benchmark_*.py`
- `debug_*.py`
- `profile_*.py`
- `run_*.py`
- `*_analysis.py`
- `*_audit.py`
- `*_counterfactual.py`
- `*_harness.py`
- `*_report.py`
- `*_robustness.py`

## Why this matters

Historical audit scripts often depend on local cache state, large symbol
universes, CSV artifacts, or long-running outcome windows. Keeping them in the
default pytest path makes routine validation slower and less deterministic.

They remain in the repository as reference material, but they should not block
normal development or release-gate testing.

## Running an archived analysis explicitly

Run an excluded script directly when doing research work:

```cmd
python tests\run_hidden_demand_policy_audit.py
```

Or run a specific pytest-compatible historical test only when you intentionally
want that audit check:

```cmd
pytest tests\test_decision_outcome_audit.py
```

## Physical archive plan

This PR performs the first safety step: stale audit checks are moved out of the
default test phase. A later housekeeping PR can physically move the old scripts
from `tests/` into an archive folder once import dependencies are reviewed.

That avoids breaking reference scripts while still speeding up normal testing now.

## Milestone 3 direction

New reusable audit logic should live under `audit/` as importable modules.
New fast regression tests for those modules should remain under `tests/` with
focused fixtures and no network dependency.

Avoid adding new long-running research scripts to default pytest collection.
