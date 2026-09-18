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
