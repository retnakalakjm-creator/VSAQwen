# Swing pivot and confirmation timing policy

A confirmed swing has two separate timestamps:

- **Pivot bar / pivot week**: the bar where the swing high or swing low actually occurred.
- **Confirmation bar / confirmation week**: the later bar where the reversal became knowable under the swing confirmation rules.

The pivot bar is useful for technical structure: higher highs, higher lows, lower highs, lower lows, amplitude, and swing duration.

The confirmation bar is the causal boundary. A system must not behave as if the swing was known before this bar closed.

## API compatibility

`StructuralSwingDTO` keeps the older fields for backward compatibility:

- `bar_index`
- `week`
- `confirmation_index`

For clarity, new code should prefer the explicit fields:

- `pivot_bar_index`
- `pivot_week`
- `confirmation_bar_index`
- `confirmation_week`

`bar_index` and `week` are aliases for `pivot_bar_index` and `pivot_week`.

## Trading interpretation

A swing can be drawn at its pivot bar after confirmation, but it can only influence decisions from the confirmation bar onward. Backtests and live scanner output should use confirmation timing whenever evaluating when information became available.
