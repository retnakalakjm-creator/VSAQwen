"""Analysis-only audit utilities for ProVSA.

Modules in this package must not mutate production scanner decisions. They are
for historical validation, calibration research, and reporting only.

Available modules:

- ``audit.outcomes``: next-bar-execution forward outcome calculations.
- ``audit.candidates``: flat candidate outcome dataset generation.
- ``audit.calibration``: grouped outcome summaries for evidence calibration.
- ``audit.reports``: CSV report bundle exports for calibration review.
- ``audit.runner``: historical full-replay scanner audit orchestration.
- ``audit.stability``: confidence-aware calibration stability diagnostics.
- ``audit.vsa_events``: VSA event causality contract catalog.
"""
