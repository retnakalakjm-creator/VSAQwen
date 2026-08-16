# SPRING Event Specification

This document records the current production semantics and validation record for the VSA `SPRING` event.

`SPRING` is production-integrated but remains **provisional** because the validated production population is still small. This specification records the frozen working semantics; it does not independently change detector weights, qualification rules, or scanner actionability.

## Core principle

A real-market Spring does not need to reproduce a textbook Wyckoff drawing perfectly.

The event should identify a point-in-time break below an established structural support area, followed by recovery, a low-effort test, and later bullish confirmation. Imperfect but meaningful real-market evidence is acceptable as long as the sequence remains faithful to strict VSA methodology.

## Production detector

Production detector:

```text
EvidenceCode.SPRING
evidence/spring.py::collect_spring()
```

The detector operates point-in-time on the current bar and validates the candidate/test/confirmation sequence using only information available through the relevant bar.

## Frozen working semantics

A production-quality Spring represents a **bullish reversal/trap event** with four conceptual stages:

1. Structural support exists.
2. Price penetrates below that support in a controlled, spread-normalized manner.
3. A low-effort test occurs after the break.
4. Bullish follow-through confirms recovery.

The detector should not require every textbook visual characteristic when the underlying VSA sequence remains meaningful.

## Candidate requirements

The current production candidate filters are:

```text
support touches       >= 2
candidate penetration <= 0.50 spread-normalized
```

The candidate is evaluated point-in-time. No future outcome or later confirmation is used to decide whether the historical candidate itself qualifies.

## Test validation

A successful low-effort test is required.

Current production filters include:

```text
test distance       <= 1.00 spread-normalized
test penetration    <= 0.50 spread-normalized
test volume ratio   <= 0.75
test close position >= 2
```

The test must occur within the configured lookahead.

## Bullish confirmation

Bullish confirmation is required within the configured confirmation lookahead.

Confirmation is downstream evidence and must not leak future information backward into the candidate detector during point-in-time historical validation.

## Production weight

Current calibrated production base weight:

```text
SPRING = 0.75
```

This remains **provisional**. The 13-event production sample is not large enough to justify increasing the base weight or tightening the detector further.

## Quality and conflict policy

Normal Spring quality is:

```text
quality = 1.00
```

A same-bar `UPTHRUST` or `BUYING_CLIMAX` is treated as a direct bearish contradiction to the bullish Spring interpretation.

Production policy:

```text
Spring detected                         KEEP
Base weight                             0.75
Same-bar bearish conflict quality       0.50
Spring rejection                        NO
```

The conflict changes evidence quality/confidence rather than acting as a hard rejection gate.

## Validation record

The current production replay baseline is:

- production Spring events: `13`
- symbols with events: `6 / 8`
- `POSITIVE_8_BAR`: `6`
- `NEGATIVE_8_BAR`: `4`
- `FLAT_8_BAR`: `3`
- failures: `0`

The 8-bar outcome classification is an audit measure only. It is not used by the detector when deciding whether Spring evidence exists.

## Production readiness

Current status:

```text
Status: Production-integrated / provisional
Base weight: 0.75
Point-in-time detector: YES
Test validation: YES
Bullish confirmation: YES
Focused regression coverage: YES
Production replay: VERIFIED
```

The event is usable by the production evidence pipeline, but its status should remain provisional until a larger validation population supports stronger confidence in the calibration.

## What SPRING must not claim

A Spring event alone must not imply:

- confirmed accumulation,
- guaranteed reversal,
- confirmed demand dominance,
- immediate trade entry,
- or a guaranteed positive future outcome.

Those conclusions belong to downstream contextual qualification and persistence logic.
