from __future__ import annotations

from pathlib import Path

from evidence.effort import collect_effort
from evidence.high_volume_reversal import HIGH_VOLUME_REVERSAL_CODE
from model.evidence_result_model import EvidenceResult
from models import ClosePosition, Direction, SpreadClass, VolumeClass
from scanner import ScannerEngine


EFFORT_PATH = Path("evidence/effort.py")
FRONTEND_PATH = Path("frontend/app/bar-by-bar-panel.tsx")
HVR_DOC_PATH = Path("docs/HIGH_VOLUME_REVERSAL_READONLY_EVIDENCE.md")


def _hvr_like_context():
    from types import SimpleNamespace

    current = SimpleNamespace(
        direction=Direction.DOWN,
        volume=VolumeClass.HIGH,
        spread=SpreadClass.ABOVE_AVERAGE,
        close_position=ClosePosition.UPPER,
        close_ratio=0.62,
        low=90.0,
        bar_index=42,
        week_beginning="2026-01-05",
    )
    previous = SimpleNamespace(
        direction=Direction.DOWN,
        volume=VolumeClass.AVERAGE,
        spread=SpreadClass.AVERAGE,
        close_position=ClosePosition.LOWER,
        close_ratio=0.25,
        low=100.0,
        bar_index=41,
        week_beginning="2025-12-29",
    )
    return SimpleNamespace(current=current, previous=previous)


def test_high_volume_reversal_is_not_collected_in_production_effort_path() -> None:
    evidence = collect_effort(_hvr_like_context())

    assert HIGH_VOLUME_REVERSAL_CODE not in {item.code for item in evidence}


def test_effort_collector_documents_hvr_hold_boundary() -> None:
    source = EFFORT_PATH.read_text(encoding="utf-8")

    assert "collect_high_volume_reversal" not in source
    assert "High Volume Reversal is intentionally not collected here" in source
    assert "A single bar is not enough to define reversal" in source


def test_high_volume_reversal_is_not_frontend_visible_detector_code() -> None:
    source = FRONTEND_PATH.read_text(encoding="utf-8")

    assert "high_volume_reversal" not in source
    assert "High Volume Reversal" not in source
    assert "No Effort/Result or Absorption event" in source


def test_high_volume_reversal_hold_doc_is_explicit() -> None:
    source = HVR_DOC_PATH.read_text(encoding="utf-8")

    assert "High Volume Reversal is on hold" in source
    assert "not collected as production-visible evidence" in source
    assert "A reversal cannot be reliably defined by a single bar" in source
    assert "multi-bar rule" in source


def test_hvr_code_remains_excluded_from_scoring_if_historical_payload_exists() -> None:
    result = EvidenceResult(context=object(), evidence=())

    assert ScannerEngine._scoring_evidence(result, 42) == ()