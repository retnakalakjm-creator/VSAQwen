# Shakeout forward-window terminology

The shakeout validation constants use `FORWARD_WINDOW` terminology instead of `LOOKAHEAD` terminology.

## Why

A shakeout candidate can only be validated after later bars confirm a test and recovery. That means the detector may inspect bars after the candidate bar, but only inside a point-in-time data slice that is already available at the current evaluation bar.

`LOOKAHEAD` was misleading because it sounded like future, unavailable data could be used. The correct interpretation is:

- `SHAKEOUT_TEST_FORWARD_WINDOW`: maximum observed bars after the shakeout candidate in which a valid test may appear.
- `SHAKEOUT_RECOVERY_FORWARD_WINDOW`: maximum observed bars after the accepted test in which a valid recovery may appear.

## Causal rule

At evaluation bar `t`, validation may inspect only bars with index `<= t`.

The forward window is relative to an older candidate bar, not relative to the current evaluation boundary. It is causal only when the caller provides point-in-time metrics through the current bar.

## Compatibility

The old names remain as aliases for existing code:

- `SHAKEOUT_TEST_LOOKAHEAD`
- `SHAKEOUT_RECOVERY_LOOKAHEAD`

New code should use the `*_FORWARD_WINDOW` names.
