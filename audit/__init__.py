"""Analysis-only audit utilities for ProVSA.

Modules in this package must not mutate production scanner decisions. They are
for historical validation, calibration research, and reporting only.

Available modules:

- ``audit.outcomes``: next-bar-execution forward outcome calculations.
- ``audit.candidates``: flat candidate outcome dataset generation.
"""
