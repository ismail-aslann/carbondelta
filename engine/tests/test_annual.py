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
    export_annual_csv(path, r, {5}, "tCO2")
    rows = list(csv.reader(path.open(encoding="utf-8-sig"), delimiter=";"))
    assert rows[0] == ["CarbonDelta yıllık etki"]
    flat = {row[0]: row[1] for row in rows if len(row) >= 2}
    assert float(flat["Yıllık değişim (kg CO2)"].replace(",", ".")) == pytest.approx(r.delta_kg)
    assert "Örnek yük" in rows[-1][0]
    assert any(row and row[0].startswith("Yenilenebilir payı") for row in rows)


def test_facility_is_sum_of_machines():
    f = annual.facility_impact(2025, 3, 3, 18, 1.0)
    ids = [m["id"] for m in data.machines() if m["shiftable"]]
    parts = [annual.annual_impact(a, 2025, 3, 3, 18, 1.0) for a in ids]
    assert f.is_facility and [x.asset_id for x in f.parts] == ids
    assert f.baseline_kg == pytest.approx(sum(x.baseline_kg for x in parts))
    assert f.delta_kg == pytest.approx(sum(x.delta_kg for x in parts))
    assert f.days_ok == sum(x.days_ok for x in parts)
    assert sum(m.delta_kg for m in f.months) == pytest.approx(f.delta_kg)
    assert annual.years_for(annual.ALL) == [2025]


def test_renewable_share_is_energy_weighted():
    r = annual.annual_impact("comp_b", 2025, 3, 3, 18, 1.0)
    src = tgt = e_tot = 0.0
    for d in data.days_for("comp_b"):
        load, ci = data.scenario_series("comp_b", d)
        if simulate(load, ci, 3, 3, 18, 1.0).status != "ok":
            continue
        for i in range(3):
            e = load[3 + i]
            e_tot += e
            src += e * data.mix_at(d, 3 + i)["renewable_pct"]
            tgt += e * data.mix_at(d, 18 + i)["renewable_pct"]
    assert r.ren_source_pct == pytest.approx(src / e_tot)
    assert r.ren_target_pct == pytest.approx(tgt / e_tot)
    assert r.ren_target_pct > r.ren_source_pct


def test_parametric_uses_constant_load():
    series = annual.year_series("comp_b", 2025, "tCO2", parametric_kwh=10.0)
    r = annual.annual_impact("comp_b", 2025, 3, 3, 18, 1.0, series=series)
    assert r.days_ok == len(series)                        # sabit yükte "yük yok" günü olmaz
    assert r.shifted_kwh == pytest.approx(10.0 * 3 * len(series))


def test_annual_explain_request_and_validator():
    from desktop import ai_context
    from desktop.ai_client import allowed_numbers, validate_numbers
    f = annual.facility_impact(2025, 3, 3, 18, 1.0)
    req = ai_context.annual_explain(f, f)
    assert req.func_id == "annual_explain" and "makine_katkilari" in req.payload
    text = req.fallback()
    assert "makine-günde" in text and "18:00–21:00" in text
    assert validate_numbers(text, allowed_numbers([req.payload]))   # şablon metin kendi doğrulayıcısından geçer
    assert ai_context.annual_explain(annual.annual_impact("comp_b", 2025, 3, 3, 18, 1.0, restricted={19}), None) is None


def test_units_follow_emission_type():
    from desktop.annual_tab import mass
    assert mass(-1500, "tCO2esd").endswith("t CO2-eşd") and mass(-15, "tCO2").endswith("kg CO2")


def test_pdf_report(tmp_path):
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])  # noqa: F841
    from desktop.annual_tab import annual_report_html, chart_png, export_annual_pdf
    f = annual.facility_impact(2025, 3, 3, 18, 1.0)
    path = tmp_path / "r.pdf"
    export_annual_pdf(path, f, f, {5}, "tCO2", None, chart_png(f.months), "Deneme yorumu", "ai")
    assert path.read_bytes()[:5] == b"%PDF-" and path.stat().st_size > 20_000
    h = annual_report_html(f, f, set(), "tCO2", 10.0, "", "")
    assert "Makine katkıları" in h and "Parametrik mod" in h and "Yöntem ve sınırlılıklar" in h
