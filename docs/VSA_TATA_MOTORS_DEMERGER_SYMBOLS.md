# Tata Motors Demerger Symbol Maintenance

PR #95 updates the Milestone 6 VSA audit baskets after the Tata Motors demerger/listing symbol changes.

## Symbol changes

- `TATAMOTORS.NS` is no longer used in the repeatable audit baskets.
- `TMPV.NS` is used for Tata Motors Passenger Vehicles.
- `TMCV.NS` is included in the expanded 60-symbol basket for the commercial vehicles listing.

## Basket impact

### `milestone6_standard_india_large_cap_30`

The standard 30-symbol regression basket keeps its count unchanged by replacing:

```text
TATAMOTORS.NS -> TMPV.NS
```

### `milestone6_expanded_india_large_mid_60`

The expanded 60-symbol basket keeps the first 30 symbols aligned with the standard basket, so it now includes `TMPV.NS` in the original Tata Motors slot.

It also adds `TMCV.NS` to keep both post-demerger Tata Motors entities visible during broader audit review.

To preserve the exact 60-symbol basket size, `IOC.NS` is removed from the expanded additional-symbol list. Oil/energy/PSU coverage remains represented through existing names such as `ONGC.NS`, `BPCL.NS`, and `GAIL.NS`.

## Scope

This is a basket-maintenance change only.

It does not:

- fetch market data;
- call providers;
- replay the scanner by itself;
- change scanner state;
- activate detectors;
- change Stopping Volume, Spring/Shakeout, Absorption, Effort-vs-Result, or High Volume Reversal behavior;
- change scoring or ranking;
- change API behavior;
- change frontend behavior;
- change persistence.

## Follow-up audit

After merge, rerun the expanded basket workflow and compare whether `TMPV.NS` or `TMCV.NS` adds any new lifecycle or detector-gate clusters.
