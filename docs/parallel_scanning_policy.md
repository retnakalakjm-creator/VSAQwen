# Parallel Scanning Policy

ProVSA supports bounded parallel scanning for multi-symbol live observation runs.

## Scope

Parallelism is an orchestration optimization only. It does not change:

- weekly aggregation
- completed-week filtering
- metric calculations
- trend analysis
- evidence generation
- qualification
- professional scoring

Each symbol still travels through the same single-symbol scanner path.

## Worker limits

The live scanner accepts `--workers` and defaults to a conservative worker count. Worker count is bounded by the number of requested symbols and must be greater than zero.

Use lower worker counts when scanning many symbols against online data providers to avoid rate-limit pressure. A good starting range is 2 to 4 workers for live runs.

## Deterministic output

Parallel execution preserves input symbol order in the returned and printed observations. This makes CLI output, JSON-line consumers, and future benchmark comparisons easier to compare.

## Error isolation

A failure for one symbol returns a non-actionable error payload for that symbol and does not stop the rest of the scan batch.

Error payloads use:

- `qualification="ERROR"`
- `actionable=false`
- `error=<exception class name>`
- `reason=<exception message>`

## Live polling

The live loop retains the previous optimization boundary: a symbol is only rescanned when its latest downloaded daily bar key changes or when no observation exists yet.
