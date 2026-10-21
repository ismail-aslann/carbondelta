"""Veri paketleri: makine, yıl (EPİAŞ) ve emisyon katsayısı içe aktarma."""
import os
from pathlib import Path

import pandas as pd
import pytest

from engine import data
from engine import packages as pk
from engine.core import simulate


@pytest.fixture
def pkg_dir(tmp_path, monkeypatch):
    d = tmp_path / "veri"
    monkeypatch.setenv("CARBONDELTA_DATA_DIR", str(d))
    data.reload()
    yield d
    monkeypatch.setenv("CARBONDELTA_DATA_DIR", os.environ["CARBONDELTA_TEST_EMPTY_DIR"])
    data.reload()


def test_parse_helpers():
    assert pk.parse_num("1.234,56") == 1234.56
    assert pk.parse_num("12,40") == 12.4
    assert pk.parse_num(",01") == 0.01
    assert pk.parse_num("-,05") == -0.05
    assert pk.parse_num("12.4") == 12.4
    assert pk.parse_num("") != pk.parse_num("")  # NaN
    assert pk.parse_date("01.03.2026") == "2026-03-01"
    assert pk.parse_date("2026-03-01 00:00:00") == "2026-03-01"
    assert pk.parse_hour("03:00") == 3 and pk.parse_hour("23") == 23
    assert pk.source_key("Doğal Gaz (MWh)") == "Dogal_Gaz"
    assert pk.source_key("Taş Kömürü") == "Tas_Komur"
    assert pk.source_key("Dogal_Gaz_Pay_Yuzde") == "Dogal_Gaz"


def test_base_label_unchanged():
    assert data.source_label("comp_b", "2025-07-15") == \
        "Örnek yük, Balıkesir tesisi değil · Kaynak: EPİAŞ 2025, ETKB 2023, Zenodo"


def _machine_csv(path: Path, days: list[str], break_day: str | None = None) -> None:
    rows = ["Tarih;Saat;kWh"]
    for d in days:
        dd = f"{d[8:10]}.{d[5:7]}.{d[:4]}"
        for h in range(24):
            if d == break_day and h == 5:
                continue
            rows.append(f"{dd};{h:02d}:00;{10 + h},5")
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def test_machine_import_and_simulate(pkg_dir, tmp_path):
    f = tmp_path / "m.csv"
    _machine_csv(f, ["2025-07-14", "2025-07-15", "2025-07-16", "2030-01-01"], break_day="2025-07-16")
    check = pk.check_machine_file(f, set(data.all_dates()))
    assert not check.report.has_errors
    assert check.days == ["2025-07-14", "2025-07-15"]          # eksik saatli gün ve şebekesiz gün atlandı
    levels = [lvl for lvl, _ in check.report.lines]
    assert levels.count("warn") == 2
    p = pk.add_machine_package(check, "Kompresör (Hat 2)", "Basınçlı hava", True, "real")
    data.reload()
    m = data.machine(next(x["id"] for x in data.machines() if x.get("package") == p.id))
    assert m["name"] == "Kompresör (Hat 2)" and m["days"] == check.days
    load, ci = data.scenario_series(m["id"], "2025-07-15")
    assert load[3] == 13.5
    r = simulate(load, ci, 3, 3, 18, 1.0, shiftable=m["shiftable"])
    assert r.status == "ok"
    assert data.source_label(m["id"], "2025-07-15").startswith("Tesis ölçümü (Balıkesir)")
    pk.set_enabled(p.id, False)
    data.reload()
    assert not data.has_machine(m["id"])


def test_machine_import_rejects_bad_file(pkg_dir, tmp_path):
    f = tmp_path / "bad.csv"
    f.write_text("a;b\n1;2\n", encoding="utf-8")
    assert pk.check_machine_file(f, set(data.all_dates())).report.has_errors


