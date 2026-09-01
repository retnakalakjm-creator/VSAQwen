from __future__ import annotations

import inspect

from evidence.demand_drying_up import collect_demand_drying_up
from evidence.profiles import EVIDENCE_REGISTRY
from models import EvidenceCode
import tests.run_demand_drying_up_audit as runner


def test_demand_drying_up_is_registered_as_audit_only() -> None:
    profile = EVIDENCE_REGISTRY[EvidenceCode.DEMAND_DRYING_UP]
    assert profile.weight == 0.0
    assert profile.direction.name == "BEARISH"


def test_audit_runner_uses_point_in_time_detector() -> None:
    source = inspect.getsource(runner._audit_symbol)
    assert "collect_demand_drying_up(ctx)" in source
    assert "metrics.iloc[:" not in source
    assert "metrics.iloc[index + horizon" not in source
    assert "label_outcome" in source


def test_detector_is_the_expected_callable() -> None:
    assert callable(collect_demand_drying_up)
