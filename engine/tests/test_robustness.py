"""Tarama sonrası düzeltmelerin testleri: saat altı veri, bozuk paket, golden yalıtımı, kural çözümleyici."""
import os

import pytest

from engine import data
from engine import packages as pk


@pytest.fixture
def pkg_dir(tmp_path, monkeypatch):
    d = tmp_path / "veri"
    monkeypatch.setenv("CARBONDELTA_DATA_DIR", str(d))
    data.reload()
    yield d
    monkeypatch.setenv("CARBONDELTA_DATA_DIR", os.environ["CARBONDELTA_TEST_EMPTY_DIR"])
    data.reload()


def _write(path, rows):
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


@pytest.mark.parametrize("step", [15, 30])
def test_subhourly_energy_is_summed(pkg_dir, tmp_path, step):
    rows = ["Tarih;Saat;kWh"]
    for h in range(24):
        for m in range(0, 60, step):
            rows.append(f"2025-07-15;{h:02d}:{m:02d};{step / 60:.2f}".replace(".", ","))
    _write(tmp_path / "q.csv", rows)
    c = pk.check_machine_file(tmp_path / "q.csv", set(data.all_dates()))
    assert not c.report.has_errors, c.report.lines
    assert c.days == ["2025-07-15"]
    assert c.frame["Saatlik_Tuketim_kWh"].tolist() == pytest.approx([1.0] * 24)
    assert any(f"{step} dakikalık" in t for _, t in c.report.lines)


def test_subhourly_incomplete_hour_skips_day(pkg_dir, tmp_path):
    rows = ["Tarih;Saat;kWh"]
    for d in ("2025-07-14", "2025-07-15"):
        for h in range(24):
            for m in (0, 15, 30, 45):
                if d == "2025-07-14" and h == 5 and m == 30:
                    continue
                rows.append(f"{d};{h:02d}:{m:02d};1")
    _write(tmp_path / "q.csv", rows)
    c = pk.check_machine_file(tmp_path / "q.csv", set(data.all_dates()))
    assert c.days == ["2025-07-15"]


def test_power_column_hourly_mean(pkg_dir, tmp_path):
    rows = ["Tarih;Saat;Güç (kW)"]
    for h in range(24):
        for m, v in ((0, 10), (15, 20), (30, 30), (45, 40)):
            rows.append(f"15.07.2025 ;{h:02d}:{m:02d};{v}")
    _write(tmp_path / "p.csv", rows)
    c = pk.check_machine_file(tmp_path / "p.csv", set(data.all_dates()))
    assert not c.report.has_errors, c.report.lines
    assert c.frame["Saatlik_Tuketim_kWh"].tolist() == pytest.approx([25.0] * 24)  # ortalama güç


def test_dotted_date_without_time_is_hourly(pkg_dir, tmp_path):
    rows = ["Tarih;Saat;kWh"] + [f"15.07.2025;{h};2" for h in range(24)]
    _write(tmp_path / "d.csv", rows)
    c = pk.check_machine_file(tmp_path / "d.csv", set(data.all_dates()))
    assert c.days == ["2025-07-15"] and not any("dakikalık" in t for _, t in c.report.lines)


def test_broken_packages_do_not_stop_loading(pkg_dir):
    bad = pkg_dir / "machine-bozuk"
    bad.mkdir(parents=True)
    (bad / "manifest.json").write_text('{"id":"machine-bozuk","kind":"machine","name":"Bozuk","enabled":true}',
                                       encoding="utf-8")
    (bad / "machines.json").write_text("[{bozuk", encoding="utf-8")
    worse = pkg_dir / "manifest-yok"
    worse.mkdir()
    (worse / "manifest.json").write_text("{bozuk", encoding="utf-8")
    data.reload()                                  # hata fırlatmamalı
    assert len(data.machines()) == 7               # varsayılan makineler duruyor
    errs = data.package_errors()
    assert "machine-bozuk" in errs and "manifest-yok" in errs
    pk.delete_package("manifest-yok")              # bozuk paket silinebilir
    assert not worse.exists()


