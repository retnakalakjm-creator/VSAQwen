from types import SimpleNamespace

import config
import evidence.demand as demand
from evidence.campaign import ShakeoutRecoveryResult, ShakeoutTestResult
from models import EvidenceCode


def _ctx(index: int = 1083) -> SimpleNamespace:
    return SimpleNamespace(
        current=SimpleNamespace(bar_index=index),
        previous=SimpleNamespace(),
    )


def _validation(recovery_index: int = 1083, test_index: int = 1081) -> SimpleNamespace:
    return SimpleNamespace(
        test=SimpleNamespace(
            result=ShakeoutTestResult.VALID,
            test_index=test_index,
        ),
        recovery=SimpleNamespace(
            result=ShakeoutRecoveryResult.VALID,
            recovery_index=recovery_index,
        ),
    )


def test_shakeout_evidence_is_anchored_to_recovery_bar(monkeypatch) -> None:
    ctx = _ctx(1083)
    validation = _validation(1083, 1081)
    captured = []

    monkeypatch.setattr(
        demand,
        "_find_recovery_anchored_shakeout",
        lambda *, ctx, validation_metrics: (
            (SimpleNamespace(passed=True),),
            validation,
        ),
    )
    monkeypatch.setattr(
        demand,
        "calculate_shakeout_quality",
        lambda *, validation: 0.80,
    )

    def fake_evaluate_detector(**kwargs):
        captured.append(kwargs)

    monkeypatch.setattr(demand, "evaluate_detector", fake_evaluate_detector)

    result = demand._collect_shakeout(ctx, SimpleNamespace())

    assert result == []
    assert len(captured) == 1
    assert captured[0]["code"] == EvidenceCode.SHAKEOUT
    assert captured[0]["ctx"] is ctx
    assert captured[0]["test_index"] == 1081
    assert captured[0]["recovery_index"] == 1083
    assert captured[0]["quality"] == 0.80


def test_shakeout_production_weight_is_050() -> None:
    assert config.DEMAND_EVIDENCE_WEIGHTS[EvidenceCode.SHAKEOUT] == 0.50
