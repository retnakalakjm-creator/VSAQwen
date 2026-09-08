# Signal vs. Execution Policy

ProVSA scanner candidates distinguish between the bar that generated a setup signal and the bar on which execution may first be evaluated.

## Signal bar

The signal bar is the fully evaluated bar used by the scanner pipeline. Existing fields remain available for backward compatibility:

- `bar_index`
- `week`

New aliases make the meaning explicit:

- `signal_bar_index`
- `signal_week`

## Execution bar

The execution bar is the next available bar after the signal bar:

- `execution_bar_index`
- `execution_week`
- `execution_available`
- `execution_pending`
- `execution_note`

For the latest completed weekly signal, no future bar exists yet, so `execution_bar_index` and `execution_week` are `None`. This means the output is a setup signal, not a same-bar entry.

Execution rules must be evaluated only from the next bar/session after the signal bar. This avoids implying that a trade can be entered using information from the completed signal bar before that bar has closed.
