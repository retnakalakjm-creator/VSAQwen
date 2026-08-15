# TEST Event Specification

This document records the current audit-stage semantics for the VSA `TEST` event.

It is a research/specification artifact only. It does not enable TEST, change weights, qualification rules, or scanner actionability.

## Core principle

A real-market TEST does not need to reproduce a textbook pattern perfectly.

The engine should identify a low-effort response to prior selling pressure and judge it in context. Individual confirmations are evidence, not mandatory textbook checkboxes unless later testing proves they should gate the event.

## Current detector baseline

The existing detector requires:

- recent selling campaign
- down bar
- low volume
- narrow spread

The existing implementation also evaluates:

- volume decreasing
- strong close
- higher low

Those latter observations are currently confirmations and do not gate emission.

## Audit findings

The full-history audit currently identifies eight TEST events: `149`, `152`, `248`, `338`, `346`, `510`, `942`, and `1084`.

The audit did **not** find a single textbook checklist that reliably separates useful TESTs from failures.

### Context and response

- `149` and `152` show structural weakness without a confirmed downtrend and later positive medium-term follow-through, despite only partial immediate area holding.
- `248` is the strongest positive example. All three contextual confirmations pass and the TEST area holds through the four-bar response window.
- `338`, `346`, and `510` occur in confirmed downtrends without structural weakness and show early area failure.
- `942` is an important counterexample: it has structural weakness, no confirmed downtrend, a higher low, and decreasing volume, yet it fails the TEST area immediately and is followed by renewed supply.
- `1084` also demonstrates that structural weakness and a higher low are not sufficient by themselves.

### Structural location

Testing a recent structural low is **not required**. Some TESTs occur near prior structural lows, while `248` and other cases are materially farther away and can still produce useful outcomes. Location is context, not a mandatory gate.

### Pre-TEST change of character

A simple count of supportive changes before TEST does **not** reliably distinguish outcomes. Some failures show several apparent supportive changes, while the strongest positive example does not require a large change count.

### Effort/result sequence

The final sequence audit confirms that a preceding effort/result pattern is informative but not a mandatory textbook prerequisite:

- `346`, `942`, and `1084` show descriptive selling-effectiveness loss before TEST, yet all fail shortly afterward.
- `248` has meaningful prior high effort with weak/mixed results, but the audit classifies selling effectiveness as still effective or unclear and it becomes the strongest TEST example.
- `149`, `152`, `338`, and `510` do not contain enough clearly defined high-effort precursor bars for the audit classification to be decisive.

This means the TEST should not be forced into a rigid precursor sequence such as `high effort -> weak result -> TEST`.

## Frozen working semantics

A production-quality TEST represents a **low-effort probe after meaningful recent selling pressure**. The detector may establish that event from current-bar and prior-context evidence, but it must not claim that demand has taken control merely because TEST occurred.

The event should therefore be interpreted through these layers:

1. **Event evidence:** down bar, low volume, narrow spread.
2. **Campaign context:** meaningful recent selling pressure and its broader structural environment.
3. **Supporting observations:** decreasing volume, higher low, acceptable/strong close, supply drying, or related structural context when present.
4. **Contradiction:** persistent confirmed downtrend, obvious continuing supply, or other evidence materially inconsistent with a bullish Test interpretation should weaken the event rather than be ignored.
5. **Response validation:** area holding and subsequent demand/supply behavior are validation evidence, not inputs available to the historical TEST detector itself.

No single supporting condition is mandatory merely because it is present in textbook examples.

## What TEST must not claim

A TEST event alone must not imply:

- confirmed accumulation,
- confirmed demand dominance,
- successful support,
- immediate bullish continuation,
- or a trade entry.

Those conclusions belong to downstream contextual qualification and persistence logic.

## Production status

`TEST` has passed the current validation gates and is approved for production integration.

Validated point-in-time population:

- 47 TEST events across 8 symbols.
- 27 positive 8-bar outcomes.
- 14 negative 8-bar outcomes.
- 6 flat outcomes.
- 41 decisive outcomes.
- 65.85% positive decisive rate.
- Leave-one-symbol-out positive decisive rate: 62.86%–69.44%.
- Semantic audit: 47/47 low-effort probes with meaningful selling context.
- 0 tested persistent-downtrend contradictions.
- Interaction audit: 4 same-bar NO_SUPPLY overlaps and 10 nearby conflicts; no hard conflict gate was justified.

TEST remains a contextual confirmation event and must not independently imply demand dominance, accumulation, or a trade entry.

## Enablement requirement

Before production scoring or actionability is changed, the production integration must reproduce the validated 47-event point-in-time population and pass focused interaction/regression tests.

No future-response information may be used when determining whether TEST emits.
