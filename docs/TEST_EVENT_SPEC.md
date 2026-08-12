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

## Audit finding

The current six-event audit separates into two broad groups:

### Structurally weakening campaign

Bars 149, 152, and 248 showed recent weakness with structural weakness present but no confirmed downtrend.

- 149: partial confirmation; subsequent response was mixed but later price follow-through was positive.
- 152: volume decreasing + higher low; subsequent upward progression improved materially.
- 248: all three confirmations passed; subsequent bars showed immediate upward response and strong later price follow-through.

### Confirmed downtrend without structural weakening

Bars 338, 346, and 510 occurred inside confirmed downtrends without the same structural-weakness profile.

Each was followed quickly by renewed `INCREASING_SUPPLY`, with poor medium-term follow-through.

## Working semantic hypothesis

A useful TEST is more likely when:

1. A genuine recent selling campaign exists.
2. The selling campaign shows evidence that its effectiveness is weakening, preferably through structural weakness rather than merely trend classification.
3. The TEST bar itself shows reduced effort: low volume and narrow spread remain important observations.
4. One or more contextual confirmations strengthen the interpretation, especially reduced volume, acceptable close, and/or a higher low.
5. Subsequent price action does not quickly reintroduce strong supply and begins to show demand or structural improvement.

This is a working hypothesis, not yet a production rule.

## Negative contextual evidence

The following should be treated as disqualifying or strongly weakening context during future audit work, but are not production gates yet:

- confirmed downtrend combined with no structural weakness
- immediate `INCREASING_SUPPLY` after the TEST
- failure to hold the TEST area
- persistent weak/lower closes after the TEST

## Production status

`TEST` remains disabled in `collect_demand()`.

No production threshold, weight, qualification rule, or scanner actionability has been changed as a result of this document.

## Next audit

Expand the audit sample beyond the current six events and test whether the working hypothesis consistently separates stronger and weaker TEST outcomes before modifying `_collect_test()`.
