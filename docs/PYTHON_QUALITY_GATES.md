# Python Quality Gate Policy

## Purpose

M10 introduces Python quality tooling without changing scanner semantics or
forcing a repository-wide modernization in one step.

The rollout is evidence-driven:

1. add a high-signal correctness linter;
2. measure test coverage;
3. establish type-checking scope from observed defects and module boundaries;
4. promote a coverage floor only after the baseline is known and stable.

## J1 first cut

Both hosted and Windows self-hosted backend CI install dependencies from
`requirements-ci.txt`.

### Ruff gate

The first Ruff gate uses only:

```text
E9   syntax/runtime parse failures
F63  invalid comparison/tuple/assert patterns
F7   invalid control-flow constructs
F82  undefined names
```

This deliberately avoids style, formatting, import ordering, complexity, and
large automatic rewrites.

The gate is scoped to active scanner/data/API/domain modules and collected tests.
Archived/manual research tooling is not promoted into the production quality gate
by this cut.

### Coverage baseline

Pytest runs with `pytest-cov` over the core scanner/data/domain packages and
writes `coverage.xml`.

There is intentionally no `--cov-fail-under` threshold in the first cut.

Validated local baseline on Windows / Python 3.13.15:

```text
1018 passed
1 skipped
TOTAL 5500 statements
1437 missed
74% coverage
```

Ruff also passed after removing one genuine stale `evidence.rules.__all__`
export. The first full coverage run exposed four legacy injected-store
compatibility failures; those were fixed by preserving the old `load()` /
`save()` test-double surface while real `ScannerStateStore` instances continue
to use revision-aware CAS.

A percentage chosen before measuring the repository would have been arbitrary.
The retained 74% baseline is now evidence for a later floor decision; this first
cut still does not impose a threshold.

### Type checking

Repository-wide mypy/Pyright is not enabled in the first cut. Pandas-heavy and
legacy dynamic boundaries should be inventoried first so type checking can start
from stable public interfaces rather than produce a large unreviewed suppression
set.

Likely first targets are immutable/domain-facing modules such as scanner policy,
semantic exceptions, recovery telemetry, and state boundaries.

## Safety

These gates do not change:

- VSA detection;
- structural/professional scoring;
- qualification;
- ranking/actionability;
- scanner state semantics;
- market-data policy;
- alerts/execution/orders.


## J1 second cut — typed domain boundaries

The second J1 cut introduces strict mypy only on small stable public/domain
modules:

```text
scanner_exceptions.py
scanner_recovery.py
scanner_policy.py
weekly_setup.py
```

Configuration:

```text
python_version = 3.11
strict = true
follow_imports = skip
```

`follow_imports = skip` is deliberate. The target modules are checked strictly,
but this cut does not recursively pull pandas-heavy or legacy implementation
modules into the typing gate.

The goal is to establish a typed public-boundary island first. Expansion should
happen one boundary at a time after each scope is clean and useful.

This cut does not add `type: ignore` suppressions to runtime code and does not
change scanner behavior.


## J1 third cut — weekly-to-daily typed domain expansion

After the initial typed-domain gate validated, the strict mypy island expands to
three additional modules:

```text
weekly_setup_materializer.py
daily_behavior.py
daily_entry.py
```

These modules form the non-pandas weekly-to-daily domain handoff:

```text
production ScannerCandidate
        ↓
WeeklySetup materializer
        ↓
Daily behavior model
        ↓
Daily shadow-entry observation
```

The pandas/session/replay infrastructure remains outside this cut. In particular,
`weekly_daily_coordinator.py`, `daily_trigger_replay.py`,
`daily_completion.py`, and `trading_calendar.py` are not promoted into strict
typing merely because they are adjacent.

No runtime source changes are required by this cut unless local strict mypy
validation exposes a concrete type-contract defect.
