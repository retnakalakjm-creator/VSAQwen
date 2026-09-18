# Frozen K4 Daily Sequence Study Runner

## Purpose

K9 runs an already-frozen K4 dataset through the existing M11 research stack
without re-preparing data or changing any sequence logic.

The path is:

    frozen K4 JSON
        |
        +--> K4 load + fingerprint verification
                |
                +--> K3 historical runner
                        |
                        +--> K1 sequence audit
                        +--> K2 forward outcomes
                        |
                        +--> existing JSON/CSV study bundle

K9 does not recompute K5 daily Evidence or K6 weekly directions. That work is
already frozen into the K4 dataset.

## Fingerprint gate

The K4 loader verifies the embedded prepared-input fingerprint before K3 runs.

K3 then receives the same embedded fingerprints as an external baseline, so a
mismatch fails closed rather than silently studying changed inputs.

## Review artifacts

The existing K3 bundle writer produces:

- daily_sequence_study_summary.json
- daily_sequence_input_fingerprints.json
- daily_sequence_input_fingerprints.csv
- daily_sequence_symbol_failures.csv
- daily_sequence_records.csv
- daily_sequence_outcomes.csv
- daily_sequence_signature_summaries.csv

All outputs remain explicitly non-actionable.

## CLI

For the first LT real-market case:

    python scripts/run_frozen_daily_sequence_study.py reports/daily-behavior-sequences/genuine/LT_NS.json

The CLI also prints weekly-direction assignment counts. This is diagnostic only;
it does not rebalance or reinterpret the production weekly authority frozen in
the dataset.

## First review objective

For LT, inspect:

- fresh sequence count;
- sequence signatures actually observed;
- outcome availability by 1/3/5/10/15 bars;
- favorable return, MFE, and MAE by signature;
- the all-bearish weekly-direction assignment characteristic reported by the
  frozen dataset.

No production promotion should follow from one symbol. This first case is a
pipeline and evidence-quality audit.
