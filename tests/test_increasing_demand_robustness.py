from run_increasing_demand_robustness_audit import _unique_pairs, _bootstrap_delta


def test_unique_pairs_do_not_reuse_control_within_horizon() -> None:
    class P:
        def __init__(self, symbol, target_bar, control_bar, horizon, score_gap=0.0, pressure_gap=0.0, age_gap=0):
            self.target = type("T", (), {"symbol": symbol, "bar_index": target_bar, "horizon": horizon})()
            self.control = type("C", (), {"symbol": symbol, "bar_index": control_bar})()
            self.horizon = horizon
            self.score_gap = score_gap
            self.pressure_gap = pressure_gap
            self.age_gap = age_gap

    pairs = [P("A", 1, 10, 5), P("A", 2, 10, 5), P("A", 3, 10, 3)]
    result = _unique_pairs(pairs)
    assert len(result) == 2
    assert {p.horizon for p in result} == {3, 5}


def test_bootstrap_delta_is_deterministic() -> None:
    class P:
        def __init__(self, delta):
            self.target = type("T", (), {"forward_return": delta})()
            self.control = type("C", (), {"forward_return": 0.0})()

    pairs = [P(0.02), P(0.04), P(-0.01)]
    first = _bootstrap_delta(pairs, 500, 42)
    second = _bootstrap_delta(pairs, 500, 42)
    assert first == second
    assert first[0] == 0.016666666666666666
