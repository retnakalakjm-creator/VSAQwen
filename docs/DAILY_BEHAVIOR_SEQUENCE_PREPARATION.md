# K5 + K6 to Frozen K4 Daily Sequence Composer

## Purpose

K7 closes the prepared-input gap between the validated M11 producers and the
frozen K4 interchange contract.

It composes the following flow:

    real completed daily OHLCV
            |
            +-- K5 -> point-in-time daily Evidence
            |
            +-- K6 -> causal armed weekly direction
                         |
                         v
            DailyBehaviorSequenceStudyInput
                         |
                         v
                  K4 frozen dataset

K7 does not create another detector or another weekly-direction rule.

## Exact alignment gate

K5 and K6 independently receive the same symbol, raw daily frame, now boundary,
and trading calendar.

Before anything is frozen, K7 requires their retained completed-session
sequences to be exactly identical.

If row count or session identity differs, preparation fails closed.

This protects the positional bar_index contract used by K3/K4.

## K4 price boundary

K4 intentionally stores the price fields consumed by the sequence study:

    close
    high
    low

The full raw OHLCV provenance is still preserved through the K5 source
fingerprint, which covers session, open, high, low, close, and volume.

## Provenance

The K4 source metadata records the K7 composer identity, K5 producer identity,
K5 raw daily source fingerprint, K6 producer identity, K6 weekly/setup
visibility fingerprint, caller-supplied source reference, caller-supplied
preparation timestamp, and optional notes.

The timestamp is explicit input rather than generated internally so a frozen
case remains attributable to the caller's preparation run.

## Weekly authority

K7 accepts WeeklySetup history and passes it to K6.

It does not derive weekly direction from daily price movement and does not run a
daily substitute for weekly qualification.

The source of historical WeeklySetup objects remains the existing
production-weekly scanner/materializer path.

## Research-only boundary

K7 is non-actionable.

It does not change weekly production qualification, scanner scoring or ranking,
DailyEntryEngine, F3 trigger/replay semantics, execution timing, alerts, or
orders.

## First genuine case

The repository deliberately does not commit a fabricated real OHLCV fixture.

After K7 is validated locally, the first genuine case should be prepared from an
actual downloaded or cached daily history plus historical production-weekly
WeeklySetup outputs. The resulting K4 JSON is then fingerprint-frozen and can be
passed unchanged through K3, K2, and K1 for a small reviewable historical study.
