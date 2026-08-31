from confirmation_event_analysis import analyze_confirmation_events, render


def _rows() -> list[dict[str, str]]:
    return [
        {"change": "True->False", "confirmation_only_codes": "increasing_demand", "forward_return": "-0.10", "mfe": "0.02", "mae": "0.11"},
        {"change": "False->True", "confirmation_only_codes": "increasing_demand", "forward_return": "0.05", "mfe": "0.08", "mae": "0.01"},
        {"change": "False->True", "confirmation_only_codes": "selling_climax", "forward_return": "0.06", "mfe": "0.09", "mae": "0.01"},
    ]


def test_groups_confirmation_events_and_splits_actionability_changes() -> None:
    results = analyze_confirmation_events(_rows())

    increasing = next(item for item in results if item.code == "increasing_demand")
    assert increasing.cases == 2
    assert increasing.true_to_false == 1
    assert increasing.false_to_true == 1
    assert increasing.mean_return ==  -0.025
    assert increasing.mean_return_true_to_false == -0.10
    assert increasing.mean_return_false_to_true == 0.05

    climax = next(item for item in results if item.code == "selling_climax")
    assert climax.cases == 1
    assert climax.true_to_false == 0
    assert climax.false_to_true == 1


def test_render_contains_all_event_groups() -> None:
    text = render(analyze_confirmation_events(_rows()))
    assert "increasing_demand" in text
    assert "selling_climax" in text
    assert "T->F" in text
    assert "F->T" in text
