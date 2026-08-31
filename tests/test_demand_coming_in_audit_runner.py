from pathlib import Path


def test_demand_coming_in_audit_runner_exists() -> None:
    path = Path(__file__).with_name("run_demand_coming_in_audit.py")
    assert path.is_file()


def test_demand_coming_in_audit_runner_has_required_horizons() -> None:
    source = Path(__file__).with_name("run_demand_coming_in_audit.py").read_text(encoding="utf-8")
    assert "horizons = (3, 5, 10)" in source


def test_demand_coming_in_audit_is_point_in_time() -> None:
    source = Path(__file__).with_name("run_demand_coming_in_audit.py").read_text(encoding="utf-8")
    assert "metrics.iloc[index]" in source
    assert "collect_demand_coming_in(ctx)" in source
    assert "index + horizon >= len(metrics)" in source