def _grid_csv_from_base(path: Path, year: int, days: int = 3) -> list[str]:
    """2025 kaynak paylarından (shared/assets, git'te) EPİAŞ dışa aktarım biçiminde (Türkçe başlıklar,
    ondalık virgül) bir dosya üretir. Pay × 333,3 MWh üretim, aynı oranları korur."""
    raw = pd.read_csv(Path(__file__).resolve().parents[2] / "shared" / "assets" / "epias_2025.csv",
                      dtype=str)
    raw = raw[raw["Tarih"].isin(sorted(raw["Tarih"].unique())[:days])]
    names = {"Dogal_Gaz": "Doğal Gaz", "Barajli": "Barajlı", "Linyit": "Linyit", "Akarsu": "Akarsu",
             "Ithal_Komur": "İthal Kömür", "Ruzgar": "Rüzgar", "Gunes": "Güneş", "Fuel_Oil": "Fuel Oil",
             "Jeotermal": "Jeotermal", "Asfaltit_Komur": "Asfaltit Kömür", "Tas_Komur": "Taş Kömür",
             "Biyokutle": "Biyokütle", "Atik_Isi": "Atık Isı"}
    out = pd.DataFrame({"Tarih": [f"{d[8:10]}.{d[5:7]}.{year}" for d in raw["Tarih"]],
                        "Saat": [f"{int(h):02d}:00" for h in raw["Saat_No"]]})
    for s, n in names.items():
        out[n] = [f"{float(v) * 333.3:.4f}".replace(".", ",") for v in raw[f"{s}_Pay_Yuzde"]]
    out.to_csv(path, sep=";", index=False)
    return sorted({f"{year}-{d[5:7]}-{d[8:10]}" for d in raw["Tarih"]}), raw


def test_grid_import_matches_base_method(pkg_dir, tmp_path):
    f = tmp_path / "epias2026.csv"
    days, raw = _grid_csv_from_base(f, 2026)
    check = pk.check_grid_file(f, data.factors(), set(data.all_dates()))
    assert not check.report.has_errors, check.report.lines
    assert check.days == days and check.years == [2026]
    p = pk.add_grid_package(check, "EPİAŞ 2026")
    data.reload()
    for d26 in days:
        d25 = "2025" + d26[4:]
        new, old = data.ci_24(d26), data.ci_24(d25)
        assert max(abs(a - b) for a, b in zip(new, old)) < 1e-6   # aynı yöntem, aynı sonuç
    assert data.grid_label(days[0]) == "EPİAŞ 2026"
    pk.delete_package(p.id)
    data.reload()
    assert days[0] not in data.all_dates()


def test_factors_package_recomputes_ci(pkg_dir, tmp_path):
    base = data.ci_24("2025-07-15")
    f = tmp_path / "etkb.csv"
    rows = ["Kaynak;tCO2/MWh;tCO2-eşd/MWh"]
    for s, (t, e) in data.factors().items():
        rows.append(f"{pk.SOURCE_NAMES[s]};{str(t).replace('.', ',')};{str(e).replace('.', ',')}")
    f.write_text("\n".join(rows) + "\n", encoding="utf-8")
    same = pk.check_factors_file(f, data.factors())
    assert not same.report.has_errors
    p = pk.add_factors_package(same, "ETKB 2023 (kopya)")
    data.reload()
    assert max(abs(a - b) for a, b in zip(data.ci_24("2025-07-15"), base)) < 1e-6
    assert data.factors_label() == "ETKB 2023 (kopya)"
    pk.delete_package(p.id)

    rows2 = [r.replace("Doğal gaz;0,4;", "Doğal gaz;0,5;") for r in rows]
    f.write_text("\n".join(rows2) + "\n", encoding="utf-8")
    higher = pk.check_factors_file(f, data.factors())
    pk.add_factors_package(higher, "ETKB deneme")
    data.reload()
    assert all(a > b for a, b in zip(data.ci_24("2025-07-15"), base))  # doğal gaz katsayısı arttı


def test_factors_missing_fossil_is_error(pkg_dir, tmp_path):
    f = tmp_path / "eksik.csv"
    f.write_text("Kaynak;tCO2/MWh;tCO2-eşd/MWh\nDoğal gaz;0,4;0,405\n", encoding="utf-8")
    assert pk.check_factors_file(f, data.factors()).report.has_errors
