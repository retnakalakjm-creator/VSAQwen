# M12 / L3 — Daily Detector Confirmation Counterfactual Audit

## Purpose

L3 measures the effect of enforcing the seven detector confirmation clauses
identified by canonical L2 before any production detector semantics change.

The counterfactual remains read-only and non-actionable.

## Canonical source chain

L3 no longer uses the mutable production data loader.

Before replay it validates all three canonical sources:

1. the frozen full-history OHLCV snapshot bundle;
2. the regenerated frozen L1 inventory;
3. the regenerated frozen L2 co-firing summary.

The following lineage must agree exactly:

    snapshot audit id
    snapshot manifest SHA-256
    basket
    period
    cutoff
    L1 summary SHA-256
    L1 emissions SHA-256
    L2 source lineage

The canonical snapshot lineage is:

    audit id = daily-audit-input-snapshot-v1
    basket = milestone6_standard_india_large_cap_30
    period = max
    cutoff = 2026-09-18T00:00:00
    manifest SHA-256 =
      45bb7123d2b3b570cf58241f09cb6175f6052d792f92728b194fc587762fb8ff

Canonical L1 lineage:

    L1 summary SHA-256 =
      04cb67d5c5469befea2e662d35787d6c1373aa5804d1529aaddfcf52056fd534
    L1 emissions SHA-256 =
      6fa63cc5b9bee123cc08ef5f943f94e5a2ecae5e3b05fbf4406739bf60dda6b9

L3 also records the SHA-256 of the exact L2 summary it consumed.

## Policies

    CURRENT_NO_CONFIRMATION_GATE
    ANY_CONFIRMATION
    STRICT_MAJORITY_CONFIRMATIONS
    ALL_CONFIRMATIONS

Definitions:

- CURRENT preserves today's production behavior.
- ANY requires at least one confirmation to pass.
- STRICT_MAJORITY requires more than half to pass.
- ALL requires every confirmation to pass.

These are research policies, not production recommendations.

## Causal replay

Each worker independently loads and verifies a frozen symbol snapshot, then runs
the existing K5 prefix-only daily Evidence path.

For each completed target daily bar:

    frozen completed daily prefix through D
    -> existing Metrics / Swing / Structure / Trend stack
    -> existing EvidenceEngine
    -> instrument only target-bar confirmation-sensitive calls

The wrapper always delegates to the unchanged production evaluate_detector().
Production emission behavior is therefore unchanged.

The seven captured detectors are:

    BUYING_CLIMAX
    NO_DEMAND
    UPTHRUST
    STOPPING_VOLUME
    SELLING_CLIMAX
    TEST
    NO_SUPPLY

## Deterministic identity gate

L3 compares captured CURRENT identities to canonical L1 using:

    symbol + normalized session + code

Because L1 and L3 now consume the exact same frozen snapshots, bar_index is also
expected to match exactly. Any of the following makes the CLI return non-zero:

- symbol failure;
- stable identity mismatch;
- bar-index mismatch.

The old cross-machine cache-drift allowance is no longer needed for canonical
runs because mutable cache history has been removed from the source chain.

## Duplicate physical observations

The instrumentation can physically observe the same stable event more than once
when detector collection paths repeat a call. L3 keeps this measurable as:

    physical_observation_count
    duplicate_observation_count

Policy and pairwise calculations use one canonical observation per stable
identity. Conflicting duplicate payloads raise an error.

## Parallel execution

Frozen replay is parallelized only at the symbol boundary.

- Windows-safe multiprocessing spawn;
- conservative default of at most four workers;
- leaves one logical CPU free when possible;
- longest histories scheduled first;
- final observations restored to requested symbol order;
- worker failure remains isolated and explicit.

The per-symbol K5 replay semantics are unchanged.

## Outputs

    daily_confirmation_counterfactual_summary.json
    daily_confirmation_observations.csv
    daily_confirmation_policy_summary.csv
    daily_confirmation_pairwise.csv
    daily_confirmation_index_drift.csv
    daily_confirmation_failures.csv

## Canonical local run

First validate:

```powershell
python -m ruff check audit/daily_event_confirmation_counterfactual.py audit/daily_event_confirmation_runner.py scripts/audit_daily_event_confirmation_counterfactual.py tests/test_daily_event_confirmation_counterfactual.py tests/test_daily_event_confirmation_runner.py
```

```powershell
python -m pytest -q tests/test_daily_event_confirmation_counterfactual.py tests/test_daily_event_confirmation_runner.py tests/test_daily_event_cofiring.py tests/test_daily_event_inventory.py tests/test_daily_input_reproducibility.py
```

Then run:

```powershell
python scripts/audit_daily_event_confirmation_counterfactual.py --now 2026-09-18T16:00:00+05:30 --input-dir reports\daily-events\inventory\milestone6_standard_india_large_cap_30_frozen_2026-09-18 --input-snapshot-dir reports\daily-events\input-snapshots\milestone6_standard_india_large_cap_30\2026-09-18 --workers 4
```

The L2 directory is inferred as:

    reports\daily-events\cofiring\milestone6_standard_india_large_cap_30_frozen_2026-09-18

The L3 output defaults to:

    reports\daily-events\confirmation-counterfactual\milestone6_standard_india_large_cap_30_frozen_2026-09-18

## Canonical CURRENT baseline

From regenerated frozen L1, the seven affected labels contain:

    BUYING_CLIMAX       4,497
    NO_DEMAND           1,355
    UPTHRUST             4,497
    STOPPING_VOLUME      1,298
    SELLING_CLIMAX       3,436
    TEST                   775
    NO_SUPPLY              777
    --------------------------------
    total               16,635

Therefore the canonical full-basket hard gate is:

    baseline_event_count = 16635
    captured_event_count = 16635
    identity_mismatch_count = 0
    bar_index_mismatch_count = 0
    failed_symbol_count = 0

## Safety

L3 changes no:

- production detector rule;
- confirmation gate;
- evidence weight/direction;
- DailyBehavior mapping;
- weekly qualification;
- scoring/ranking;
- DailyEntry trigger;
- API behavior;
- alert/order behavior.

Only after this canonical counterfactual is validated should a separate
detector-semantics change be considered.
