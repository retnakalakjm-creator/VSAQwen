from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Historical audit/analysis scripts are intentionally kept out of the default
# pytest path. They are useful research artifacts, but they are not fast,
# deterministic regression tests. Run them explicitly by filename when needed.
collect_ignore_glob = [
    "benchmark_*.py",
    "debug_*.py",
    "profile_*.py",
    "run_*.py",
    "*_analysis.py",
    "*_audit.py",
    "*_counterfactual.py",
    "*_harness.py",
    "*_report.py",
    "*_robustness.py",
]
