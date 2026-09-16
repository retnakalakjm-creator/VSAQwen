from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_SCANNER = ROOT / "production_scanner.py"
CLOSURE_DOC = ROOT / "docs" / "PRODUCTION_TRANSITION_CLOSURE.md"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _import_modules(source: str) -> set[str]:
    tree = ast.parse(source)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_production_scanner_has_no_direct_incremental_engine_dependency() -> None:
    source = _source(PRODUCTION_SCANNER)
    imports = _import_modules(source)

    assert "incremental_scanner" not in imports
    assert "IncrementalScannerEngine" not in source


def test_production_scanner_uses_all_transition_boundaries() -> None:
    source = _source(PRODUCTION_SCANNER)
    imports = _import_modules(source)

    assert "historical_scanner" in imports
    assert "scanner_transition" not in imports
    assert "scanner_transition_resume" in imports
    assert "scanner_transition_snapshot" in imports
    assert "HistoricalScannerRunner().scan_to_index(metrics, target_index)" in source
    assert "scan_to_index_with_state" in source
    assert "snapshot_from_transition_state(" in source
    assert "transition_resume = ScannerTransitionResumeAdapter()" in source
    assert "transition_snapshot = ScannerTransitionSnapshotAdapter()" in source
    assert "snapshot.snapshot(" in source
    assert "transition_resume.resume_latest(metrics, state)" in source


def test_transition_boundary_docs_do_not_describe_old_pre_production_phase() -> None:
    combined_source = "\n".join(
        _source(ROOT / path)
        for path in (
            "historical_scanner.py",
            "scanner_transition_resume.py",
            "scanner_transition_snapshot.py",
        )
    )

    assert "without wiring the production scanner" not in combined_source
    assert "Phase 4 guardrail surface only" not in combined_source
    assert "before the production resume path is routed" not in combined_source


def test_closure_doc_lists_final_transition_boundaries_and_non_goals() -> None:
    doc = _source(CLOSURE_DOC)

    for phrase in (
        "Full replay/bootstrap/fallback candidate and snapshot creation",
        "HistoricalScannerRunner",
        "Validated checkpoint resume",
        "Snapshot creation and refresh",
        "ScannerTransitionResumeAdapter",
        "ScannerTransitionSnapshotAdapter",
        "snapshot_from_transition_state",
        "does not import `scanner_transition` directly",
        "IncrementalScannerEngine is no longer a production_scanner dependency",
        "No detector logic",
        "No scoring, ranking, qualification, or actionability changes",
        "No frontend, API, replay/manual-review, HVR, stopping-volume, or climactic-action changes",
    ):
        assert phrase in doc
