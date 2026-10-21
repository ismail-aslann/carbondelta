"""Yıllık etki: günlük simulate() sonuçlarının toplamıyla birebir aynı olmalı."""
import csv

import pytest

from engine import annual, data
from engine.core import simulate


def _manual(asset, year, s, L, t, p, restricted=frozenset()):
    m = data.machine(asset)
    B = S = D = 0.0
    n = 0
    for d in data.days_for(asset):
        if not d.startswith(str(year)):
            continue
        load, ci = data.scenario_series(asset, d)
        r = simulate(load, ci, s, L, t, p, set(restricted), m["shiftable"])
        if r.status == "ok":
            B += r.baseline_kg
            S += r.scenario_kg
            D += r.daily_kg
            n += 1
    return B, S, D, n


@pytest.mark.parametrize("asset, s, L, t, p", [("comp_b", 3, 3, 18, 1.0), ("mh_a", 4, 2, 19, 0.5),
                                               ("u_e", 10, 1, 13, 0.25)])
def test_matches_daily_sum(asset, s, L, t, p):
    r = annual.annual_impact(asset, 2025, s, L, t, p)
    B, S, D, n = _manual(asset, 2025, s, L, t, p)
    assert r.days_ok == n and r.days_total == len(data.days_for(asset))
    assert r.baseline_kg == pytest.approx(B, rel=1e-12)
    assert r.scenario_kg == pytest.approx(S, rel=1e-12)
    assert r.delta_pct == pytest.approx((S - B) / B * 100)
    assert r.daily_delta_pct == pytest.approx((S - B) / D * 100)
    assert sum(m.days for m in r.months) == n
    assert sum(m.delta_kg for m in r.months) == pytest.approx(r.delta_kg)
    assert r.better_days + r.worse_days <= n
    assert sum(r.status_counts.values()) == r.days_total


def test_reference_scenario_reduces_emissions():
    r = annual.annual_impact("comp_b", 2025, 3, 3, 18, 1.0)
    assert r.delta_kg < 0 and r.better_days > r.worse_days
    assert r.best_day[1] <= r.delta_pct <= r.worst_day[1]


def test_restricted_target_and_non_shiftable():
    r = annual.annual_impact("comp_b", 2025, 3, 3, 18, 1.0, restricted={19})
    assert r.days_ok == 0 and r.status_counts == {"restricted_conflict": r.days_total}
    assert r.delta_pct is None and r.daily_delta_pct is None
    ns = annual.annual_impact("ex_a", 2025, 3, 3, 18, 1.0)
    assert ns.days_ok == 0 and set(ns.status_counts) == {"non_shiftable"}


def test_best_annual_target_is_minimum():
    best = annual.best_annual_target("comp_b", 2025, 3, 3, 1.0, restricted={20})
    assert best and all(not ({b.t, b.t + 1, b.t + 2} & {20}) for b in best)
    assert best[0].scenario_kg == min(b.scenario_kg for b in best)
    assert all(b.t + b.L <= 24 for b in best)


def test_years_for():
    assert annual.years_for("comp_b") == [2025]


def test_export_csv(tmp_path):
    from desktop.annual_tab import export_annual_csv
    r = annual.annual_impact("comp_b", 2025, 3, 3, 18, 1.0)
    path = tmp_path / "y.csv"
    export_annual_csv(path, r, {5})
    rows = list(csv.reader(path.open(encoding="utf-8-sig"), delimiter=";"))
    assert rows[0] == ["CarbonDelta yıllık etki"]
    flat = {row[0]: row[1] for row in rows if len(row) >= 2}
    assert float(flat["Yıllık değişim (kg)"].replace(",", ".")) == pytest.approx(r.delta_kg)
    assert "Örnek yük" in rows[-1][0]
