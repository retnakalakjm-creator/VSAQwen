from evidence.demand import collect_demand
from evidence.demand_drying_up import collect_demand_drying_up


def test_demand_drying_up_is_not_in_production_demand_collector() -> None:
    """DDU remains audit-only until it is deliberately promoted."""
    assert "collect_demand_drying_up" not in collect_demand.__globals__
    assert collect_demand_drying_up.__name__ == "collect_demand_drying_up"
