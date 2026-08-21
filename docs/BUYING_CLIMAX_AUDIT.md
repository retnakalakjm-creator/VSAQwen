# BUYING_CLIMAX Audit Summary

This is the authoritative audit addendum for `BUYING_CLIMAX` and should be read together with `docs/PRIMARY_VSA_EVENT_MATRIX.md` and `PROJECT_ARCHITECTURE.md` until their next consolidated documentation refresh.

## Production path

- Collector: `evidence/supply.py::_collect_buying_climax`
- Engine path: `EvidenceEngine.collect()` → `collect_supply()`
- Campaign gate: buying campaign required
- Latest production readiness: `PASS`
- Campaign-qualified events: `181`
- Production emissions: `181`
- Duplicate emissions: `0`
- Campaign mismatches: `0`
- Runtime-weight out-of-bounds events: `0`
- Runtime bounds: `0.50 .. 2.00`
- Interaction penalty in production: `NO`
- Production score mutation: `NO`

## Weight provenance

The codebase has three distinct weight concepts:

1. **Registry/profile weight:** `1.00` in `evidence/profiles.py`.
2. **Runtime weight:** dynamically calculated by `WeightCalculator._buying_climax_weight(ctx)`.
3. **Empirical reference weight:** `0.38`, used only in analysis/counterfactual decision-value tests.

The full runtime provenance audit observed `BUYING_CLIMAX` runtime weights from `0.90` to `2.00` with mean approximately `1.4464`, confirming that the event is dynamically weighted in the current production architecture.

## Interaction evidence

For the 181 campaign-qualified events:

- `UPTHRUST` overlap: `181 / 181`
- `INCREASING_DEMAND + UPTHRUST`: `119`
- `UPTHRUST` only: `53`
- all remaining combinations: `9`

`UPTHRUST` alone is not a reason to suppress `BUYING_CLIMAX`: the pure group produced `66.04%` positive decisive outcomes and `+4.75%` mean 8-bar return.

The large `INCREASING_DEMAND + UPTHRUST` combination was weaker at `51.69%` positive decisive and `+2.20%` mean return.

## Counterfactual interaction penalty

A `0.20` penalty on only `INCREASING_DEMAND + UPTHRUST` improved the aggregate BUYING_CLIMAX decision-value metrics:

- positive decisive rate: `56.35%` → `57.12%`
- mean 8-bar return: `+3.03%` → `+3.15%`

The penalized population still remained below the eligible-market baseline (`60.79%` positive decisive; `+3.83%` mean return).

Therefore the `0.20` interaction penalty is **provisional analysis policy only** and is not part of production scoring.

## Documentation rule

Do not describe `BUYING_CLIMAX` as non-scoring merely because the empirical reference weight is `0.38` or because the standalone candidate population is below market baseline. It is production-active and dynamically weighted. The empirical `0.38` value is not the current production runtime weight.
