import pytest

from engine import data
from engine.core import simulate


def test_comp_b_reference():
    load = data.load_24("comp_b", "2025-07-15")
    ci = data.ci_24("2025-07-15", "tCO2")
    r = simulate(load, ci, s=3, L=3, t=18, p=1.0)
    assert r.status == "ok"
    assert r.baseline_kg == pytest.approx(42.613384, abs=1e-4)
    assert r.scenario_kg == pytest.approx(35.957618, abs=1e-4)
    assert r.delta_pct == pytest.approx(-15.6190, abs=1e-4)
    assert r.daily_delta_pct == pytest.approx(-2.1542, abs=1e-4)


def test_data_layer_shapes():
    ms = data.machines()
    assert len(ms) == 7
    shiftable = {m["id"]: m["shiftable"] for m in ms}
    assert shiftable["ex_a"] is False and shiftable["php_c"] is False
    days = data.days_for("comp_b")
    assert days[0] == "2025-05-23" and "2025-07-15" in days
    assert len(data.ci_24("2025-07-15", "tCO2esd")) == 24
    mix = data.mix_at("2025-07-15", 18)
    assert mix["dominant"]
    assert sum(mix["shares"].values()) == pytest.approx(100.0, abs=0.01)


def test_unknown_day_raises():
    with pytest.raises(KeyError):
        data.load_24("php_c", "2025-01-01")
