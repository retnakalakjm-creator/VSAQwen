# M12 / L4B — Detector-Specific Confirmation Semantics Audit

## Purpose

L3 established that confirmation evidence is meaningful, but the seven
confirmation-sensitive detectors do not behave uniformly. L4B therefore audits
the detector contracts and empirical confirmation patterns separately before
any production confirmation rule is considered.

L4B is read-only, non-actionable, and does not replay market data.

## Input

L4B consumes only the completed canonical L3 directory:

    reports/daily-events/confirmation-counterfactual/
      milestone6_standard_india_large_cap_30_frozen_2026-09-18/

Required files:

    daily_confirmation_counterfactual_summary.json
    daily_confirmation_observations.csv

The loader requires:

    failed_symbol_count = 0
    identity_mismatch_count = 0
    bar_index_mismatch_count = 0
    baseline_event_count = captured_event_count
    requested_symbol_count = succeeded_symbol_count
    physical_observation_count =
      captured_event_count + duplicate_observation_count
    is_actionable = false

It also fingerprints the exact L3 summary and observation ledger and preserves
the existing snapshot/L1/L2 lineage hashes.

## Static detector contract

L4B extracts the source-level contract for each detector directly from the
production collector function:

    mandatory requirement name
    mandatory passed= expression
    confirmation requirement name
    confirmation passed= expression

No requirement list is copied manually into the audit.

Canonical scope:

    BUYING_CLIMAX
    NO_DEMAND
    NO_SUPPLY
    SELLING_CLIMAX
    STOPPING_VOLUME
    TEST
    UPTHRUST

Expected contract surface:

    detectors:                 7
    total contract rows:      51
    confirmation clauses:     21

## Empirical outputs

For every detector L4B measures:

- current event count;
- mandatory and confirmation contract fingerprints;
- detectors with an exactly identical mandatory contract;
- number of distinct confirmation patterns;
- zero / any / strict-majority / all survival;
- mean passed confirmation count;
- mean confirmation pass fraction.

For every individual confirmation clause it measures:

- pass count;
- fail count;
- pass rate;
- number of symbols on which it passes.

It also exports the full exact passed-confirmation pattern distribution for each
detector.

## Important source facts already exposed

### BUYING_CLIMAX vs UPTHRUST

These two detectors have the exact same mandatory contract:

    Buying Campaign
    Bullish Bar
    Very High Volume
    Above Average Spread

They also share two confirmation clauses:

    Wide Spread
    Weak Close

Their third confirmations differ:

    BUYING_CLIMAX -> Increasing Volume
    UPTHRUST      -> Lower Close Than Previous

On canonical L3, the individual clause pass rates were approximately:

    BUYING_CLIMAX
      Wide Spread            65.04%
      Weak Close              3.96%
      Increasing Volume      73.98%

    UPTHRUST
      Wide Spread            65.04%
      Weak Close              3.96%
      Lower Close Previous    3.94%

This explains why CURRENT collapses the labels while confirmation evidence can
separate them. L4B records the underlying clause distributions rather than
selecting a threshold.

### NO_SUPPLY environment label

The production contract currently contains:

    requirement name:
      "Bullish Environment"

but its actual passed expression is:

    ctx.is_bearish_environment()

L4B preserves both the label and expression verbatim so this inconsistency can
be reviewed explicitly later.

### NO_SUPPLY Weak Spread redundancy

NO_SUPPLY has mandatory:

    Narrow Spread -> is_narrow_spread(bar)

and confirmation:

    Weak Spread -> has_weak_spread(bar)

In evidence/rules.py:

    has_weak_spread(bar)
        -> is_narrow_spread(bar)

Therefore this confirmation is already implied by the mandatory candidate gate.
Canonical L3 confirms the consequence:

    Weak Spread passed 777 / 777 = 100%

This is evidence for detector-specific semantics review, not a production
change in this PR.

## Outputs

    daily_confirmation_semantics_summary.json
    daily_confirmation_detector_summary.csv
    daily_confirmation_detector_contracts.csv
    daily_confirmation_requirement_rates.csv
    daily_confirmation_pattern_distribution.csv

For the canonical full L3 ledger the expected high-level invariants are:

    requested symbols:                 30
    detectors:                           7
    events:                         16,635
    contract rows:                      51
    confirmation requirement rows:      21
    confirmation pattern rows:          56
    is_actionable:                   false

## Local validation

```powershell
python -m ruff check audit/daily_event_confirmation_semantics.py scripts/audit_daily_event_confirmation_semantics.py tests/test_daily_event_confirmation_semantics.py
```

```powershell
python -m pytest -q tests/test_daily_event_confirmation_semantics.py tests/test_daily_event_confirmation_counterfactual.py tests/test_daily_event_cofiring.py
```

## Canonical run

```powershell
python scripts/audit_daily_event_confirmation_semantics.py --input-dir reports\daily-events\confirmation-counterfactual\milestone6_standard_india_large_cap_30_frozen_2026-09-18
```

Default output:

    reports\daily-events\confirmation-semantics\
      milestone6_standard_india_large_cap_30_frozen_2026-09-18

This audit should complete quickly because it analyzes the already-frozen L3
ledger and does not rerun Metrics, Swing, Structure, Trend, or Evidence engines.

## Safety

This PR changes no:

- detector requirement;
- confirmation gate;
- Evidence emission;
- scoring/ranking;
- DailyBehavior mapping;
- qualification/actionability;
- API behavior;
- alerts/orders;
- market-data path.

A later production change, if any, must be a separate PR supported by the L4B
detector-specific evidence.
