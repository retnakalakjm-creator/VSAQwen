from __future__ import annotations

from types import SimpleNamespace

from evidence.evidence_registry import build_evidence
from model.evidence_result_model import EvidenceResult
from models import EvidenceCode
from scanner import ScannerEngine


def test_fallback_scoring_does_not_use_vsa_before_qualification_boundary() -> None:
    scanner = ScannerEngine()
    current = EvidenceResult(
        context=None,
        evidence=(
            build_evidence(
                EvidenceCode.DEMAND_COMING_IN,
                bar_index=14,
                week_beginning="2025-01-14",
            ),
        ),
    )
    qualifying_evidence = (SimpleNamespace(bar_index=15),)

    scoring = scanner._scoring_evidence(
        current,
        bar_index=20,
        qualifying_evidence=qualifying_evidence,
    )

    assert scoring == ()


def test_fallback_scoring_does_not_cross_ten_bar_lookback() -> None:
    scanner = ScannerEngine()
    current = EvidenceResult(
        context=None,
        evidence=(
            build_evidence(
                EvidenceCode.DEMAND_COMING_IN,
                bar_index=19,
                week_beginning="2025-01-19",
            ),
            build_evidence(
                EvidenceCode.NO_SUPPLY,
                bar_index=20,
                week_beginning="2025-01-20",
            ),
        ),
    )

    scoring = scanner._scoring_evidence(current, bar_index=30)

    assert {item.bar_index for item in scoring} == {20}


def test_fallback_scoring_uses_latest_vsa_bar_inside_window() -> None:
    scanner = ScannerEngine()
    current = EvidenceResult(
        context=None,
        evidence=(
            build_evidence(
                EvidenceCode.DEMAND_COMING_IN,
                bar_index=21,
                week_beginning="2025-01-21",
            ),
            build_evidence(
                EvidenceCode.NO_SUPPLY,
                bar_index=24,
                week_beginning="2025-01-24",
            ),
        ),
    )

    scoring = scanner._scoring_evidence(current, bar_index=30)

    assert {item.bar_index for item in scoring} == {24}
