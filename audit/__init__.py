"""Analysis-only audit utilities for ProVSA.

Modules in this package must not mutate production scanner decisions. They are
for historical validation, calibration research, and reporting only.

Available modules:

- ``audit.outcomes``: next-bar-execution forward outcome calculations.
- ``audit.candidates``: flat candidate outcome dataset generation.
- ``audit.calibration``: grouped outcome summaries for evidence calibration.
- ``audit.reports``: CSV report bundle exports for calibration review.
- ``audit.runner``: historical full-replay scanner audit orchestration.
- ``audit.weekly_foundation_runner``: WF1-WF6 historical study execution and export.
- ``audit.weekly_actionability_counterfactual_runner``: WF7A legacy-actionability contradiction counterfactual execution and export.
- ``audit.weekly_contradiction_reason_runner``: WF7B contradiction-reason and episode decomposition execution and export.
- ``audit.weekly_input_reproducibility_runner``: WF7C0 exact completed-week input fingerprint capture and export.
- ``audit.weekly_opposite_supported_thesis_runner``: WF7C1 reproducibility-gated opposite-supported-thesis decomposition and matched-control export.
- ``audit.stability``: confidence-aware calibration stability diagnostics.
- ``audit.vsa_events``: VSA event causality contract catalog.
- ``audit.vsa_event_diagnostics``: VSA event outcome diagnostic summaries.
- ``audit.proposals``: reviewable Milestone 4 calibration proposal tables.
"""