def test_make_golden_refuses_user_packages(pkg_dir, tmp_path):
    _write(tmp_path / "m.csv", ["Tarih;Saat;kWh"] + [f"2025-07-15;{h};5" for h in range(24)])
    c = pk.check_machine_file(tmp_path / "m.csv", set(data.all_dates()))
    pk.add_machine_package(c, "Deneme", "x", True, "real")
    data.reload()
    from engine import make_golden
    with pytest.raises(RuntimeError):
        make_golden.build_vectors()


def test_rule_parser_knows_user_machines(pkg_dir, tmp_path):
    _write(tmp_path / "m.csv", ["Tarih;Saat;kWh"] + [f"2025-07-15;{h};5" for h in range(24)])
    c = pk.check_machine_file(tmp_path / "m.csv", set(data.all_dates()))
    p = pk.add_machine_package(c, "Kompresör (Hat 2)", "Basınçlı hava", True, "real")
    data.reload()
    new_id = next(m["id"] for m in data.machines() if m.get("package") == p.id)
    from desktop.ai_context import parse_nl_rule
    got = parse_nl_rule("Kompresör (Hat 2)'yi 3'ten 18'e al")
    assert got["asset_id"] == new_id and got["s"] == 3 and got["t"] == 18   # "Hat 2"deki 2 saat sanılmaz
    assert parse_nl_rule("Kompresörü 3'ten 18'e al")["asset_id"] == "comp_b"


def test_zero_ratio_message_names_the_ratio():
    from desktop.main_window import status_message
    from engine.core import simulate
    load, ci = data.scenario_series("p_i", "2025-07-15")
    r = simulate(load, ci, 3, 3, 19, 0.0)
    assert r.status == "no_load"
    assert "oranı %0" in status_message(r, set(), 0.0)
    assert "yük yok" in status_message(r, set(), 1.0)


def test_sources_follow_packages(pkg_dir, tmp_path):
    from desktop.tabs import note_html, packages_html, source_cards
    assert "Henüz veri eklenmedi" in packages_html()
    _write(tmp_path / "m.csv", ["Tarih;Saat;kWh"] + [f"2025-07-15;{h};5" for h in range(24)])
    c = pk.check_machine_file(tmp_path / "m.csv", set(data.all_dates()))
    p = pk.add_machine_package(c, "Hat 3 Kompresör", "x", True, "real")
    data.reload()
    cards = source_cards()
    assert "Makine yükleri" == cards[2][0] and "Hat 3 Kompresör" in cards[2][2] and "8 makine" in cards[2][1]
    assert "Hat 3 Kompresör" in packages_html() and "Etkin" in packages_html()
    assert "birlikte" in note_html() and "Tesis ölçümü ve örnek yük" in data.overall_source_label()
    pk.set_enabled(p.id, False)
    data.reload()
    assert "Kapalı" in packages_html() and "Hat 3" not in source_cards()[2][2]
    pk.delete_package(p.id)
    data.reload()
    assert "Henüz veri eklenmedi" in packages_html() and source_cards()[2][0] == data.SAMPLE_SOURCE


@pytest.mark.parametrize("s, L, t, p", [(3, 3, 18, 1.0), (3, 3, 18, 0.5), (3, 3, 4, 1.0), (18, 3, 3, 0.25)])
def test_chart_draws_shifted_energy(s, L, t, p):
    import os as _os
    _os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])  # noqa: F841
    from desktop.chart_widget import ChartWidget
    load, ci = data.scenario_series("comp_b", "2025-07-15")
    ch = ChartWidget()
    ch.update_chart(ci, load, s, L, t, set(), "ok", -1.0, "tCO2", p)
    moved = p * sum(load[s:s + L])
    assert sum(ch._out) == pytest.approx(moved) and sum(ch._in) == pytest.approx(moved)
    assert all(ch._in[h] == 0 for h in range(24) if not t <= h < t + L)
    ch.update_chart(ci, load, s, L, t, set(), "ok", -1.0, "tCO2", 0.0)
    assert sum(ch._in) == 0                       # oran %0: grafikte taşıma yok
