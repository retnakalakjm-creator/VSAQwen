from __future__ import annotations

from types import SimpleNamespace

from tests.changed_actionability_report import ChangedActionabilityCase, summarize_cases


def _case(*, baseline_actionable: bool, masked_actionable: bool, forward_return: float) -> ChangedActionabilityCase:
    outcome = SimpleNamespace(
        complete=True,
        forward_return=forward_return,
        maximum_favorable_excursion=0.04,
        maximum_adverse_excursion=0.02,
    )
    baseline = SimpleNamespace(actionable=baseline_actionable, base_score=1.0, net_pressure=0.2)
    masked = SimpleNamespace(actionable=masked_actionable, base_score=0.9, net_pressure=0.1)
    return ChangedActionabilityCase(
        bar_index=10,
        baseline=baseline,
        masked=masked,
        outcome=outcome,
        confirmation_only_codes=("shakeout",),
    )


def test_summary_separates_removed_and_added_actionability() -> None:
    summary = summarize_cases(
        [
            _case(baseline_actionable=True, masked_actionable=False, forward_return=0.03),
            _case(baseline_actionable=False, masked_actionable=True, forward_return=-0.01),
        ]
    )

    assert summary["cases"] == 2
    assert summary["complete"] == 2
    assert summary["confirmation_removed_actionability"] == 1
    assert summary["confirmation_added_actionability"] == 1
    assert summary["removed_mean_forward_return"] == 0.03
    assert summary["added_mean_forward_return"] == -0.01


def test_incomplete_cases_are_excluded() -> None:
    case = _case(baseline_actionable=True, masked_actionable=False, forward_return=0.03)
    incomplete = ChangedActionabilityCase(
        bar_index=11,
        baseline=case.baseline,
        masked=case.masked,
        outcome=SimpleNamespace(
            complete=False,
            forward_return=None,
            maximum_favorable_excursion=None,
            maximum_adverse_excursion=None,
        ),
        confirmation_only_codes=("shakeout",),
    )

    summary = summarize_cases([case, incomplete])

    assert summary["cases"] == 2
    assert summary["complete"] == 1
    assert summary["confirmation_removed_actionability"] == 1
