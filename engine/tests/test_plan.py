"""Tesis günlük planı ve fosil marjinal duyarlılık."""
import pytest

from engine import data, plan
from engine.best_window import best_window
from engine.core import simulate
from engine.insights import fossil_sensitivity

DAY = "2025-07-15"


def test_ci_fossil_is_ci_over_fossil_share():
    ci, cif = data.ci_24(DAY), data.ci_fossil_24(DAY)
    for h in range(24):
        frac = data.mix_at(DAY, h)["fossil_pct"] / 100
        assert cif[h] == pytest.approx(ci[h] / frac)
        assert cif[h] >= ci[h]


def test_fossil_sensitivity_reference():
    load, _ = data.scenario_series("comp_b", DAY)
    b, s, pct = fossil_sensitivity(load, data.ci_fossil_24(DAY), 3, 3, 18, 1.0)
    r = simulate(load, data.ci_fossil_24(DAY), 3, 3, 18, 1.0)
    assert (b, s) == pytest.approx((r.baseline_kg, r.scenario_kg))
    assert pct == pytest.approx(r.delta_pct) and -15.62 < pct < 0     # ana sonuçtan daha temkinli


def test_plan_without_limit_picks_each_machines_best_window():
    p = plan.facility_plan(DAY, plan.default_settings(3, 3, 1.0))
    for row in p.rows:
        m = data.machine(row.asset_id)
        if row.status == plan.PLANNED:
            load = data.load_24(row.asset_id, DAY)
            t, r = best_window(load, data.ci_24(DAY), 3, 3, 1.0)
            assert row.t == t and row.result.scenario_kg == pytest.approx(r.scenario_kg)
        if not m["shiftable"] and DAY in m["days"]:
            assert row.status == plan.NON_SHIFTABLE
    assert p.planned_count >= 3 and p.delta_kg < 0
    assert sum(p.before) == pytest.approx(sum(p.after))                  # enerji korunur
    assert p.delta_kg == pytest.approx(sum(r.delta_kg for r in p.rows if r.status in (plan.PLANNED, plan.KEEP)))


def test_peak_limit_is_respected():
    free = plan.facility_plan(DAY, plan.default_settings(3, 3, 1.0))
    assert free.peak_after > free.peak_before                           # hepsi aynı saate toplanınca tepe artar
    lim = plan.facility_plan(DAY, plan.default_settings(3, 3, 1.0), peak_limit=free.peak_before)
    assert lim.peak_after <= free.peak_before + 1e-9
    assert free.delta_kg <= lim.delta_kg < 0                            # sınır azaltımı küçültür ama sıfırlamaz


def test_restricted_and_excluded():
    st = plan.default_settings(3, 3, 1.0)
    st["comp_b"].include = False
    p = plan.facility_plan(DAY, st, restricted={18, 19, 20})
    rows = {r.asset_id: r for r in p.rows}
    assert rows["comp_b"].status == plan.EXCLUDED
    for r in p.rows:
        if r.status == plan.PLANNED:
            assert not {r.t + i for i in range(r.L)} & {18, 19, 20}


def test_plan_csv(tmp_path):
    from desktop.plan_tab import export_plan_csv
    p = plan.facility_plan(DAY, plan.default_settings(3, 3, 1.0), peak_limit=80)
    path = tmp_path / "p.csv"
    export_plan_csv(path, p, {5})
    text = path.read_text(encoding="utf-8-sig")
    assert "Tepe yük sonra" in text and "Kompresör" in text


def test_auto_standard_window_is_heaviest():
    p = plan.facility_plan("2025-09-01", plan.default_settings(None, 3, 1.0))
    ci = data.ci_24("2025-09-01")
    for r in p.rows:
        if r.status in (plan.PLANNED, plan.KEEP):
            load = data.load_24(r.asset_id, "2025-09-01")
            emissions = [sum(load[s + i] * ci[s + i] for i in range(3)) for s in range(22)]
            assert r.s == max(range(22), key=lambda s: (emissions[s], -s))
    assert p.planned_count >= 3 and p.shifted_kwh > 50


def test_reason_counts_when_nothing_moves():
    st = plan.default_settings(3, 3, 1.0)
    p = plan.facility_plan(DAY, st, restricted=set(range(24)) - {3, 4, 5})   # tek geçerli hedef standardın kendisi
    assert p.planned_count == 0
    assert sum(plan.reason_counts(p).values()) >= 3
