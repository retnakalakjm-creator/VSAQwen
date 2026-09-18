# Genuine Daily Sequence Case Generator

## Purpose

K8 generates the first reproducible real-market K4 case without weakening the
validated weekly/daily architecture.

The authority chain is:

    actual daily market history
            |
            +--> completed daily sessions
            |
            +--> daily_to_weekly
                    |
                    +--> completed_weekly_only
                            |
                            +--> MetricsEngine
                                    |
                                    +--> HistoricalScannerRunner
                                            |
                                            +--> ScannerCandidate
                                                    |
                                                    +--> materialize_production_weekly_setup
                                                            |
                                                            +--> WeeklySetup history

The resulting WeeklySetup history is passed into K7. K7 then combines K5 daily
Evidence and K6 causal weekly-direction assignments and freezes the result
through K4.

## No substitute qualification

K8 does not infer weekly direction from daily prices.

It does not create a new weekly qualifier.

Only an existing production ScannerCandidate that is already actionable and
persistently qualified can materialize into a WeeklySetup.

If the selected history produces no such setup, genuine-case generation fails by
default instead of fabricating a thesis.

## Production weekly source fingerprint

K8 fingerprints the exact completed weekly OHLCV rows consumed by the production
weekly scanner path:

- week identity;
- open;
- high;
- low;
- close;
- volume.

That fingerprint is added to the K4 provenance notes in addition to K5 and K6
fingerprints.

## CLI

Example:

    python scripts/generate_daily_sequence_case.py LT.NS --now 2026-09-18T16:00:00+05:30 --refresh

Default output:

    reports/daily-behavior-sequences/genuine/LT_NS.json

The command prints a JSON summary with counts and fingerprints.

The generated dataset remains research-only and non-actionable.

## Next step after the first case

Load the generated JSON through K4 and run the unchanged K3 historical study.
Review K1/K2 sequence behavior and outcomes before considering any production
promotion.
