# M12 / L5 — Daily Detector Correction Design Audit

## Purpose

L5 converts the validated L4B detector findings into explicit correction
candidates without modifying production semantics.

The goal is to separate three classes of work:

1. changes that can be projected exactly from the frozen L3 ledger;
2. source-only metadata corrections with deterministic zero event impact;
3. semantic predicate changes that require a fresh causal replay.

L5 does not choose a winner and does not recommend a production rule.

## Inputs

L5 consumes the canonical L4B semantics directory and the exact L3
confirmation directory from which L4B was built.

Canonical L4B:

    reports\daily-events\confirmation-semantics\
      milestone6_standard_india_large_cap_30_frozen_2026-09-18

Canonical L3:

    reports\daily-events\confirmation-counterfactual\
      milestone6_standard_india_large_cap_30_frozen_2026-09-18

The loader hashes every L4B artifact and verifies that the L4B source lineage
points to the exact supplied L3 summary and observation ledger.

## Finding classes

### 1. Identical mandatory detector contracts

L4B found one mandatory collision:

    BUYING_CLIMAX
    UPTHRUST

Both use:

    Buying Campaign
    Bullish Bar
    Very High Volume
    Above Average Spread

L5 enumerates every non-empty AND subset of each detector's three confirmation
clauses.

That produces:

    7 BUYING_CLIMAX gate candidates
    7 UPTHRUST gate candidates
    14 total gate candidates

Every BC candidate is crossed with every UT candidate:

    7 x 7 = 49 projection rows

For every pair L5 records:

- retained BC count;
- retained UT count;
- overlap;
- Jaccard;
- BC-only count;
- UT-only count;
- coverage of the current collision set.

This is a projection from existing L3 evidence only. It does not imply that a
candidate should become production logic.

### Distinctive-only pair

The confirmation clauses unique to each detector are:

    BUYING_CLIMAX -> Increasing Volume
    UPTHRUST      -> Lower Close Than Previous

Canonical L3 projection:

    BC retained             3,327 / 4,497 = 73.98%
    UT retained               177 / 4,497 =  3.94%
    overlap                   121
    BC only                 3,206
    UT only                    56
    union                   3,383
    current-set coverage      75.23%
    Jaccard                    0.03577

This is useful evidence about separation, but the very different retention
rates mean it is not itself a production recommendation.

## NO_SUPPLY correction alternatives

### Environment label / predicate mismatch

Current contract:

    label:      Bullish Environment
    predicate:  ctx.is_bearish_environment()

L5 records two distinct correction classes.

#### Align label to predicate

    rename label to Bearish Environment
    predicate unchanged

Effect class:

    LABEL_ONLY

Data sufficiency:

    SOURCE_DETERMINISTIC

Projected CURRENT event impact:

    777 -> 777

No replay is required because detector behavior is unchanged.

#### Align predicate to label

    label remains Bullish Environment
    predicate becomes bullish-environment eligibility

Effect class:

    MANDATORY_PREDICATE_CHANGE

Data sufficiency:

    REPLAY_REQUIRED

L3 only contains events that passed the current bearish-environment predicate.
It does not contain the alternate bullish-environment candidate population.
Therefore L5 deliberately does not invent a projected event count.

## NO_SUPPLY redundant Weak Spread

Current mandatory contract contains:

    Narrow Spread -> is_narrow_spread(bar)

Current confirmation contract contains:

    Weak Spread -> has_weak_spread(bar)

The current rule helper resolves:

    has_weak_spread(bar)
      -> is_narrow_spread(bar)

L5 detects this from source-level helper aliasing rather than from a manually
encoded detector exception.

Because the mandatory gate already guarantees the condition:

    Weak Spread passed 777 / 777

Removing the redundant confirmation would not change CURRENT emissions because
confirmations are presently non-gating:

    CURRENT 777 -> 777

But if future confirmation policies were evaluated using only the remaining
two clauses:

    Volume Decreasing
    Weak Selling Result

the canonical L3 projection becomes:

    ANY                 629
    STRICT_MAJORITY     243
    ALL                 243

For two remaining clauses, strict majority and all both require 2 / 2.

## Outputs

    daily_detector_correction_design_summary.json
    daily_detector_correction_findings.csv
    daily_detector_collision_gate_candidates.csv
    daily_detector_collision_projection_matrix.csv
    daily_detector_correction_candidates.csv

## Canonical expected invariants

    requested_symbol_count             30
    event_count                     16635
    finding_count                       3
    mandatory_collision_pair_count      1
    gate_candidate_count               14
    collision_projection_row_count     49
    correction_candidate_count          3
    is_actionable                   false

Expected finding types:

    IDENTICAL_MANDATORY_CONTRACT
    ENVIRONMENT_LABEL_PREDICATE_POLARITY_MISMATCH
    REDUNDANT_CONFIRMATION_IMPLIED_BY_MANDATORY

## Local validation

```powershell
python -m ruff check audit/daily_event_detector_correction_design.py scripts/audit_daily_event_detector_correction_design.py tests/test_daily_event_detector_correction_design.py
```

```powershell
python -m pytest -q tests/test_daily_event_detector_correction_design.py tests/test_daily_event_confirmation_semantics.py tests/test_daily_event_confirmation_counterfactual.py
```

## Canonical run

```powershell
python scripts/audit_daily_event_detector_correction_design.py --semantics-dir reports\daily-events\confirmation-semantics\milestone6_standard_india_large_cap_30_frozen_2026-09-18 --confirmation-dir reports\daily-events\confirmation-counterfactual\milestone6_standard_india_large_cap_30_frozen_2026-09-18
```

This is a ledger-only analysis and should complete quickly.

## Safety

L5 changes no:

- production detector requirement;
- confirmation gate;
- evidence definition;
- event emission;
- scoring/ranking;
- DailyBehavior mapping;
- qualification/actionability;
- API behavior;
- alerts/orders;
- production market-data behavior.

A production detector correction, if justified, must be a separate later PR
with exact before/after replay evidence.
